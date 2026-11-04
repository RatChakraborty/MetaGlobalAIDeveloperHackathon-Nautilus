"""Bounded Muse controller-engineering loop (mock provider only).

The loop gives a model a fixed tool surface over the trusted evaluator. Every
tool call is schema-checked, every candidate is validated by the IR, and every
number in the transcript comes from a real simulator run. The provider here is
deterministic and offline: it chooses its next tool from the evidence it has
already observed, so the workflow can fail, revise and abstain rather than
replaying a fixed script.

Live provider calls are not implemented and remain disabled: `live_available()`
is False unless an operator explicitly enables them, which this branch never
does. No credential, price or reservation is read here.
"""
from __future__ import annotations

import os
import time
from copy import deepcopy
from dataclasses import dataclass, field

from nautilus.policy_ir import PARAM_LIMITS, PolicyError, baseline_policy, validate
from nautilus.policy_source import from_source, to_source
from nautilus.studio import cases, paired_trial, policy_fingerprint, robustness

TOOLS = (
    {'name': 'inspect_controller', 'description': 'Read the baseline controller IR, readable source and fingerprint.',
     'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False}},
    {'name': 'inspect_diagnosis_evidence', 'description': 'Read public cross-track evidence from matched baseline runs.',
     'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False}},
    {'name': 'propose_controller_revision', 'description': 'Propose a structural revision, by IR parameters or by source text.',
     'parameters': {'type': 'object', 'properties': {
         'candidate_id': {'type': 'string'}, 'rationale': {'type': 'string'},
         'evidence_refs': {'type': 'array', 'items': {'type': 'string'}},
         'params': {'type': 'object', 'description': 'IR parameter overrides. Send only one of params or source; never both.'},
         'source': {'type': 'string', 'description': 'Complete controller source text. Send only one of params or source; never both.'}},
         'required': ['candidate_id', 'rationale'], 'additionalProperties': False}},
    {'name': 'validate_controller', 'description': 'Validate a proposed candidate against the IR limits.',
     'parameters': {'type': 'object', 'properties': {'candidate_id': {'type': 'string'}},
                    'required': ['candidate_id'], 'additionalProperties': False}},
    {'name': 'execute_controller_trial', 'description': 'Run matched paired development trials for a candidate.',
     'parameters': {'type': 'object', 'properties': {'candidate_id': {'type': 'string'}},
                    'required': ['candidate_id'], 'additionalProperties': False}},
    {'name': 'inspect_experiment_results', 'description': 'Read the recorded numerical result of a candidate trial.',
     'parameters': {'type': 'object', 'properties': {'candidate_id': {'type': 'string'}},
                    'required': ['candidate_id'], 'additionalProperties': False}},
    {'name': 'compare_candidate_policies', 'description': 'Compare two evaluated candidates numerically.',
     'parameters': {'type': 'object', 'properties': {'candidate_a': {'type': 'string'},
                    'candidate_b': {'type': 'string'}}, 'required': ['candidate_a', 'candidate_b'],
                    'additionalProperties': False}},
    {'name': 'evaluate_policy_robustness', 'description': 'Evaluate a candidate on the held-out robustness split.',
     'parameters': {'type': 'object', 'properties': {'candidate_id': {'type': 'string'}},
                    'required': ['candidate_id'], 'additionalProperties': False}},
    {'name': 'finalize_controller_recommendation', 'description': 'End the session with a decision or abstention.',
     'parameters': {'type': 'object', 'properties': {'candidate_id': {'type': 'string'},
                    'decision': {'type': 'string', 'enum': ['recommend', 'reject', 'abstain']},
                    'rationale': {'type': 'string'}}, 'required': ['decision', 'rationale'],
                    'additionalProperties': False}},
)
TOOL_NAMES = tuple(tool['name'] for tool in TOOLS)
MAX_INVALID_CALLS = 3


def muse_enabled() -> bool:
    """Server-side kill switch. Live Muse is off unless NAUTILUS_MUSE_ENABLED is exactly 'true'."""
    return os.environ.get('NAUTILUS_MUSE_ENABLED', '').strip().lower() == 'true'


def live_available() -> bool:
    """Live Studio provider is available only when the kill switch is on and a key is configured."""
    return muse_enabled() and bool(os.environ.get('MODEL_API_KEY', '').strip())


class ToolError(ValueError):
    pass


@dataclass
class Budget:
    max_requests: int = 12
    max_candidates: int = 3
    max_trials: int = 12
    max_seconds: float = 180.0
    requests: int = 0
    trials: int = 0
    started: float = field(default_factory=time.monotonic)

    def charge(self):
        self.requests += 1
        if self.requests > self.max_requests:
            raise ToolError('model request budget exhausted')
        if time.monotonic() - self.started > self.max_seconds:
            raise ToolError('wall-clock budget exhausted')

    def as_dict(self):
        return {'requests': self.requests, 'max_requests': self.max_requests,
                'trials': self.trials, 'max_trials': self.max_trials,
                'candidates': self.max_candidates,
                'elapsed_s': round(time.monotonic() - self.started, 3),
                'max_seconds': self.max_seconds}


class Session:
    """State and trust boundary of one engineering session."""

    def __init__(self, budget: Budget | None = None, handoff: dict | None = None):
        self.budget = budget or Budget()
        self.handoff = handoff
        self.baseline = baseline_policy()
        self.candidates = {}
        self.results = {}
        self.robustness = {}
        self.evidence = None
        self.transcript = []
        self.final = None
        # Bounded evidence memory: stable IDs (M1, M2, ...) survive eviction of older entries.
        self.memory = []
        self._memory_next = 1
        # Hypotheses cite evidence IDs; the action log is append-only and never edited in place.
        self.hypotheses = {}
        self.action_log = []

    MEMORY_LIMIT = 16

    def _log(self, action, candidate_id, **detail):
        self.action_log.append({'seq': len(self.action_log) + 1, 'action': action,
                                'candidate_id': candidate_id, **detail})

    def remember(self, kind, summary):
        entry = {'id': f'M{self._memory_next}', 'kind': kind, 'summary': str(summary)[:300]}
        self._memory_next += 1
        self.memory.append(entry)
        del self.memory[:-self.MEMORY_LIMIT]
        return entry['id']

    # ---- tool implementations -------------------------------------------
    def inspect_controller(self):
        return {'policy': self.baseline, 'source': to_source(self.baseline),
                'fingerprint': policy_fingerprint(self.baseline),
                'ir_limits': {'max_nodes': 96, 'max_depth': 14, 'parameters': PARAM_LIMITS}}

    def inspect_diagnosis_evidence(self):
        """Public, truth-free evidence: the investigation handoff when provided, else matched tracking error."""
        if self.handoff is not None:
            return {'source': 'investigation_handoff', 'handoff': self.handoff,
                    'uncertainty': 'hypotheses are candidate explanations, not proven causes',
                    'hidden_truth_exposed': False}
        if self.evidence is None:
            trial = paired_trial(self.baseline, 'development',
                                 scenario_ids={cases('development')[1].identifier})
            row = trial['rows'][0]
            self.evidence = {'evidence_id': 'E1', 'scenario_id': row['scenario_id'], 'matched': True,
                             'baseline_rms_cross_track_m': row['baseline']['rms_cross_track_m'],
                             'baseline_max_abs_cross_track_m': row['baseline']['max_abs_cross_track_m'],
                             'baseline_fraction_outside_corridor': row['baseline']['fraction_outside_corridor'],
                             'uncertainty': 'inferred from observed tracking error; not a confirmed fault',
                             'hidden_truth_exposed': False}
        return self.evidence

    def propose_controller_revision(self, candidate_id, rationale, params=None, source=None, evidence_refs=None):
        if candidate_id in self.candidates:
            raise ToolError('candidate id already used')
        if self.evidence is None and self.handoff is None:
            raise ToolError('inspect diagnosis evidence before proposing a revision')
        if len(self.candidates) >= self.budget.max_candidates:
            raise ToolError('candidate budget exhausted')
        if not isinstance(rationale, str) or not 1 <= len(rationale) <= 500:
            raise ToolError('rationale must be short text')
        refs = list(evidence_refs or [])
        known = {'E1'} if self.evidence is not None else set()
        if any(ref not in known for ref in refs):
            raise ToolError('evidence_refs must cite evidence ids returned by inspect_diagnosis_evidence')
        policy = deepcopy(self.baseline)
        policy['name'] = candidate_id
        if source is not None:
            if params:
                raise ToolError('provide either source or parameters, not both')
            policy = from_source(source, name=candidate_id)
        else:
            merged = dict(policy.get('params', {}))
            merged.update(params if isinstance(params, dict) else {})
            policy['params'] = merged
            validate(policy)
        self.candidates[candidate_id] = {'policy': policy, 'rationale': rationale,
                                         'validated': False, 'source': to_source(policy)}
        # Hypothesis record cites evidence IDs; written only after the candidate is accepted.
        self.hypotheses[candidate_id] = {'hypothesis': rationale, 'evidence_refs': refs}
        self._log('propose', candidate_id, refs=refs)
        return {'candidate_id': candidate_id, 'rationale': rationale,
                'params': policy.get('params', {}), 'fingerprint': policy_fingerprint(policy)}

    def validate_controller(self, candidate_id):
        record = self._candidate(candidate_id)
        try:
            validate(record['policy'])
        except PolicyError as exc:
            return {'candidate_id': candidate_id, 'valid': False, 'error': str(exc)}
        record['validated'] = True
        record['source'] = to_source(record['policy'])
        return {'candidate_id': candidate_id, 'valid': True, 'source': record['source'],
                'params': record['policy'].get('params', {})}

    def execute_controller_trial(self, candidate_id):
        record = self._candidate(candidate_id)
        if not record['validated']:
            raise ToolError('candidate must be validated before execution')
        if self.budget.trials >= self.budget.max_trials:
            raise ToolError('trial budget exhausted')
        trial = paired_trial(record['policy'], 'development')
        self.budget.trials += len(trial['rows'])
        self.results[candidate_id] = trial
        self._log('trial', candidate_id, outcome=trial['outcome']['label'])
        # Counterfactual: each row replays the baseline controller on the identical scenario.
        self.remember('counterfactual', f'{candidate_id} vs baseline on identical scenarios: '
                      f"{trial['outcome']['label']}")
        return {'candidate_id': candidate_id, 'outcome': trial['outcome'],
                'rows': [{k: row[k] for k in ('scenario_id', 'baseline', 'candidate')}
                         for row in trial['rows']],
                'aggregate': trial['decision']['aggregate'], 'gates': trial['decision']['gates']}

    def inspect_experiment_results(self, candidate_id):
        trial = self.results.get(candidate_id)
        if trial is None:
            raise ToolError('no executed trial for that candidate')
        worst = max(trial['rows'], key=lambda row: row['candidate']['rms_cross_track_m'])
        return {'candidate_id': candidate_id, 'outcome': trial['outcome'],
                'per_case_rms': [{'scenario_id': row['scenario_id'],
                                  'baseline_rms_cross_track_m': row['baseline']['rms_cross_track_m'],
                                  'candidate_rms_cross_track_m': row['candidate']['rms_cross_track_m'],
                                  'baseline_saturation_fraction': row['baseline']['command_saturation_fraction'],
                                  'candidate_saturation_fraction': row['candidate']['command_saturation_fraction']}
                                 for row in trial['rows']],
                'worst_candidate_case': worst['scenario_id']}

    def compare_candidate_policies(self, candidate_a, candidate_b):
        a, b = self.results.get(candidate_a), self.results.get(candidate_b)
        if a is None or b is None:
            raise ToolError('both candidates must have executed trials')
        mean = lambda t: t['decision']['aggregate']['mean_rms_cross_track_m']['difference']
        return {'a': candidate_a, 'b': candidate_b,
                'a_mean_rms_difference_m': mean(a), 'b_mean_rms_difference_m': mean(b),
                'a_outcome': a['outcome']['label'], 'b_outcome': b['outcome']['label'],
                'better': candidate_a if mean(a) < mean(b) else candidate_b}

    def evaluate_policy_robustness(self, candidate_id):
        record = self._candidate(candidate_id)
        report = robustness(record['policy'])
        # Approval is bound to the exact controller version and the held-out split.
        self.robustness[candidate_id] = {**report, 'fingerprint': policy_fingerprint(record['policy']),
                                         'protocol': 'held_out:' + report['part']}
        self.budget.trials += len(report['rows'])
        return {'candidate_id': candidate_id, 'part': report['part'],
                'outcome': report['outcome'],
                'per_case': [{'scenario_id': row['scenario_id'],
                              'baseline_rms_cross_track_m': row['baseline']['rms_cross_track_m'],
                              'candidate_rms_cross_track_m': row['candidate']['rms_cross_track_m']}
                             for row in report['rows']],
                'note': 'Held-out split: reported for evidence, never used to select the candidate.'}

    def finalize_controller_recommendation(self, decision, rationale, candidate_id=None):
        if decision not in ('recommend', 'reject', 'abstain'):
            raise ToolError('decision must be recommend, reject or abstain')
        if not isinstance(rationale, str) or not 1 <= len(rationale) <= 1000:
            raise ToolError('rationale must be short text')
        if decision == 'recommend':
            trial = self.results.get(candidate_id)
            if trial is None or trial['outcome']['label'] != 'Recommended':
                raise ToolError('refusing to recommend a candidate without a Recommended trial')
            robust = self.robustness.get(candidate_id)
            if robust is None:
                raise ToolError('refusing to recommend a candidate before held-out robustness is evaluated')
            if robust['fingerprint'] != policy_fingerprint(self._candidate(candidate_id)['policy']):
                raise ToolError('refusing to recommend: robustness was evaluated on a different controller version')
            if robust['protocol'] != 'held_out:held_out':
                raise ToolError('refusing to recommend: robustness was not evaluated on the held-out split')
            if robust['outcome']['label'] != 'Recommended':
                raise ToolError('refusing to recommend a candidate whose held-out robustness is not Recommended')
        self.final = {'decision': decision, 'rationale': rationale, 'candidate_id': candidate_id,
                      'budget': self.budget.as_dict()}
        return self.final

    def _candidate(self, candidate_id):
        record = self.candidates.get(candidate_id)
        if record is None:
            raise ToolError('unknown candidate')
        return record


def call(session: Session, name: str, arguments: dict) -> dict:
    """Schema-check a tool call, then dispatch it."""
    if name not in TOOL_NAMES:
        raise ToolError(f'unknown tool: {name}')
    schema = next(tool for tool in TOOLS if tool['name'] == name)['parameters']
    if type(arguments) is not dict:
        raise ToolError('arguments must be an object')
    unknown = set(arguments) - set(schema['properties'])
    if unknown:
        raise ToolError(f'unknown arguments: {sorted(unknown)}')
    missing = [key for key in schema.get('required', []) if key not in arguments]
    if missing:
        raise ToolError(f'missing arguments: {missing}')
    for key, value in arguments.items():
        expected = schema['properties'][key].get('type')
        ok = {'string': type(value) is str, 'object': type(value) is dict,
              'array': type(value) is list}.get(expected, True) if expected else True
        if not ok:
            raise ToolError(f'argument {key} must be {expected}')
        if expected == 'string' and len(value) > 4000:
            raise ToolError(f'argument {key} too long')
    if name == 'finalize_controller_recommendation':
        enum = schema['properties']['decision']['enum']
        if arguments['decision'] not in enum:
            raise ToolError('invalid decision')
    session.budget.charge()
    result = getattr(session, name)(**arguments)
    session.transcript.append({'tool': name, 'arguments': arguments, 'result': result})
    return result


class MockMuse:
    """Deterministic provider that selects tools from observed evidence."""

    name = 'mock-muse-engineer'

    def __init__(self, first_params=None, second_params=None):
        self.first_params = first_params or {'integral_ki': 6.0, 'integral_limit': 1.5}
        self.second_params = second_params or {'integral_ki': 3.0, 'integral_limit': 0.8}

    def next_call(self, session: Session, observations) -> dict:
        seen = [step['tool'] for step in observations]
        if 'inspect_controller' not in seen:
            return {'tool': 'inspect_controller', 'arguments': {}}
        if 'inspect_diagnosis_evidence' not in seen:
            return {'tool': 'inspect_diagnosis_evidence', 'arguments': {}}
        proposals = [step for step in observations if step['tool'] == 'propose_controller_revision']
        trials = [step for step in observations if step['tool'] == 'execute_controller_trial']
        if not proposals:
            return {'tool': 'propose_controller_revision', 'arguments': {
                'candidate_id': 'integral-ki-6',
                'rationale': 'Observed cross-track bias with zero steady-state correction; add bounded integral action.',
                'params': dict(self.first_params)}}
        last = proposals[-1]['arguments']['candidate_id']
        if not any(step['arguments'].get('candidate_id') == last for step in observations
                   if step['tool'] == 'validate_controller'):
            return {'tool': 'validate_controller', 'arguments': {'candidate_id': last}}
        if not any(step['arguments'].get('candidate_id') == last for step in trials):
            return {'tool': 'execute_controller_trial', 'arguments': {'candidate_id': last}}
        outcome = trials[-1]['result']['outcome']
        if outcome['label'] == 'Recommended':
            if not any(step['tool'] == 'evaluate_policy_robustness' for step in observations):
                return {'tool': 'evaluate_policy_robustness', 'arguments': {'candidate_id': last}}
            return {'tool': 'finalize_controller_recommendation', 'arguments': {
                'candidate_id': last, 'decision': 'recommend',
                'rationale': 'Development gates passed and the held-out robustness split did not regress; '
                             'recommend as a bounded integral augmentation of the baseline law.'}}
        if outcome['label'] == 'Rejected' and len(proposals) == 1:
            return {'tool': 'propose_controller_revision', 'arguments': {
                'candidate_id': 'integral-ki-3',
                'rationale': 'Previous integral gain destabilised degraded-thruster cases; reduce gain and bound.',
                'params': dict(self.second_params)}}
        return {'tool': 'finalize_controller_recommendation', 'arguments': {
            'candidate_id': last, 'decision': 'abstain',
            'rationale': 'Recorded evidence is inconclusive: neither a gated improvement nor a clear regression.'}}


def run_session(provider=None, budget: Budget | None = None, session: Session | None = None,
                handoff: dict | None = None) -> dict:
    """Run the bounded loop. Stops on finalize, on budget exhaustion, or on tool error."""
    provider = provider or MockMuse()
    session = session or Session(budget, handoff=handoff)
    stopped = None
    invalid = 0
    while session.final is None:
        try:
            decision = provider.next_call(session, list(session.transcript))
        except ToolError as exc:
            # A malformed model reply is an invalid call the model can correct, unless a
            # budget or ceiling is exhausted. Record it and count it toward MAX_INVALID_CALLS.
            if 'budget' in str(exc) or 'ceiling' in str(exc):
                stopped = str(exc)
                break
            session.transcript.append({'tool': None, 'arguments': {}, 'error': str(exc)})
            invalid += 1
            if invalid >= MAX_INVALID_CALLS:
                stopped = 'too many invalid tool calls'
                break
            continue
        if decision.get('tool') not in TOOL_NAMES:
            stopped = 'provider requested an unsupported tool'
            break
        try:
            call(session, decision['tool'], decision.get('arguments') or {})
            invalid = 0
        except ToolError as exc:
            # Budget exhaustion stops the session; other refusals are returned to the model as errors.
            session.transcript.append({'tool': decision['tool'], 'arguments': decision.get('arguments') or {},
                                       'error': str(exc)})
            if 'budget' in str(exc) or 'ceiling' in str(exc):
                stopped = str(exc)
                break
            invalid += 1
            if invalid >= MAX_INVALID_CALLS:
                stopped = 'too many invalid tool calls'
                break
        except PolicyError as exc:
            session.transcript.append({'tool': decision['tool'], 'arguments': decision.get('arguments') or {},
                                       'error': 'invalid controller: ' + str(exc)})
            invalid += 1
            if invalid >= MAX_INVALID_CALLS:
                stopped = 'too many invalid controller proposals'
                break
    return {'final': session.final, 'stopped': stopped, 'transcript': session.transcript,
            'budget': session.budget.as_dict(),
            'candidates': {key: {'rationale': value['rationale'], 'params': value['policy'].get('params', {}),
                                 'source': value['source']} for key, value in session.candidates.items()},
            'results': {key: {'outcome': value['outcome'],
                              'rows': [{k: row[k] for k in ('scenario_id', 'baseline', 'candidate')}
                                       for row in value['rows']],
                              'gates': value['decision']['gates']}
                        for key, value in session.results.items()},
            'robustness': {key: {'outcome': value['outcome'],
                                 'rows': [{k: row[k] for k in ('scenario_id', 'baseline', 'candidate')}
                                          for row in value['rows']]}
                           for key, value in session.robustness.items()},
            'mock': True, 'live_available': live_available(),
            'model': provider.name, 'provider_calls': 0}
