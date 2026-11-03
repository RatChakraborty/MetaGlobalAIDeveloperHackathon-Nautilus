"""Host-owned control-improvement phase that runs after scientific finalization.

The model may read a sanitized context, propose a bounded change, request a
host-managed evaluation, interpret the reported result and recommend an outcome.
It never executes numerics, supplies metrics, approves its own change or sees
private scenario truth or seeds.
"""
from __future__ import annotations

from copy import deepcopy
import math

from ..controller_context import PARAMETERS, fingerprint
from ..simulator import Controller
from .artifact import build as build_artifact
from .evaluation import LIMITATIONS as EVALUATION_LIMITATIONS
from .patch import EXECUTION, review as review_patch
from .policy import TUNABLE, build_policy, candidate, differences, identity, validate_policy
from .proposal import coordinate_search, validate_change
from .robustness import DEFAULT_SUITE, build_suite, evaluate_suite

SCHEMA = 'nautilus.control-lab.v1'
RECOMMENDATIONS = ('accept', 'reject', 'further_testing')
CONTEXT_LIMITATIONS = (
    'The control phase runs after finalization; it cannot add fault-diagnosis evidence.',
    'Private scenario truth, current values and noise seeds are withheld from the model.',
    'A tracking-metric improvement does not imply that a physical fault was repaired.',
)


def _text(value, limit=1000):
    if type(value) is not str or not value.strip() or len(value) > limit:
        raise ValueError('Invalid control-lab text')
    return value


