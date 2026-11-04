"""Control Policy Studio: IR, interpreter, source compiler, paired evaluation, Muse loop, API."""
import copy
import json
import math
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from nautilus.policy_ir import (MAX_DEPTH, MAX_NODES, PARAM_LIMITS, SCHEMA, Context, PolicyError,
                                baseline_policy, evaluate, validate)
from nautilus.policy_runtime import PolicyController, params_for
from nautilus.policy_source import from_source, to_source
from nautilus.simulator import Controller, Vehicle, command, simulate
from nautilus.studio import cases, outcome, paired_trial, policy_fingerprint, robustness
from nautilus.studio_muse import (Budget, MockMuse, Session, ToolError, call, live_available,
                                  run_session)


def ctx(y=0.0, heading=0.0, rate=0.0, integral=0.0):
    return Context(y, heading, rate, 7.0, 0.72, 13.0, 45.0, 0.32, integral, 0.5, 0.0)


# ---------------------------------------------------------------- schema / IR
def test_baseline_is_valid_and_deterministic():
    policy = baseline_policy()
    assert validate(policy) is policy
    assert policy['schema'] == SCHEMA
    assert evaluate(policy, ctx(1.0, 0.1, 0.05)) == evaluate(policy, ctx(1.0, 0.1, 0.05))


def test_baseline_ir_reproduces_simulator_control_law_exactly():
    policy, vehicle, controller = baseline_policy(), Vehicle(), Controller()
    for y, heading, rate in [(0.0, 0.0, 0.0), (1.0, 0.2, -0.1), (-2.5, 0.6, 0.4), (3.0, -0.7, -0.5)]:
        expected = command(y, heading, rate, vehicle, controller)
        got = evaluate(policy, ctx(y, heading, rate))
        assert got == pytest.approx(expected[:2], abs=1e-12)


def test_baseline_ir_drives_identical_simulation_trajectory():
    plain = simulate()
    policy = simulate(policy=PolicyController(baseline_policy(), 0.05))
    assert len(plain.truth) == len(policy.truth) > 100
    for left, right in zip(plain.truth, policy.truth):
        assert left['y_m'] == right['y_m']
        assert left['heading_rad'] == right['heading_rad']


def test_unknown_schema_and_fields_rejected():
    policy = baseline_policy()
    with pytest.raises(PolicyError):
        validate({**policy, 'schema': 'other'})
    with pytest.raises(PolicyError):
        validate({**policy, 'extra': 1})


@pytest.mark.parametrize('params', [{'heading_kp': -1}, {'heading_kp': 1e9}, {'integral_ki': 'high'},
                                    {'unknown_gain': 1.0}])
def test_parameters_outside_declared_bounds_rejected(params):
    policy = copy.deepcopy(baseline_policy())
    policy['params'].update(params)
    with pytest.raises(PolicyError):
        validate(policy)


def test_node_and_depth_limits_enforced():
    policy = copy.deepcopy(baseline_policy())
    node = {'op': 'add', 'args': [1.0, 1.0]}
    for _ in range(MAX_NODES):
        node = {'op': 'add', 'args': [node, 1.0]}
    policy['port'] = node
    with pytest.raises(PolicyError):
        validate(policy)
    deep = 'y_m'
    policy = copy.deepcopy(baseline_policy())
    node = {'op': 'add', 'args': [1.0, 1.0]}
    for _ in range(MAX_DEPTH + 2):
        node = {'op': 'neg', 'args': [node]}
    policy['starboard'] = node
    with pytest.raises(PolicyError):
        validate(policy)


def test_interpreter_forbids_non_finite_and_division_by_zero():
    policy = copy.deepcopy(baseline_policy())
    policy['port'] = {'op': 'div', 'args': [1.0, 0.0]}
    validate(policy)
    with pytest.raises(PolicyError):
        evaluate(policy, ctx())
    policy['port'] = {'op': 'mul', 'args': [1e308, 1e308]}
    with pytest.raises(PolicyError):
        evaluate(policy, ctx())


