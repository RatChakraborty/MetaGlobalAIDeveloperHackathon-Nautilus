from copy import deepcopy
from dataclasses import asdict
import math
import numpy as np
from .v2_tools import InvestigationSession, capability_schema, fields, verdict
from .v2_models import fit_model, validate_proposal, REGISTRY, configs
from .diagnosis import _prepare, _predict, FitConfig
from .simulator import Vehicle, Experiment, effective_vehicle
from .reliability import fit as experimental_fit, residual_diagnostics
from .lab_safety import SafeBackend, screen, TAIL_S, advisory_report
from .v2_experiments import parse_trial


class Laboratory(InvestigationSession):
    def __init__(self, observations, backend, *, method='singleton', **limits):
        if type(backend) is not SafeBackend:
            raise ValueError('Validated simulation backend required')
        if method not in ('singleton', 'nuisance', 'discrepancy'):
            raise ValueError('Unknown numerical method')
        if any(k in limits for k in ('initial_fits', 'fit_provider')):
            raise ValueError('Externally supplied fits are not accepted')
        super().__init__(observations, backend.execute, **limits)
        self.method = method
        self._backend = backend
        self._reports = {}

    def propose_hypothesis(self, template, knobs, bounds, rationale):
        if self._closed: raise ValueError('Session finalized')
        spec, _ = validate_proposal(template, knobs, bounds)
        if type(rationale) is not str or len(rationale) > 2000: raise ValueError('Invalid rationale')
        if self.method != 'singleton' and (knobs or bounds):
            raise ValueError('Experimental methods use declared shared bounds and starts')
        attempts = (1 if knobs else self._starts) if spec.parameter or self.method != 'singleton' else 0
        if self.fit_calls >= self._fit_limit or self.optimization_attempts+attempts > self._optimization_limit:
            raise ValueError('Fitting budget exhausted')
        self.fit_calls += 1
        self.optimization_attempts += attempts
        try:
            if self.method == 'singleton':
                fitted = fit_model(self.episodes, template, knobs=knobs, bounds=bounds, starts=self._starts)
                report = asdict(fitted)
                self._fits[template] = fitted
                faults, plant, _ = configs(template, fitted.parameters.get(spec.parameter))
                residuals = []
                for episode in self.episodes:
                    a = _prepare(episode['observations'], FitConfig(method='observer'))[0]
                    prediction = _predict(a, effective_vehicle(Vehicle(), plant), faults, 'observer',
                                          {'actuator_tau_s': plant.actuator_tau_s, 'thrust_deadzone_n': plant.thrust_deadzone_n})
                    delta = prediction-a[:, 1:4]
                    delta[:, 1] = np.arctan2(np.sin(delta[:, 1]), np.cos(delta[:, 1]))
                    delta /= np.array([.035, .004, .003]); delta[1:] /= math.sqrt(2)
                    residuals.append(delta)
                report['residual_diagnostics'] = residual_diagnostics(residuals)
                report['identifiability'] = {'scaled_norm': fitted.sensitivity_scaled_norm,
                    'rank': (int(fitted.sensitivity_scaled_norm > 1e-8) if spec.parameter else 0),
                    'condition': (1. if spec.parameter and fitted.sensitivity_scaled_norm > 1e-8 else None),
                    'qualification': 'One-dimensional local sensitivity only; no model-identity guarantee.'}
            else:
                report = experimental_fit(self.episodes, template, method=self.method, starts=self._starts)
                report['experimental'] = True
                report['warning'] = 'No demonstrated attribution improvement; nuisance absorption and boundary saturation remain.'
        except (ValueError, FloatingPointError, OverflowError, np.linalg.LinAlgError) as exc:
            self._reports.pop(template, None); self._fits.pop(template, None)
            self._event('fit_failure', {'template': template, 'method': self.method, 'reason': str(exc)})
            return {'status': 'OPTIMIZATION_FAILURE', 'template': template, 'reason': str(exc)}
        report['bound_hits'] = [k for k, v in report['parameters'].items() if k in report['bounds'] and min(v-report['bounds'][k][0], report['bounds'][k][1]-v) < .001*(report['bounds'][k][1]-report['bounds'][k][0])]
        report.update(method=self.method, evidence_refs=self.evidence_refs(),
                      interpretation='Numerical evidence under model assumptions, not physical attribution.')
        self._reports[template] = report
        self._event('fit', {'report': {k: v for k, v in report.items() if k != 'elapsed_s'}, 'rationale': rationale})
        return deepcopy(report)

    def request_experiment(self, name, params):
        if self._closed: raise ValueError('Session finalized')
        trial = parse_trial(name, params)
        if self._allowed is not None and trial.key not in self._allowed: raise ValueError('Outside experiment menu')
        cost = trial.duration_s+self._backend.tail_reserve_s
        if self.tests >= self._experiment_limit or self.test_time_s+cost > self._time_limit or trial.key in self._seen:
            raise ValueError('Experiment budget exhausted or repeated action')
        safety = advisory_report(screen(trial), self._backend.mode)
        self._event('safety', {'request': asdict(trial), 'screen': safety})
        if not safety['accepted'] and self._backend.mode == 'simulation_enforced':
            return {'accepted': False, 'action_id': trial.key, 'constraint': 'predictive_envelope',
                    'safety': safety, 'may_request_alternative': True}
        self.tests += 1; self.test_time_s += cost; self._seen.add(trial.key)
        self._reports.clear(); self._fits.clear()
        result = self._execute(trial)
        if not result['accepted']: return result
        rows = result['observations']
        _prepare(rows, FitConfig(method='observer'))
        prefix = [r for r in rows if r['time_s'] < result['execution']['fit_end_exclusive_s']-1e-9]
        if len(prefix) >= 3:
            self.episodes.append({'observations': prefix, 'experiment': trial.experiment()})
        ref = self._event('observation', {'observations': rows, 'execution': result['execution'],
                                         'fit_rows': len(prefix), 'request': asdict(trial)})
        return {**result, 'evidence_ref': ref, 'fit_reports_stale': True,
                'fit_scope': 'Actual waveform samples; enforced intervention/tail excluded from command-law fitting.'}

    def get_fit_report(self):
        if self.method == 'singleton':
            summary = verdict(list(self._fits.values()))
            summary['status'] = summary['kind'].upper()
        else:
            from .reliability import diagnose
            summary = diagnose(list(self._reports.values()))
        return deepcopy({'fits': list(self._reports.values()), 'numerical_summary': summary,
            'remaining': {'fit_calls': self._fit_limit-self.fit_calls,
                          'optimization_attempts': self._optimization_limit-self.optimization_attempts,
                          'experiments': self._experiment_limit-self.tests,
                          'time_s': self._time_limit-self.test_time_s},
            'evidence_refs': self.evidence_refs(), 'history': self.ledger,
            'registry': list(REGISTRY), 'method': self.method,
            'safety_constraints': {'corridor_m': 1.5, 'predictive_limit_m': 1.1, 'guard_m': .9, 'tail_reserve_s': self._backend.tail_reserve_s, 'mode': self._backend.mode},
            'schemas': capability_schema(),
            'scope': 'Only requested models were evaluated. Investigator may disagree or abstain.'})

    def finalize(self, diagnosis, confidence, ambiguity_statement):
        if self._closed: raise ValueError('Session finalized')
        if type(diagnosis) is not dict: raise ValueError('Structured diagnosis required')
        fields(diagnosis, ('hypothesis', 'evidence_refs'))
        refs = diagnosis['evidence_refs']; name = diagnosis['hypothesis']
        if type(refs) is not list or not refs or any(type(r) is not str or r not in self.evidence_refs() for r in refs):
            raise ValueError('Actual evidence references required')
        if confidence not in ('supported', 'tentative', 'abstain') or type(ambiguity_statement) is not str or not 1 <= len(ambiguity_statement.strip()) <= 4000:
            raise ValueError('Qualified confidence and stop reason required')
        if confidence == 'abstain':
            if name is not None: raise ValueError('Abstention cannot assert a cause')
        elif type(name) is not str or name not in self._reports or not self._reports[name]['converged']:
            raise ValueError('Current fitted evidence required')
        result = {'diagnosis': diagnosis, 'confidence': confidence, 'stop_reason': ambiguity_statement,
                  'numerical_summary': self.get_fit_report()['numerical_summary'],
                  'interpretation': 'Investigator claim; correctness is evaluated privately, not certified by this interface.'}
        self._event('finalized', result); self._closed = True
        return deepcopy(result)
