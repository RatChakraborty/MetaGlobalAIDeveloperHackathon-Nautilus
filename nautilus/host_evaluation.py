from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math

from .configuration_evaluation import CHANGES, ConfigurationEvaluation, DevelopmentScenario, evaluate_configuration
from .controller_context import PARAMETERS, canonical, configuration, fingerprint
from .simulator import Controller
from .v2_tools import fields as _tool_fields, parse_json

SCHEMA = 'nautilus.post-investigation.v1'
METRICS = ('final_x_m', 'final_y_m', 'elapsed_s', 'rms_cross_track_m', 'max_abs_cross_track_m',
           'fraction_outside_corridor', 'reached_cable_end', 'mission_success', 'command_saturation_fraction',
           'samples', 'outside_corridor_samples', 'completion_time_s', 'termination',
           'saturated_command_samples', 'mean_squared_command_n2')
STATUSES = ('not_proposed', 'rejected_validation', 'proposed_not_executed', 'evaluation_failed',
            'completed_improvement', 'completed_no_improvement')
LIMITATION = 'Post-investigation development comparison; visualization-only metrics, not diagnosis evidence or a verified repair.'


def fields(value, expected):
    if type(value) is not dict: raise ValueError('Post-investigation object required')
    _tool_fields(value, expected)


def _text(value, limit=1000):
    if type(value) is not str or not value.strip() or len(value) > limit:
        raise ValueError('Invalid post-investigation text')


def _sha(value):
    if type(value) is not str or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Invalid post-investigation reference')


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_proposal(value, evidence_refs):
    value = parse_json(value)
    if set(value)-{'parameter', 'value', 'rationale', 'evidence_refs', 'expected_effect'} or not {'parameter', 'value', 'rationale', 'evidence_refs'} <= set(value):
        raise ValueError('Invalid configuration proposal fields')
    name = value['parameter']
    if type(name) is not str or name not in CHANGES:
        raise ValueError('Unsupported configuration proposal parameter')
    _, low, high = PARAMETERS[name]
    if not _number(value['value']) or not low <= value['value'] <= high:
        raise ValueError('Configuration proposal outside approved bounds')
    _text(value['rationale'])
    if 'expected_effect' in value:
        _text(value['expected_effect'], 500)
    refs = value['evidence_refs']
    if type(refs) is not list or not refs or len(refs) > 128 or any(type(r) is not str or r not in evidence_refs for r in refs) or len(set(refs)) != len(refs):
        raise ValueError('Public observation references required')
    return deepcopy(value)


def _final_anchor(ledger):
    previous = None
    refs = []
    for index, event in enumerate(ledger):
        if type(event) is not dict:
            raise ValueError('Invalid finalized ledger')
        body = {k:v for k,v in event.items() if k != 'event_hash'}
        if event.get('index') != index or event.get('previous_hash') != previous or event.get('event_hash') != fingerprint(body):
            raise ValueError('Finalized ledger hash mismatch')
        if event.get('type') == 'observation':
            refs.append(event['event_hash'])
        if event.get('type') == 'finalized' and index != len(ledger)-1:
            raise ValueError('Events after finalization are not supported')
        previous = event['event_hash']
    if not ledger or ledger[-1].get('type') != 'finalized' or not refs:
        raise ValueError('Successful finalization required')
    return previous, refs


def _metrics(value):
    fields(value, METRICS)
    for key, number in value.items():
        if key in ('reached_cable_end', 'mission_success'):
            if type(number) is not bool:
                raise ValueError('Invalid completion metric')
        elif key == 'termination':
            if number not in ('cable_end', 'duration_cap'):
                raise ValueError('Invalid termination metric')
        elif key == 'completion_time_s' and number is None:
            continue
        elif not _number(number):
            raise ValueError('Invalid measured metric')
    for key in ('samples', 'outside_corridor_samples', 'saturated_command_samples'):
        if type(value[key]) is not int or value[key] < (2 if key == 'samples' else 0):
            raise ValueError('Invalid sample count')
    if any(value[k] < 0 for k in ('elapsed_s','rms_cross_track_m','max_abs_cross_track_m','mean_squared_command_n2')):
        raise ValueError('Invalid metric range')
    if any(not 0 <= value[k] <= 1 for k in ('fraction_outside_corridor','command_saturation_fraction')) or any(value[k] > value['samples'] for k in ('outside_corridor_samples','saturated_command_samples')):
        raise ValueError('Invalid metric range')
    if not math.isclose(value['fraction_outside_corridor'],value['outside_corridor_samples']/value['samples'],abs_tol=1e-12):
        raise ValueError('Inconsistent sampled excursion metric')
    reached = value['reached_cable_end']
    if (value['termination'] == 'cable_end') != reached or value['completion_time_s'] != (value['elapsed_s'] if reached else None) or (value['mission_success'] and not reached):
        raise ValueError('Inconsistent mission completion')