class ControlLabHost:
    def __init__(self, baseline=Controller(), *, investigation_id='unrecorded', evidence_refs=(),
                 authorized=False, permitted=TUNABLE, evaluation_limit=2, simulation_limit_s=600.,
                 suite=None, rubric=None, patch_lab=False):
        if type(baseline) is not Controller:
            raise ValueError('Approved baseline controller required')
        _text(investigation_id, 200)
        refs = list(evidence_refs)
        for ref in refs:
            if type(ref) is not str or len(ref) != 64 or any(c not in '0123456789abcdef' for c in ref):
                raise ValueError('Public evidence references required')
        if type(authorized) is not bool or type(patch_lab) is not bool:
            raise ValueError('Invalid host policy')
        if type(evaluation_limit) is not int or not 0 <= evaluation_limit <= 4:
            raise ValueError('Bounded evaluation limit required')
        if type(simulation_limit_s) not in (int, float) or not math.isfinite(simulation_limit_s) or not 0 < simulation_limit_s <= 1200:
            raise ValueError('Bounded simulation budget required')
        if type(permitted) not in (list, tuple) or len(set(permitted)) != len(permitted) or any(p not in TUNABLE for p in permitted):
            raise ValueError('Invalid permitted parameter list')
        self._baseline = baseline
        self._policy = build_policy(baseline)
        self._investigation_id = investigation_id
        self._evidence = refs
        self._authorized = authorized
        self._permitted = tuple(permitted)
        self._suite = tuple(DEFAULT_SUITE if suite is None else suite)
        if not self._suite:
            raise ValueError('Development suite required')
        self._rubric = rubric
        self._patch_lab = patch_lab
        self._limit = evaluation_limit
        self._simulation_limit = float(simulation_limit_s)
        self._used_simulations = 0.
        self._search = None
        self._proposals = []
        self._results = []
        self._recommendation = None
        self._patch = None
        self._finished = False

    @property
    def policy(self) -> dict:
        return deepcopy(self._policy)

    @property
    def budget(self) -> dict:
        return {'evaluation_limit': self._limit, 'evaluations': len(self._results),
                'simulation_limit_s': self._simulation_limit, 'simulation_used_s': self._used_simulations}

    @property
    def proposals(self) -> list:
        return deepcopy(self._proposals)

    @property
    def results(self) -> list:
        return [{'proposal_index': index, 'changes': deepcopy(self._proposals[index]['changes']),
                 'decision': result['decision'], 'reasons': list(result['decision_reasons'])}
                for index, result in self._results]

    def context(self) -> dict:
        """Sanitized model-visible context. No truth, seeds, currents or measured trajectories."""
        body = {'schema_version': SCHEMA,
                'phase': 'post-finalization control improvement',
                'investigation_id': self._investigation_id,
                'policy': deepcopy(self._policy),
                'permitted_parameters': list(self._permitted),
                'diagnosis_rubric': deepcopy(self._rubric),
                'screening': None if self._search is None else {
                    'candidates': [{'changes': item['changes'], 'mean_rms_difference_m': item['mean_rms_difference_m'],
                                    'worst_case_cross_track_difference_m': item['worst_case_cross_track_difference_m'],
                                    'admissible': item['admissible']} for item in self._search['attempted']],
                    'best': deepcopy(self._search['best']), 'screening_cases': self._search['screening_cases'],
                    'limitations': list(self._search['limitations'])},
                'budget': self.budget, 'patch_lab': {'available': self._patch_lab,
                                                     'execution': EXECUTION,
                                                     'scope': 'Static diff validation and structural checks only; patch execution is not implemented.'},
                'tools': ['search_candidates', 'propose_change', 'evaluate_change', 'recommend', 'review_patch'],
                'limitations': list(CONTEXT_LIMITATIONS)}
        if set(body) != {'schema_version', 'phase', 'investigation_id', 'policy', 'permitted_parameters',
                         'diagnosis_rubric', 'screening', 'budget', 'patch_lab', 'tools', 'limitations'}:
            raise ValueError('Control-lab context shape changed')
        validate_policy(body['policy'])
        return body

    def search(self) -> dict:
        """Host-run bounded coordinate search over development screening cases."""
        if self._search is None:
            self._search = coordinate_search(self._baseline)
        return {'schema_version': self._search['schema_version'], 'screening_cases': self._search['screening_cases'],
                'best': deepcopy(self._search['best']), 'attempted': deepcopy(self._search['attempted']),
                'budget': deepcopy(self._search['budget']),
                'limitations': list(self._search['limitations'])}

    def propose(self, value) -> dict:
        """Validate a model proposal. Extra fields, including metrics, are rejected."""
        if self._finished:
            raise ValueError('Control lab already finalized')
        if len(self._proposals) >= 4:
            raise ValueError('Proposal limit reached')
        proposal = validate_change(value, self._evidence, self._policy)
        if proposal['parameter'] not in self._permitted:
            raise ValueError('Parameter is not permitted for this phase')
        record = {'index': len(self._proposals), 'changes': {proposal['parameter']: proposal['value']},
                  'proposal': proposal, 'status': 'proposed_not_evaluated'}
        self._proposals.append(record)
        return deepcopy(record)

    def evaluate(self, index: int) -> dict:
        """Run the fixed suite for one proposal; the host alone produces the metrics."""
        if self._finished:
            raise ValueError('Control lab already finalized')
        if type(index) is not int or not 0 <= index < len(self._proposals):
            raise ValueError('Unknown proposal index')
        if len(self._results) >= self._limit:
            raise ValueError('Evaluation budget exhausted')
        estimate = 2 * len(self._suite) * max(case.mission.duration_s for case in self._suite)
        if self._used_simulations + estimate > self._simulation_limit:
            raise ValueError('Simulation budget exhausted')
        if not self._authorized:
            raise ValueError('Host evaluation is not authorized')
        record = self._proposals[index]
        candidate(self._baseline, record['changes'])
        result = evaluate_suite(self._baseline, record['changes'], suite=self._suite)
        self._used_simulations += float(result['budget']['total_simulation_s'])
        record['status'] = 'evaluated'
        self._results.append((index, result))
        return deepcopy({**result, 'proposal_index': index})

    def recommend(self, decision: str, rationale: str, evidence_refs=None) -> dict:
        """Record the model's recommendation; the host rule still governs the artifact."""
        if self._finished or not self._results:
            raise ValueError('A completed host evaluation is required')
        if decision not in RECOMMENDATIONS:
            raise ValueError('Unsupported recommendation')
        _text(rationale, 1000)
        refs = list(evidence_refs or self._evidence[:1])
        if not refs or any(ref not in self._evidence for ref in refs):
            raise ValueError('Public evidence references required')
        self._recommendation = {'recommendation': decision, 'rationale': rationale}
        return deepcopy(self._recommendation)

    def review_patch(self, diff: str) -> dict:
        if not self._patch_lab:
            return {'status': 'unavailable', 'diff': None, 'certified': False, 'sandbox': None, 'checks': [],
                    'notes': ['Controller patch lab is not enabled for this phase.']}
        self._patch = review_patch(diff)
        return deepcopy(self._patch)

    def finish(self) -> dict:
        if self._finished:
            raise ValueError('Control lab already finalized')
        if not self._results:
            raise ValueError('At least one host evaluation is required')
        index, robustness = self._results[-1]
        proposal = self._proposals[index]
        if robustness['decision'] == 'accept':
            change, evidence = proposal['proposal'], proposal['proposal']['evidence_refs']
        else:
            change, evidence = None, (proposal['proposal']['evidence_refs'] if self._proposals else self._evidence[:1])
        artifact = build_artifact(self._investigation_id, evidence or self._evidence[:1], self._policy, change,
                                  robustness, self._recommendation, patch=self._patch, rubric=self._rubric)
        self._artifact = artifact
        self._finished = True
        return artifact

    @property
    def artifact(self):
        return None if not self._finished else deepcopy(self._artifact)


def lab_from_suite(duration_s: float = 45., cable_length_m: float = 30.):
    """Convenience constructor for the declared development suite."""
    return build_suite(duration_s=duration_s, cable_length_m=cable_length_m)


def proposal_fingerprint(proposal: dict) -> str:
    return fingerprint({'parameter': proposal['parameter'], 'value': proposal['value']})


def parameter_units() -> dict:
    return {name: PARAMETERS[name][0] for name in TUNABLE}


def differentiate(baseline: Controller, candidate_controller: Controller) -> dict:
    return differences(build_policy(baseline), candidate_controller)

