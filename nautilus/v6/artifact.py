"""Validated engineering recommendation package for one control change.

The artifact is a review document. It records what was proposed, what the host
measured, which declared gates passed and what remains unresolved. It is never a
deployment instruction and never claims a physical repair.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

from ..controller_context import PARAMETERS, fingerprint
from .policy import TUNABLE, identity, validate_policy
from .robustness import validate_robustness

SCHEMA = 'nautilus.control-lab-recommendation.v1'
DIFF_SCHEMA = 'nautilus.configuration-diff.v1'
SCOPE = 'Engineering recommendation from matched offline simulation; not a deployed repair, safety certificate or diagnosis evidence.'
HUMAN_REVIEW = 'required'
CHECKLIST = (
    'Confirm the recorded diagnosis supports a controller change rather than a hardware repair.',
    'Review every development scenario and the worst-case corridor result.',
    'Confirm the approved differences match the intended configuration.',
    'Decide separately whether the change is deployed; this artifact grants no authority.',
)
PATCH_STATES = ('not_attempted', 'review_only', 'executed', 'unavailable')


def _text(value, limit=1000):
    if type(value) is not str or not value.strip() or len(value) > limit:
        raise ValueError('Invalid control-lab text')
    return value


def _sha(value):
    if type(value) is not str or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Invalid control-lab reference')
    return value


def build(investigation_id, evidence_refs, policy, change, robustness, model_recommendation,
          *, patch=None, unresolved_risks=(), rubric=None) -> dict:
    policy = validate_policy(policy)
    robustness = validate_robustness(robustness)
    _text(investigation_id, 200)
    if type(evidence_refs) not in (list, tuple) or not evidence_refs or len(evidence_refs) > 128:
        raise ValueError('Public evidence references required')
    for ref in evidence_refs:
        _sha(ref)
    if change is not None:
        if type(change) is not dict or set(change) != {'parameter', 'value', 'rationale', 'evidence_refs', 'expected_effect'}:
            raise ValueError('Validated proposal required')
    if robustness['decision'] == 'accept' and change is None:
        raise ValueError('Accepted recommendation requires an approved change')
    if model_recommendation is not None:
        if type(model_recommendation) is not dict or set(model_recommendation) != {'recommendation', 'rationale'}:
            raise ValueError('Invalid model recommendation')
        if model_recommendation['recommendation'] not in ('accept', 'reject', 'further_testing'):
            raise ValueError('Unsupported model recommendation')
        _text(model_recommendation['rationale'], 1000)
    differences = {}
    if change is not None:
        name, value = change['parameter'], change['value']
        if name not in TUNABLE:
            raise ValueError('Unsupported approved difference')
        baseline = policy['parameters'][name]['value']
        if value == baseline:
            raise ValueError('A no-op change is not an approved difference')
        differences[name] = {'baseline': baseline, 'candidate': float(value),
                             'unit': policy['parameters'][name]['unit']}
    risks = list(unresolved_risks) or ['No real-world safety certification; simulation-only evidence.']
    for risk in risks:
        _text(risk, 500)
    if robustness['decision'] == 'reject':
        risks.append('Candidate was rejected by the predeclared acceptance rule; no change is recommended.')
    if change is not None:
        risks.append('A tracking-metric improvement does not repair a physical fault such as a degraded thruster.')
    patch_record = {'status': 'not_attempted', 'diff': None, 'certified': False,
                    'sandbox': None, 'checks': [], 'notes': ['Source-patching is a separate, optional milestone.']}
    if patch is not None:
        if type(patch) is not dict or patch.get('status') not in PATCH_STATES:
            raise ValueError('Invalid patch record')
        patch_record = {'status': patch['status'], 'diff': patch.get('diff'), 'certified': bool(patch.get('certified', False)),
                        'sandbox': patch.get('sandbox'), 'checks': list(patch.get('checks', [])),
                        'notes': list(patch.get('notes', []))}
        if patch_record['diff'] is not None:
            _text(patch_record['diff'], 20000)
        if patch_record['status'] == 'executed' and patch_record['certified'] is not True:
            raise ValueError('Executed patch requires a certified runner')
    body = {
        'schema_version': SCHEMA,
        'investigation_id': investigation_id,
        'created_from': 'nautilus.control-lab.v1',
        'evidence_refs': list(evidence_refs),
        'controller': {**identity(policy),
                       'baseline_configuration': {name: item['value'] for name, item in policy['parameters'].items()}},
        'proposal': None if change is None else dict(change),
        'approved_differences': differences,
        'evaluation_conditions': {
            'suite_id': robustness['suite_id'], 'suite_sha256': robustness['suite_sha256'],
            'cases': list(robustness['suite']), 'matched_conditions': dict(robustness['conditions']),
            'budget': dict(robustness['budget']), 'acceptance_rule': dict(robustness['acceptance']),
            'rubric': rubric,
        },
        'baseline': {'aggregate': {name: values['baseline'] for name, values in robustness['aggregate'].items()}},
        'candidate': {'aggregate': {name: values['candidate'] for name, values in robustness['aggregate'].items()}},
        'robustness': {'cases': robustness['cases'], 'per_scenario': robustness['per_scenario'],
                       'gates': robustness['gates'], 'decision': robustness['decision'],
                       'decision_reasons': robustness['decision_reasons'], 'failures': robustness['failures'],
                       'limitations': robustness['limitations']},
        'recommendation': {'decision': robustness['decision'],
                           'reasons': list(robustness['decision_reasons']),
                           'model_recommendation': model_recommendation,
                           'agreement': None if model_recommendation is None else
                           model_recommendation['recommendation'] == ('accept' if robustness['decision'] == 'accept' else 'reject'),
                           'authority': 'Host rule governs the artifact; a model recommendation cannot approve a change.'},
        'unresolved_risks': risks,
        'human_review': {'status': HUMAN_REVIEW, 'performed': False, 'checklist': list(CHECKLIST)},
        'patch': patch_record,
        'limitations': list(robustness['limitations']) + ['Human review is required before any deployment decision.'],
        'scope': SCOPE,
    }
    return validate({**body, 'artifact_hash': fingerprint(body)})


def validate(value) -> dict:
    if type(value) is not dict:
        raise ValueError('Control-lab artifact object required')
    expected = {'schema_version', 'investigation_id', 'created_from', 'evidence_refs', 'controller', 'proposal',
                'approved_differences', 'evaluation_conditions', 'baseline', 'candidate', 'robustness',
                'recommendation', 'unresolved_risks', 'human_review', 'patch', 'limitations', 'scope',
                'artifact_hash'}
    if set(value) != expected or value['schema_version'] != SCHEMA:
        raise ValueError('Unsupported control-lab artifact')
    _text(value['investigation_id'], 200)
    _text(value['created_from'], 100)
    if value['scope'] != SCOPE:
        raise ValueError('Scope wording is fixed: a recommendation is not a deployed repair')
    for ref in value['evidence_refs']:
        _sha(ref)
    controller = value['controller']
    if type(controller) is not dict or set(controller) != {'policy_id', 'implementation_version', 'source_sha256',
                                                           'policy_hash', 'configuration_id', 'baseline_configuration'}:
        raise ValueError('Invalid controller identity')
    _sha(controller['source_sha256']); _sha(controller['policy_hash']); _sha(controller['configuration_id'])
    if type(controller['baseline_configuration']) is not dict or set(controller['baseline_configuration']) != set(PARAMETERS):
        raise ValueError('Invalid baseline configuration')
    for name, (unit, low, high) in PARAMETERS.items():
        number = controller['baseline_configuration'][name]
        if type(number) not in (int, float) or not math.isfinite(number) or not low <= number <= high:
            raise ValueError('Invalid baseline configuration')
    differences = value['approved_differences']
    if type(differences) is not dict or len(differences) > 1:
        raise ValueError('One approved difference maximum')
    for name, change in differences.items():
        if name not in TUNABLE or type(change) is not dict or set(change) != {'baseline', 'candidate', 'unit'}:
            raise ValueError('Invalid approved difference')
        if change['unit'] != PARAMETERS[name][0] or change['baseline'] != controller['baseline_configuration'][name]:
            raise ValueError('Approved difference does not match the baseline')
        low, high = PARAMETERS[name][1:3]
        if type(change['candidate']) not in (int, float) or not math.isfinite(change['candidate']) or not low <= change['candidate'] <= high:
            raise ValueError('Approved difference outside bounds')
        if change['candidate'] == change['baseline']:
            raise ValueError('No-op difference recorded')
    proposal = value['proposal']
    if differences:
        if type(proposal) is not dict or set(proposal) != {'parameter', 'value', 'rationale', 'evidence_refs', 'expected_effect'}:
            raise ValueError('Approved difference requires a validated proposal')
        name = next(iter(differences))
        if proposal['parameter'] != name or proposal['value'] != differences[name]['candidate']:
            raise ValueError('Proposal differs from approved difference')
        for ref in proposal['evidence_refs']:
            if ref not in value['evidence_refs']:
                raise ValueError('Proposal evidence reference is not public')
    elif proposal is not None:
        raise ValueError('Unexecuted proposal cannot carry a difference')
    robustness = value['robustness']
    if type(robustness) is not dict or set(robustness) != {'cases', 'per_scenario', 'gates', 'decision',
                                                           'decision_reasons', 'failures', 'limitations'}:
        raise ValueError('Invalid robustness record')
    if robustness['decision'] not in ('accept', 'reject'):
        raise ValueError('Invalid robustness decision')
    if robustness['decision'] == 'accept' and not differences:
        raise ValueError('Accepted recommendation requires an approved change')
    recommendation = value['recommendation']
    if type(recommendation) is not dict or set(recommendation) != {'decision', 'reasons', 'model_recommendation', 'agreement', 'authority'}:
        raise ValueError('Invalid recommendation')
    if recommendation['decision'] != robustness['decision']:
        raise ValueError('Recommendation must follow the host rule')
    if recommendation['authority'] != 'Host rule governs the artifact; a model recommendation cannot approve a change.':
        raise ValueError('Recommendation authority wording changed')
    human = value['human_review']
    if type(human) is not dict or set(human) != {'status', 'performed', 'checklist'}:
        raise ValueError('Invalid human review record')
    if human['status'] != HUMAN_REVIEW or human['performed'] is not False or human['checklist'] != list(CHECKLIST):
        raise ValueError('Human review must remain required and unperformed')
    patch = value['patch']
    if type(patch) is not dict or set(patch) != {'status', 'diff', 'certified', 'sandbox', 'checks', 'notes'}:
        raise ValueError('Invalid patch record')
    if patch['status'] not in PATCH_STATES:
        raise ValueError('Invalid patch state')
    if patch['status'] == 'executed' and patch['certified'] is not True:
        raise ValueError('Executed patch requires a certified runner')
    if type(value['limitations']) is not list or not value['limitations']:
        raise ValueError('Limitations required')
    for item in value['limitations']:
        _text(item, 500)
    if type(value['unresolved_risks']) is not list or not value['unresolved_risks']:
        raise ValueError('Unresolved risks required')
    for risk in value['unresolved_risks']:
        _text(risk, 500)
    _sha(value['artifact_hash'])
    if fingerprint({k: v for k, v in value.items() if k != 'artifact_hash'}) != value['artifact_hash']:
        raise ValueError('Control-lab artifact hash mismatch')
    return deepcopy(value)


def configuration_diff(artifact) -> dict:
    artifact = validate(artifact)
    return {'schema_version': DIFF_SCHEMA, 'investigation_id': artifact['investigation_id'],
            'controller': {'policy_id': artifact['controller']['policy_id'],
                           'source_sha256': artifact['controller']['source_sha256'],
                           'policy_hash': artifact['controller']['policy_hash']},
            'baseline_configuration': dict(artifact['controller']['baseline_configuration']),
            'approved_differences': deepcopy(artifact['approved_differences']),
            'decision': artifact['recommendation']['decision'],
            'human_review': artifact['human_review']['status'],
            'artifact_hash': artifact['artifact_hash'],
            'scope': 'Review artifact only; applying it is a separate human decision. Not a deployed repair.'}


def export_artifact(artifact, directory) -> dict:
    """Write the recommendation and its diff outside the source tree."""
    artifact = validate(artifact)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    files = {'control-lab.json': artifact, 'configuration-diff.json': configuration_diff(artifact)}
    written = {}
    for name, body in files.items():
        path = directory / name
        text = json.dumps(body, indent=2, sort_keys=True) + '\n'
        path.write_text(text)
        written[name] = {'path': str(path), 'sha256': hashlib.sha256(text.encode()).hexdigest()}
    return {'schema_version': 'nautilus.control-lab-export.v1', 'files': written,
            'artifact_hash': artifact['artifact_hash'],
            'scope': 'Exported for review only; nothing is deployed, published or applied.'}