def validate_comparison(value):
    fields(value, ('schema_version','scenario_id','baseline','candidate','approved_differences','metric_differences','simulator_sha256','conditions','limitations','scope'))
    if value['schema_version'] != 'nautilus.configuration-evaluation.v1':
        raise ValueError('Unsupported comparison schema')
    _text(value['scenario_id'], 100); _sha(value['simulator_sha256']); _text(value['scope'])
    for key in ('conditions','limitations'):
        if type(value[key]) is not list or not value[key] or len(value[key]) > 20:
            raise ValueError('Invalid comparison qualifications')
        for text in value[key]: _text(text)
    for name in ('baseline','candidate'):
        run = value[name]
        fields(run, ('run_id','controller_id','configuration_id','context_hash','source_sha256','trajectory_sha256','metrics'))
        _text(run['controller_id'])
        for key in ('run_id','configuration_id','context_hash','source_sha256','trajectory_sha256'): _sha(run[key])
        _metrics(run['metrics'])
    if type(value['approved_differences']) is not dict or len(value['approved_differences']) > 1:
        raise ValueError('One proposed configuration parameter required')
    for key, change in value['approved_differences'].items():
        if key not in CHANGES: raise ValueError('Unsupported measured configuration change')
        fields(change, ('baseline','candidate','unit'))
        unit, low, high = PARAMETERS[key]
        if change['unit'] != unit or any(not _number(change[k]) or not low <= change[k] <= high for k in ('baseline','candidate')):
            raise ValueError('Invalid approved difference')
    a,b = value['baseline']['metrics'],value['candidate']['metrics']
    expected = {k:b[k]-v for k,v in a.items() if type(v) in (int,float) and type(b[k]) in (int,float)}
    if type(value['metric_differences']) is not dict or any(not _number(v) for v in value['metric_differences'].values()) or value['metric_differences'] != expected:
        raise ValueError('Measured metric differences do not match')
    return deepcopy(value)


def _references(comparison):
    return {name:{'run_id':comparison[name]['run_id'],'configuration_id':comparison[name]['configuration_id'],
                  'trajectory_sha256':comparison[name]['trajectory_sha256'],
                  'public_file':name+'.public.json','visualization_file':name+'.visualization.json'}
            for name in ('baseline','candidate')}