def test_evaluator_cannot_reference_hidden_state():
    policy = copy.deepcopy(baseline_policy())
    for name in ('state', 'truth', 'plant', 'faults', 'current_y', 'sensor_y_std_m'):
        policy['port'] = name
        with pytest.raises(PolicyError):
            validate(policy)


def test_outputs_are_clipped_to_actuator_limits():
    policy = copy.deepcopy(baseline_policy())
    policy['port'] = {'op': 'mul', 'args': [1e6, 1e6]}  # finite, huge
    port, starboard = evaluate(policy, ctx())
    assert port == 45.0 and starboard == pytest.approx(13.0, abs=60)


# ------------------------------------------------------------------- source DSL
def test_source_round_trip_is_numerically_identical():
    policy = baseline_policy()
    compiled = from_source(to_source(policy), params=policy['params'])
    for y, heading, rate, integral in [(0.3, 0.1, 0.0, 0.0), (-1.2, 0.4, -0.2, 0.3), (2.0, -0.5, 0.3, 0.5)]:
        assert evaluate(compiled, ctx(y, heading, rate, integral)) == \
               pytest.approx(evaluate(policy, ctx(y, heading, rate, integral)), abs=1e-12)


def test_source_supports_structural_revision():
    source = """
desired = clip(atan2(-y_m, lookahead_m), -max_heading_rad, max_heading_rad)
error = wrap(desired - heading_rad)
moment = heading_kp * error - heading_kd * filtered_yaw_rate - integral_ki * integral_y
port = sat(cruise_thrust_n - moment / (2 * lever_arm_m))
starboard = sat(cruise_thrust_n + moment / (2 * lever_arm_m))
"""
    policy = from_source(source, params={'heading_kp': 39.0, 'heading_kd': 18.0,
                                         'integral_ki': 4.0, 'integral_limit': 1.0})
    assert policy['params']['integral_ki'] == 4.0
    assert evaluate(policy, ctx(1.0, 0.0, 0.0, 0.4)) != evaluate(baseline_policy(), ctx(1.0, 0.0, 0.0, 0.4))


@pytest.mark.parametrize('source', [
    'import os\nport = 1\nstarboard = 1',
    'port = __import__("os")\nstarboard = 1',
    'port = open("f")\nstarboard = 1',
    'port = y_m.__class__\nstarboard = 1',
    'while True:\n    pass',
    'for x in range(3):\n    port = 1',
    'def f():\n    return 1\nport = f()\nstarboard = 1',
    'port = [1, 2]\nstarboard = 1',
    'port = "text"\nstarboard = 1',
    'port = lambda: 1\nstarboard = 1',
    'port = eval("1")\nstarboard = 1',
    'port = y_m if y_m > 0 else 0\nstarboard = 1',
    'port = 1\nstarboard = 1\nport = 2',
    'port = 1',
    'port = 1\nstarboard = 1\ndel port',
    'port = 1;_ = 2\nstarboard = 1',
])
def test_hostile_or_unsupported_source_rejected(source):
    with pytest.raises(PolicyError):
        from_source(source)


def test_source_size_limit():
    with pytest.raises(PolicyError):
        from_source('port = 1\n' + '# ' + 'x' * 5000 + '\nstarboard = 1')


# --------------------------------------------------------------- runtime state
def test_integrator_is_bounded_and_frozen_while_saturated():
    policy = copy.deepcopy(baseline_policy())
    policy['params'].update({'integral_ki': 3.0, 'integral_limit': 0.5})
    controller = PolicyController(policy, 0.05)
    vehicle = Vehicle()
    for _ in range(400):
        controller.step(0.3, 0.0, 0.0, vehicle, Controller())
        assert abs(controller.integral_y) <= 0.5 + 1e-12
    assert controller.saturated_steps == 0
    assert controller.integral_y == pytest.approx(0.5)
    frozen = controller.integral_y
    for _ in range(50):
        controller.step(12.0, 0.0, 0.0, vehicle, Controller())
    assert controller.saturated_steps > 0
    assert controller.integral_y == pytest.approx(frozen)
    assert math.isfinite(controller.integral_y)


