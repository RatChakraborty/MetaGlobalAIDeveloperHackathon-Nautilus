from dataclasses import replace
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from nautilus.configuration_evaluation import DevelopmentScenario, evaluate_configuration
from nautilus.controller_context import canonical, fingerprint
from nautilus.simulator import Controller, Faults, Mission, simulate


def scenario():
    return DevelopmentScenario('unit-development', faults=Faults(current_y=.2), mission=Mission(duration_s=2., seed=739411))


def exporter():
    spec = importlib.util.spec_from_file_location('controller_export', Path(__file__).parents[1]/'frontend/export_records.py')
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_matched_configuration_repeatability_and_real_metrics():
    s = scenario();a = evaluate_configuration(s, Controller(), {'lookahead_m':3.})
    b = evaluate_configuration(s, Controller(), {'lookahead_m':3.})
    assert a.summary() == b.summary()
    assert a.baseline.result == simulate(s.vehicle,s.faults,Controller(),s.mission,s.plant)
    assert a.candidate.result == simulate(s.vehicle,s.faults,replace(Controller(),lookahead_m=3.),s.mission,s.plant)
    assert a.baseline.result != a.candidate.result
    for run in (a.baseline,a.candidate):
        y = np.array([r['y_m'] for r in run.result.truth]);m = run.metrics
        assert m['rms_cross_track_m'] == pytest.approx(np.sqrt(np.mean(y*y)))
        assert m['max_abs_cross_track_m'] == max(abs(y))
        assert m['outside_corridor_samples'] == sum(abs(y)>s.mission.cable_half_width_m)
        assert m['termination'] == 'duration_cap' and m['completion_time_s'] is None
        assert not m['reached_cable_end']
    assert a.metric_differences['rms_cross_track_m'] == a.candidate.metrics['rms_cross_track_m']-a.baseline.metrics['rms_cross_track_m']
    assert '739411' not in json.dumps(a.summary())
    assert 'current_y' not in json.dumps(a.summary())


@pytest.mark.parametrize('changes',[{}, {'seed':1},{'max_heading_rad':.5},{'heading_kp':float('nan')},{'heading_kd':-1},{'lookahead_m':100},{'cruise_thrust':True},{'heading_kp':float('inf')}])
def test_configuration_change_bounds(changes):
    with pytest.raises(ValueError): evaluate_configuration(scenario(), Controller(), changes)


def test_development_only_and_completion_semantics():
    with pytest.raises(ValueError): evaluate_configuration(replace(scenario(),purpose='held-out'),Controller(),{'heading_kp':40.})
    with pytest.raises(ValueError): evaluate_configuration(replace(scenario(),mission=Mission(duration_s=121)),Controller(),{'heading_kp':40.})
    s = replace(scenario(),mission=Mission(duration_s=4.,cable_length_m=.1,seed=739412))
    a = evaluate_configuration(s,Controller(),{'cruise_thrust':14.})
    assert a.baseline.metrics['termination'] == 'cable_end'
    assert a.baseline.metrics['completion_time_s'] < s.mission.duration_s
    assert a.baseline.metrics['reached_cable_end']


def test_new_export_ledger_and_truth_isolation(tmp_path):
    e = evaluate_configuration(scenario(),Controller(),{'lookahead_m':3.})
    module = exporter();summary = module.export_configuration_evaluation(e,tmp_path)
    for name,run in [('baseline',e.baseline),('candidate',e.candidate)]:
        public = json.loads((tmp_path/f'{name}.public.json').read_text())
        visual = json.loads((tmp_path/f'{name}.visualization.json').read_text())
        assert public['schema_version'] == 'nautilus.public-investigation.v2'
        assert visual['schema_version'] == 'nautilus.visualization-only.v2'
        assert visual['samples'] == [{k:r[k] for k in ('time_s','x_m','y_m','heading_rad')} for r in run.result.truth]
        ledger = []
        for item in public['ledger']:
            body = json.loads(item['body_canonical']);assert module.digest(body) == item['hash']
            ledger.append({**body,'event_hash':item['hash']})
        assert ledger[1]['previous_hash'] == ledger[0]['event_hash']
        assert all(set(r)==set(module.FIELDS) for r in ledger[1]['observations'])
        raw = tmp_path/f'{name}.history.json';raw.write_text(json.dumps({'history':ledger}))
        reexported = module.public_record(raw)
        assert reexported['ledger'] == public['ledger']
        assert summary['records'][name]['observation_ref'] == public['ledger'][1]['hash']
        assert 'current_y' not in json.dumps(public) and 'seed' not in json.dumps(public)
    bad = json.loads(raw.read_text());bad['history'][0]['context_ref']='bad'
    raw.write_text(json.dumps(bad))
    with pytest.raises(ValueError): module.public_record(raw)


def test_export_rejects_mutated_trajectory(tmp_path):
    evaluation = evaluate_configuration(scenario(),Controller(),{'lookahead_m':3.})
    evaluation.baseline.result.truth[0]['y_m'] = 999.
    with pytest.raises(ValueError,match='trajectory changed'):
        exporter().export_configuration_evaluation(evaluation,tmp_path)


@pytest.mark.parametrize('changes',[{'lookahead_m':3.},{'heading_kp':50.},{'heading_kd':30.},{'cruise_thrust':15.}])
def test_each_approved_change_is_applied_to_actual_control(changes):
    s = scenario();evaluation = evaluate_configuration(s,Controller(),changes)
    expected = simulate(s.vehicle,s.faults,replace(Controller(),**changes),s.mission,s.plant)
    assert evaluation.candidate.result == expected
    assert evaluation.candidate.result != evaluation.baseline.result
    for name,value in changes.items():
        assert evaluation.candidate.context['declared_configuration'][name]['value'] == value