def validate_post_record(value, ledger):
    fields(value, ('schema_version','investigation_id','ledger_anchor','events'))
    anchor, refs = _final_anchor(ledger)
    if value['schema_version'] != SCHEMA or value['ledger_anchor'] != anchor or value['investigation_id'] != anchor or type(value['events']) is not list or len(value['events']) != 1:
        raise ValueError('Post-investigation anchor mismatch')
    event = value['events'][0]; fields(event, ('hash','body_canonical'))
    if type(event['body_canonical']) is not str or len(event['body_canonical']) > 60000 or hashlib.sha256(event['body_canonical'].encode()).hexdigest() != event['hash']:
        raise ValueError('Post-investigation hash mismatch')
    body = parse_json(event['body_canonical'])
    fields(body, ('index','type','previous_hash','proposal','validation','status','reason','scenario_id','comparison','run_references','budget','assessment_metric','limitations'))
    if canonical(body) != event['body_canonical'] or body['index'] != 0 or body['type'] != 'configuration_evaluation' or body['previous_hash'] != anchor or body['status'] not in STATUSES or type(body['index']) is not int or body['assessment_metric'] != 'rms_cross_track_m':
        raise ValueError('Invalid post-investigation event')
    if body['proposal'] is not None: validate_proposal(body['proposal'],refs)
    if body['validation'] not in ('accepted','rejected','not_requested') or body['limitations'] != [LIMITATION]:
        raise ValueError('Invalid evaluation qualification')
    reasons = {'not_proposed':'no_proposal','rejected_validation':'invalid_proposal',
               'proposed_not_executed':('abstention','not_authorized','parameter_not_permitted','budget_exhausted'),
               'evaluation_failed':'evaluation_failed','completed_improvement':'measured_improvement',
               'completed_no_improvement':'no_measured_improvement'}
    expected_reason = reasons[body['status']]
    if body['reason'] not in (expected_reason if type(expected_reason) is tuple else (expected_reason,)):
        raise ValueError('Invalid evaluation status reason')
    validation = 'not_requested' if body['status']=='not_proposed' else 'rejected' if body['status']=='rejected_validation' else 'accepted'
    if body['validation'] != validation or (body['proposal'] is not None) != (validation == 'accepted'):
        raise ValueError('Invalid proposal validation outcome')
    budget=body['budget'];fields(budget, ('evaluation_limit','simulation_limit_s','attempted_evaluations','reserved_simulation_s','actual_simulation_s'))
    if type(budget['evaluation_limit']) is not int or not 0 <= budget['evaluation_limit'] <= 1 or type(budget['attempted_evaluations']) is not int or not 0 <= budget['attempted_evaluations'] <= budget['evaluation_limit'] or any(not _number(budget[k]) or not 0 <= budget[k] <= 240 for k in ('simulation_limit_s','reserved_simulation_s')) or budget['reserved_simulation_s'] > budget['simulation_limit_s']:
        raise ValueError('Invalid separate evaluation budget')
    if budget['actual_simulation_s'] is not None and (not _number(budget['actual_simulation_s']) or budget['actual_simulation_s'] < 0):
        raise ValueError('Invalid actual evaluation cost')
    attempted = body['status'] in ('evaluation_failed','completed_improvement','completed_no_improvement')
    if budget['attempted_evaluations'] != int(attempted) or (not attempted and (budget['reserved_simulation_s'] != 0 or budget['actual_simulation_s'] != 0)):
        raise ValueError('Invalid evaluation accounting')
    complete = body['status'].startswith('completed_')
    if complete:
        comparison = validate_comparison(body['comparison'])
        if body['scenario_id'] != comparison['scenario_id'] or body['run_references'] != _references(comparison):
            raise ValueError('Comparison run references mismatch')
        change = comparison['approved_differences'];proposal = body['proposal']
        if change and (set(change) != {proposal['parameter']} or change[proposal['parameter']]['candidate'] != proposal['value']):
            raise ValueError('Measured change differs from proposal')
        improved = comparison['metric_differences']['rms_cross_track_m'] < 0
        if (body['status'] == 'completed_improvement') != improved or budget['actual_simulation_s'] != sum(comparison[k]['metrics']['elapsed_s'] for k in ('baseline','candidate')) or budget['actual_simulation_s'] > budget['reserved_simulation_s']+1e-8:
            raise ValueError('Invalid measured outcome or accounting')
    else:
        if body['comparison'] is not None or body['run_references']:
            raise ValueError('Unexecuted comparison cannot have measured results')
        if body['status'] == 'evaluation_failed':
            _text(body['scenario_id'],100)
            if budget['actual_simulation_s'] is not None: raise ValueError('Failed evaluation cost is unknown')
        elif body['scenario_id'] is not None: raise ValueError('Unexecuted scenario must remain undisclosed')
    if ledger[-1]['confidence'] == 'abstain' and attempted:
        raise ValueError('Abstention cannot automatically evaluate a proposal')
    return deepcopy(value)


@dataclass(frozen=True)
class HostEvaluationResult:
    record: dict
    evaluation: ConfigurationEvaluation | None = None