def test_low_pass_filter_is_bounded_and_deterministic():
    policy = copy.deepcopy(baseline_policy())
    policy['params']['yaw_filter_alpha'] = 0.2
    assert params_for(policy)['yaw_filter_alpha'] == 0.2
    first = PolicyController(policy, 0.05)
    second = PolicyController(policy, 0.05)
    for _ in range(20):
        assert first.step(0.5, 0.1, 0.7, Vehicle(), Controller()) == \
               second.step(0.5, 0.1, 0.7, Vehicle(), Controller())
    bad = copy.deepcopy(policy)
    bad['params']['yaw_filter_alpha'] = 2.0
    with pytest.raises(PolicyError):
        validate(bad)


def test_structural_change_changes_simulated_behavior():
    candidate = copy.deepcopy(baseline_policy())
    candidate['params'].update({'integral_ki': 6.0, 'integral_limit': 1.5})
    base = simulate()
    changed = simulate(policy=PolicyController(candidate, 0.05))
    differences = [abs(a['y_m'] - b['y_m']) for a, b in zip(base.truth, changed.truth)]
    assert max(differences) > 0.01


def test_seeded_simulations_are_reproducible_with_policy():
    candidate = copy.deepcopy(baseline_policy())
    candidate['params']['integral_ki'] = 3.0
    first = simulate(policy=PolicyController(candidate, 0.05))
    second = simulate(policy=PolicyController(candidate, 0.05))
    assert [row['y_m'] for row in first.truth] == [row['y_m'] for row in second.truth]


# ------------------------------------------------------------------ evaluation
@pytest.fixture(scope='module')
def baseline_trial():
    return paired_trial(baseline_policy(), 'development', scenario_ids=set())


def test_split_keeps_iteration_and_reporting_separate():
    development = {case.identifier for case in cases('development')}
    held = {case.identifier for case in cases('held_out')}
    assert development and held
    assert not (development & held)


def test_baseline_versus_itself_is_inconclusive():
    trial = paired_trial(baseline_policy(), 'development',
                         scenario_ids={'nominal', 'current_positive'})
    assert trial['outcome']['label'] == 'Inconclusive'
    assert trial['outcome']['mean_rms_difference_m'] == pytest.approx(0.0)
    for row in trial['rows']:
        assert row['baseline']['rms_cross_track_m'] == pytest.approx(row['candidate']['rms_cross_track_m'])


def test_integral_revision_is_recommended_on_real_runs():
    candidate = copy.deepcopy(baseline_policy())
    candidate['params'].update({'integral_ki': 6.0, 'integral_limit': 1.5})
    trial = paired_trial(candidate, 'development')
    assert trial['outcome']['label'] == 'Recommended'
    assert trial['outcome']['mean_rms_difference_m'] < -0.05
    assert policy_fingerprint(candidate) != policy_fingerprint(baseline_policy())
    assert all(row['candidate']['mission_success'] for row in trial['rows'])


def test_aggregate_gain_with_regression_is_rejected():
    candidate = copy.deepcopy(baseline_policy())
    candidate['params'].update({'integral_ki': 12.0, 'integral_limit': 2.5})
    trial = paired_trial(candidate, 'development')
    assert trial['outcome']['label'] == 'Rejected'
    assert trial['outcome']['mean_rms_difference_m'] < 0
    assert 'no_scenario_rms_regression' in trial['outcome']['failed_gates']


def test_negligible_change_is_inconclusive():
    candidate = copy.deepcopy(baseline_policy())
    candidate['params']['integral_ki'] = 0.02
    trial = paired_trial(candidate, 'development')
    assert trial['outcome']['label'] == 'Inconclusive'


