import test from 'node:test';
import assert from 'node:assert/strict';
import {engineeringReport, initialStudio, museMarkup, studioMarkup, traceMarkup, trialMarkup} from '../src/studio-view.ts';
import {parseParams, StudioError} from '../src/studio-api.ts';

const trace = {time_s: [0, 1, 2], y_m: [0, -0.5, -0.2], heading_rad: [0, 0, 0], port_command_n: [10, 12, 11], starboard_command_n: [10, 8, 9]};

test('parameters parse only name = number lines', () => {
  assert.deepEqual(parseParams('integral_ki = 6.0\nintegral_limit = 1.5'), {integral_ki: 6, integral_limit: 1.5});
  assert.deepEqual(parseParams(''), {});
  assert.throws(() => parseParams('integral_ki = __import__("os")'), StudioError);
  assert.throws(() => parseParams('integral_ki 6'), StudioError);
});

test('studio markup states what the interpreter supports and stays escaped', () => {
  const html = studioMarkup(initialStudio());
  assert.match(html, /NOT PYTHON/);
  assert.match(html, /Validate/);
  assert.match(html, /Download|Export engineering report/);
  const escaped = studioMarkup({...initialStudio(), source: 'desired = __import__("<script>")'});
  assert.ok(!escaped.includes('<script>'));
  assert.ok(escaped.includes('&lt;script&gt;'));
});

test('trial markup reports every metric and gate from the payload', () => {
  const trial = {
    policy: {params: {integral_ki: 6}},
    source: 'desired = 0.0',
    fingerprint: 'a'.repeat(64),
    part: 'development',
    rows: [{scenario_id: 'nominal', baseline: {rms_cross_track_m: 1.2, max_abs_cross_track_m: 2, fraction_outside_corridor: 0.4, command_saturation_fraction: 0, mission_success: false, effort_proxy_n_s: 900},
            candidate: {rms_cross_track_m: 0.6, max_abs_cross_track_m: 1.4, fraction_outside_corridor: 0.1, command_saturation_fraction: 0, mission_success: true, effort_proxy_n_s: 910}}],
    gates: [{id: 'mean_rms_improvement', passed: true, observed: -0.6, threshold: -0.2}, {id: 'no_effort_blowup', passed: false}],
    outcome: {label: 'Rejected' as const, mean_rms_difference_m: -0.6, failed_gates: ['no_effort_blowup'], rationale: 'rejected on a declared gate'},
    traces: {nominal: trace},
    methodology: {matched: true, note: 'matched seeds', split: 'development'},
  };
  const html = trialMarkup(trial);
  assert.match(html, /Rejected/);
  assert.match(html, /0\.600/);
  assert.match(html, /no_effort_blowup/);
  assert.match(html, /rejected on a declared gate/);
  assert.match(html, /nominal/);
  assert.equal(trialMarkup(null).includes('<table'), false);
});

test('traces draw baseline and candidate with corridor overlays', () => {
  const html = traceMarkup({nominal: trace}, ['y_m', 'port_command_n'], 'cross-track · m', 1.5);
  assert.equal((html.match(/<polyline/g) ?? []).length, 2);
  assert.match(html, /stroke-dasharray/);
  assert.match(html, /cross-track/);
});

test('muse panel is explicit that live execution is disabled', () => {
  const disabled = museMarkup(null);
  assert.match(disabled, /disabled/);
  assert.match(disabled, /no credits are spent/i);
  assert.match(disabled, /free/);
  const session = {final: {decision: 'abstain', rationale: 'evidence does not separate candidates', candidate_id: null, budget: {}},
    stopped: null, transcript: [{tool: 'execute_controller_trial', arguments: {candidate_id: 'integral-ki-6'}, result: {outcome: {label: 'Inconclusive'}}}],
    mock: true, live_available: false as const, model: 'mock-deterministic-v1', provider_calls: 0,
    disclosure: 'mocked provider; real simulator and real evaluation', budget: {requests: 3},
    results: {}, candidates: {}};
  const html = museMarkup(session);
  assert.match(html, /abstain/);
  assert.match(html, /integral-ki-6 → Inconclusive/);
  assert.match(html, /mock-deterministic-v1/);
});

test('engineering report carries decisions, gates and limitations', () => {
  const report = engineeringReport({...initialStudio(), versions: [{label: 'v1', fingerprint: 'b'.repeat(64), outcome: 'Inconclusive'}]});
  assert.equal(report.schema, 'nautilus.policy-engineering-report.v1');
  assert.deepEqual(report.versions, [{label: 'v1', fingerprint: 'b'.repeat(64), outcome: 'Inconclusive'}]);
  assert.ok(Array.isArray(report.limitations));
  assert.match(String((report.limitations as string[]).join(' ')), /never used to select/);
});