class ConfigurationEvaluationHost:
    def __init__(self, scenario: DevelopmentScenario, baseline: Controller, *, authorized=False,
                 permitted_parameters=CHANGES, evaluation_limit=1, simulation_limit_s=240.):
        if type(scenario) is not DevelopmentScenario or scenario.purpose != 'development-only':
            raise ValueError('Trusted development conditions required')
        if not _number(scenario.mission.duration_s) or not 0 < scenario.mission.duration_s <= 120:
            raise ValueError('Invalid host simulation duration')
        configuration(baseline)
        if type(authorized) is not bool or type(evaluation_limit) is not int or not 0 <= evaluation_limit <= 1 or not _number(simulation_limit_s) or not 0 <= simulation_limit_s <= 240 or type(permitted_parameters) not in (list,tuple) or len(set(permitted_parameters)) != len(permitted_parameters) or any(p not in CHANGES for p in permitted_parameters):
            raise ValueError('Invalid host evaluation policy')
        self._scenario,self._baseline = scenario,baseline
        self._authorized,self._parameters = authorized,tuple(permitted_parameters)
        self._limit,self._time = evaluation_limit,float(simulation_limit_s)
        self._finished = False

    def finish(self, laboratory, response) -> HostEvaluationResult:
        # Finalize through the existing tool; never append to its closed ledger.
        if self._finished or laboratory._closed:
            raise ValueError('Investigation or host phase already finalized')
        if type(response) is str: response=parse_json(response)
        elif type(response) is not dict: raise ValueError('Structured final response envelope required')
        if set(response)-{'final_decision','configuration_proposal'} or 'final_decision' not in response:
            raise ValueError('Invalid final response envelope')
        decision=parse_json(response['final_decision'])
        fields(decision, ('diagnosis','confidence','ambiguity_statement'))
        proposal=None;invalid=False
        if response.get('configuration_proposal') is not None:
            try: proposal=validate_proposal(response['configuration_proposal'],laboratory.evidence_refs())
            except (ValueError,TypeError,KeyError): invalid=True
        laboratory.finalize(**decision)
        self._finished=True
        ledger=deepcopy(laboratory.ledger);anchor,_=_final_anchor(ledger)
        body={'index':0,'type':'configuration_evaluation','previous_hash':anchor,'proposal':proposal,
              'validation':'rejected' if invalid else 'accepted' if proposal else 'not_requested',
              'status':'rejected_validation' if invalid else 'not_proposed',
              'reason':'invalid_proposal' if invalid else 'no_proposal','scenario_id':None,
              'comparison':None,'run_references':{},
              'budget':{'evaluation_limit':self._limit,'simulation_limit_s':self._time,
                        'attempted_evaluations':0,'reserved_simulation_s':0.,'actual_simulation_s':0.},
              'assessment_metric':'rms_cross_track_m','limitations':[LIMITATION]}
        evaluation=None
        if proposal:
            reserve=2*self._scenario.mission.duration_s
            reason=('abstention' if decision['confidence']=='abstain' else 'not_authorized' if not self._authorized
                    else 'parameter_not_permitted' if proposal['parameter'] not in self._parameters
                    else 'budget_exhausted' if not self._limit or reserve > self._time else None)
            body.update(status='proposed_not_executed',reason=reason)
            if reason is None:
                body['budget'].update(attempted_evaluations=1,reserved_simulation_s=reserve,actual_simulation_s=None)
                body.update(status='evaluation_failed',reason='evaluation_failed',scenario_id=self._scenario.identifier)
                try:
                    evaluation=evaluate_configuration(self._scenario,self._baseline,{proposal['parameter']:proposal['value']})
                    comparison=validate_comparison(evaluation.summary())
                    improved=comparison['metric_differences']['rms_cross_track_m'] < 0
                    body.update(status='completed_improvement' if improved else 'completed_no_improvement',
                                reason='measured_improvement' if improved else 'no_measured_improvement',
                                comparison=comparison,run_references=_references(comparison))
                    body['budget']['actual_simulation_s']=sum(comparison[k]['metrics']['elapsed_s'] for k in ('baseline','candidate'))
                except Exception:
                    evaluation=None
        record={'schema_version':SCHEMA,'investigation_id':anchor,'ledger_anchor':anchor,
                'events':[{'hash':fingerprint(body),'body_canonical':canonical(body)}]}
        validate_post_record(record,ledger)
        if laboratory.ledger != ledger: raise ValueError('Finalized ledger changed during host evaluation')
        return HostEvaluationResult(record,evaluation)