def test_outcome_requires_improvement_and_all_gates():
    gates = [{'id': 'mean_rms_improvement', 'passed': True}, {'id': 'no_effort_blowup', 'passed': True}]
    decision = {'decision': 'accept', 'gates': gates,
                'aggregate': {'mean_rms_cross_track_m': {'difference': -0.2}}}
    assert outcome(decision, [])['label'] == 'Recommended'
    regressed = {'decision': 'reject',
                 'gates': gates + [{'id': 'no_scenario_rms_regression', 'passed': False}],
                 'aggregate': {'mean_rms_cross_track_m': {'difference': -0.2}}}
    rejected = outcome(regressed, [])
    assert rejected['label'] == 'Rejected'
    assert 'no_scenario_rms_regression' in rejected['failed_gates']
    marginal = {'decision': 'reject', 'gates': [{'id': 'mean_rms_improvement', 'passed': False}],
                'aggregate': {'mean_rms_cross_track_m': {'difference': 0.0}}}
    assert outcome(marginal, [])['label'] == 'Inconclusive'


def test_robustness_uses_held_out_split_only():
    report = robustness(baseline_policy())
    assert report['part'] == 'held_out'
    assert {row['scenario_id'] for row in report['rows']} == {case.identifier for case in cases('held_out')}


# ------------------------------------------------------------------ Muse loop
def test_mock_session_engineers_a_controller_end_to_end():
    run = run_session()
    assert run['stopped'] is None
    assert run['final']['decision'] == 'recommend'
    tools = [step['tool'] for step in run['transcript']]
    for required in ('inspect_controller', 'inspect_diagnosis_evidence', 'propose_controller_revision',
                     'validate_controller', 'execute_controller_trial', 'evaluate_policy_robustness',
                     'finalize_controller_recommendation'):
        assert required in tools
    assert run['results']['integral-ki-6']['outcome']['label'] == 'Recommended'
    assert run['provider_calls'] == 0 and run['mock'] is True and run['live_available'] is False


def test_mock_session_revises_after_rejection():
    provider = MockMuse(first_params={'integral_ki': 12.0, 'integral_limit': 2.5},
                        second_params={'integral_ki': 6.0, 'integral_limit': 1.5})
    run = run_session(provider=provider)
    tools = [step['tool'] for step in run['transcript']]
    assert tools.count('propose_controller_revision') == 2
    assert run['results']['integral-ki-6']['outcome']['label'] == 'Rejected'
    assert run['results']['integral-ki-3']['outcome']['label'] == 'Recommended'
    assert run['final']['decision'] == 'recommend'


def test_session_abstains_when_evidence_is_inconclusive():
    provider = MockMuse(first_params={'integral_ki': 0.02}, second_params={'integral_ki': 0.02})
    run = run_session(provider=provider)
    assert run['final']['decision'] == 'abstain'


def test_budget_limits_stop_the_loop():
    run = run_session(budget=Budget(max_requests=2))
    assert run['stopped'] == 'model request budget exhausted'
    assert run['final'] is None
    succeeded = [step for step in run['transcript'] if 'result' in step]
    assert len(succeeded) == 2
    assert run['transcript'][-1]['tool'] == 'propose_controller_revision'
    assert 'budget' in run['transcript'][-1]['error']


def test_recommendation_requires_a_recommended_trial():
    session = Session()
    with pytest.raises(ToolError):
        session.finalize_controller_recommendation('recommend', 'no evidence', 'missing')


def test_tool_schema_rejects_unknown_tools_and_arguments():
    with pytest.raises(ToolError):
        call(Session(), 'execute_arbitrary_code', {})
    with pytest.raises(ToolError):
        call(Session(), 'inspect_controller', {'path': '/etc/passwd'})
    with pytest.raises(ToolError):
        call(Session(), 'finalize_controller_recommendation', {'decision': 'deploy'})
    with pytest.raises(ToolError):
        call(Session(), 'finalize_controller_recommendation', {'decision': 'abstain'})


def test_execution_requires_prior_validation():
    session = Session()
    session.inspect_diagnosis_evidence()
    session.propose_controller_revision('c1', 'test', params={'integral_ki': 1.0})
    with pytest.raises(ToolError):
        session.execute_controller_trial('c1')


