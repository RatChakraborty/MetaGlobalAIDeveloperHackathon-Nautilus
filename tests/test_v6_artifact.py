import json

import pytest

from nautilus.simulator import Controller
from nautilus.v6 import build_artifact, build_policy, build_suite, evaluate_suite, validate_artifact
from nautilus.v6.artifact import CHECKLIST, SCOPE, configuration_diff, export_artifact

REF = 'a' * 64


def robustness(value=3.):
    suite = build_suite(duration_s=12., cable_length_m=8.,
                        specs=(('current_positive', {'current_y': .45}, {}, 9301),
                               ('nominal', {}, {}, 9302)))
    return evaluate_suite(Controller(), {'lookahead_m': value}, suite=suite)


def change(value=3.):
    return {'parameter': 'lookahead_m', 'value': value, 'rationale': 'Recorded excursions under lateral current.',
            'evidence_refs': [REF], 'expected_effect': 'Lower mean cross-track RMS.'}


def artifact(**overrides):
    result = robustness()
    options = {'investigation_id': 'inv-1', 'evidence_refs': [REF], 'policy': build_policy(Controller()),
               'change': change() if result['decision'] == 'accept' else None, 'robustness': result,
               'model_recommendation': {'recommendation': 'accept' if result['decision'] == 'accept' else 'reject',
                                        'rationale': 'Measured development suite only.'}}
    options.update(overrides)
    return build_artifact(options.pop('investigation_id'), options.pop('evidence_refs'), options.pop('policy'),
                          options.pop('change'), options.pop('robustness'), options.pop('model_recommendation'),
                          **options)


def test_recommendation_package_contains_every_required_field():
    value = artifact()
    validate_artifact(value)
    assert value['robustness']['decision'] == 'accept'
    assert value['approved_differences'] == {'lookahead_m': {'baseline': 7., 'candidate': 3., 'unit': 'm'}}
    assert value['scope'] == SCOPE and 'not a deployed repair' in value['scope']
    assert value['controller']['baseline_configuration']['lookahead_m'] == 7.
    assert value['evaluation_conditions']['matched_conditions']['matched_noise_seed'] is True
    assert value['evaluation_conditions']['acceptance_rule']
    assert 'mean_rms_cross_track_m' in value['baseline']['aggregate']
    assert value['human_review']['checklist'] == list(CHECKLIST)
    assert value['human_review']['performed'] is False
    assert value['recommendation']['authority'].startswith('Host rule governs')
    assert value['patch']['status'] == 'not_attempted'
    assert any('does not repair a physical fault' in risk for risk in value['unresolved_risks'])
    for private in ('"seed"', 'current_y', 'port_efficiency'):
        assert private not in json.dumps(value)


def test_artifact_rejects_tampering_and_unbacked_claims():
    value = artifact()
    with pytest.raises(ValueError, match='hash mismatch'):
        validate_artifact({**value, 'unresolved_risks': ['nothing left']})
    with pytest.raises(ValueError, match='deployed repair'):
        validate_artifact({**value, 'scope': 'Verified repair, ready to deploy.'})
    with pytest.raises(ValueError, match='Human review'):
        validate_artifact({**value, 'human_review': {**value['human_review'], 'performed': True}})
    with pytest.raises(ValueError, match='certified runner'):
        validate_artifact({**value, 'patch': {**value['patch'], 'status': 'executed', 'certified': False}})
    with pytest.raises(ValueError, match='host rule'):
        validate_artifact({**value, 'recommendation': {**value['recommendation'], 'decision': 'accept' if value['robustness']['decision'] == 'reject' else 'reject'}})


def test_accepted_artifact_requires_an_approved_change():
    rejected = robustness(11.)
    with pytest.raises(ValueError):
        build_artifact('inv-1', [REF], build_policy(Controller()), None,
                       {**rejected, 'decision': 'accept', 'decision_reasons': []}, None)


def test_differences_are_exact_and_exported_outside_the_tree(tmp_path):
    value = artifact()
    if value['approved_differences']:
        assert value['approved_differences'] == {'lookahead_m': {'baseline': 7., 'candidate': 3., 'unit': 'm'}}
        assert value['proposal']['parameter'] == 'lookahead_m'
        assert value['proposal']['value'] == 3.
    diff = configuration_diff(value)
    assert diff['schema_version'] == 'nautilus.configuration-diff.v1'
    assert diff['artifact_hash'] == value['artifact_hash']
    assert diff['human_review'] == 'required'
    exported = export_artifact(value, tmp_path / 'review')
    assert set(exported['files']) == {'control-lab.json', 'configuration-diff.json'}
    written = json.loads((tmp_path / 'review' / 'control-lab.json').read_text())
    assert written == value
    assert json.loads((tmp_path / 'review' / 'configuration-diff.json').read_text()) == diff
    for name, record in exported['files'].items():
        assert len(record['sha256']) == 64 and (tmp_path / 'review' / name).exists()


def test_patch_record_is_separate_and_never_certified_by_default():
    value = artifact(patch={'status': 'review_only', 'diff': '--- a/x\n+++ b/x\n', 'certified': False,
                            'sandbox': {'available': False}, 'checks': [], 'notes': ['review only']})
    assert value['patch']['status'] == 'review_only'
    assert value['patch']['certified'] is False
    with pytest.raises(ValueError):
        artifact(patch={'status': 'installed', 'diff': None, 'certified': True})