def test_candidate_budget_is_enforced():
    session = Session()
    session.inspect_diagnosis_evidence()
    for index in range(3):
        session.propose_controller_revision(f'c{index}', 'test', params={'integral_ki': 1.0})
    with pytest.raises(ToolError):
        session.propose_controller_revision('c9', 'test', params={'integral_ki': 1.0})


def test_live_provider_disabled():
    assert live_available() is False


# ---------------------------------------------------------------------- API
@pytest.fixture(scope='module')
def studio_api():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'api' / 'v1' / 'studio.py'
    spec = importlib.util.spec_from_file_location('studio_api', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_api_baseline_and_validate(studio_api):
    baseline = studio_api.dispatch({'action': 'baseline'})
    assert baseline['live_muse'] is False
    assert 'port =' in baseline['source']
    good = studio_api.dispatch({'action': 'validate', 'source': baseline['source'],
                                'params': baseline['policy']['params']})
    assert good['valid'] is True
    bad = studio_api.dispatch({'action': 'validate', 'source': 'port = 1'})
    assert bad['valid'] is False


def test_api_rejects_unknown_actions_and_fields(studio_api):
    with pytest.raises(studio_api.RequestError):
        studio_api.dispatch({'action': 'shell', 'command': 'ls'})
    with pytest.raises(studio_api.RequestError):
        studio_api.dispatch({'action': 'trial'})


def test_api_trial_returns_measured_comparison(studio_api):
    payload = studio_api.dispatch({'action': 'trial',
                                   'source': studio_api.dispatch({'action': 'baseline'})['source'],
                                   'params': baseline_policy()['params']})
    assert payload['part'] == 'development'
    assert len(payload['rows']) == 4  # full development split, no partial default
    assert payload['outcome']['label'] == 'Inconclusive'
    for row in payload['rows']:
        for key in ('rms_cross_track_m', 'max_abs_cross_track_m', 'fraction_outside_corridor'):
            assert math.isfinite(row['candidate'][key])
    assert payload['traces']
    assert len(json.dumps(payload)) < 400_000


def test_example_revision_is_recommended_through_the_api(studio_api):
    # The one-click example sends only the integral gains; declared heading gains must persist.
    payload = studio_api.dispatch({'action': 'trial', 'part': 'development',
                                   'source': studio_api.dispatch({'action': 'baseline'})['source'],
                                   'params': {'integral_ki': 6.0, 'integral_limit': 1.5}})
    assert payload['outcome']['label'] == 'Recommended'
    nominal = next(r for r in payload['rows'] if r['scenario_id'] == 'nominal')
    assert round(nominal['candidate']['rms_cross_track_m'], 4) == 0.0114


def test_studio_kill_switch_defaults_off_and_never_enables_live(monkeypatch):
    from nautilus import studio_muse
    monkeypatch.delenv("NAUTILUS_MUSE_ENABLED", raising=False)
    assert studio_muse.muse_enabled() is False
    for value in ("", "false", "1", "yes"):
        monkeypatch.setenv("NAUTILUS_MUSE_ENABLED", value)
        assert studio_muse.muse_enabled() is False
    monkeypatch.setenv("NAUTILUS_MUSE_ENABLED", "true")
    assert studio_muse.muse_enabled() is True
    # Live Studio provider is not implemented, so it stays unavailable even when enabled.
    assert studio_muse.live_available() is False


def test_api_muse_is_mock_only(studio_api):
    payload = studio_api.dispatch({'action': 'muse'})
    assert payload['mock'] is True and payload['provider_calls'] == 0
    assert payload['live_available'] is False
    assert payload['final']['decision'] in ('recommend', 'reject', 'abstain')


def test_api_rejects_unknown_scenarios(studio_api):
    with pytest.raises(studio_api.RequestError):
        studio_api.dispatch({'action': 'trial', 'policy': baseline_policy(),
                             'scenarios': ['held_out_case_that_does_not_exist']})


# ------------------------------------------------------------ HTTP integration
def _serve(handler, root=''):
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f'http://127.0.0.1:{httpd.server_address[1]}{root}'


def _post(url, body=None, raw=None, timeout=120):
    data = raw if raw is not None else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, method='POST',
                                     headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


@pytest.fixture(scope='module')
def hosted_url(studio_api):
    httpd, url = _serve(studio_api.handler, '/api/v1/studio')
    try:
        yield url
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_http_baseline_needs_no_credential(hosted_url, monkeypatch):
    monkeypatch.delenv('MODEL_API_KEY', raising=False)
    monkeypatch.delenv('NAUTILUS_DEMO_TOKEN', raising=False)
    status, body = _post(hosted_url, {'action': 'baseline'})
    assert status == 200
    assert body['live_muse'] is False
    recompiled = from_source(body['source'], params=body['policy']['params'],
                             name=body['policy']['name'])
    assert recompiled == body['policy'], 'source and IR answer the same document over the wire'
    assert validate(recompiled) == recompiled


def test_http_trial_returns_the_library_numbers(hosted_url):
    status, body = _post(hosted_url, {'action': 'trial', 'policy': baseline_policy()})
    assert status == 200
    assert body['part'] == 'development'
    library = paired_trial(baseline_policy(), part='development',
                           scenario_ids=[row['scenario_id'] for row in body['rows']])
    for wired, direct in zip(body['rows'], library['rows']):
        assert wired['scenario_id'] == direct['scenario_id']
        for side in ('baseline', 'candidate'):
            for key in ('rms_cross_track_m', 'max_abs_cross_track_m', 'fraction_outside_corridor'):
                assert wired[side][key] == pytest.approx(direct[side][key], rel=0, abs=1e-12)
    assert body['outcome']['label'] == 'Inconclusive'
    series = [values for trace in body['traces'].values() for values in trace.values()]
    assert series and all(math.isfinite(point) for values in series for point in values)
    assert all(len(values) <= 120 for values in series), 'traces stay inside the response budget'


def test_http_hostile_source_is_422(hosted_url):
    status, body = _post(hosted_url, {'action': 'trial', 'source': 'import os\nport = 1'})
    assert status == 422
    assert 'assignment' in body['error'].lower(), 'the compiler must name the unsupported construct'


def test_http_rejects_malformed_and_oversized_bodies(hosted_url):
    status, body = _post(hosted_url, raw=b'{oops')
    assert status == 400 and body['error'] == 'Invalid JSON'
    status, _ = _post(hosted_url, raw=json.dumps({'action': 'baseline',
                                                  'pad': 'x' * 20000}).encode())
    assert status == 400
    status, body = _post(hosted_url, raw=b'',)
    assert status == 400


def test_dev_server_shares_the_hosted_dispatch(hosted_url):
    from nautilus_api.server import Handler
    httpd, dev_url = _serve(Handler, '/api/v1/studio')
    try:
        hosted = _post(hosted_url, {'action': 'validate', 'source': 'port = 1'})
        local = _post(dev_url, {'action': 'validate', 'source': 'port = 1'})
        assert local == hosted
        status, body = _post(dev_url, {'action': 'baseline'})
        assert status == 200 and body['policy']['schema'] == SCHEMA
        status, _ = _post(dev_url, {'action': 'delete_everything'})
        assert status == 400
    finally:
        httpd.shutdown()
        httpd.server_close()



def test_from_source_keeps_declared_gains_when_overriding_only_some_params():
    # The Studio's example sends only the integral gains. The heading gains declared in the
    # readable source header must survive, or the controller loses its heading law.
    from nautilus.policy_ir import baseline_policy
    source = to_source(baseline_policy())
    compiled = from_source(source, params={'integral_ki': 6.0, 'integral_limit': 1.5})
    assert compiled['params']['heading_kp'] == 39.0
    assert compiled['params']['heading_kd'] == 18.0
    assert compiled['params']['integral_ki'] == 6.0
    assert compiled['params']['integral_limit'] == 1.5
