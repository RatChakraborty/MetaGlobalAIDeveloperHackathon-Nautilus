import test from 'node:test';
import assert from 'node:assert/strict';
import {EXAMPLE_PARAMS, engineeringReport, initialStudio, museMarkup, studioDiff, studioMarkup, traceMarkup, trialMarkup} from '../src/studio-view.ts';
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

test('studio offers a one-click example revision that loads the verified integral gains', () => {
  const html = studioMarkup(initialStudio());
  assert.match(html, /data-studio="example"/);
  assert.match(html, /Load example revision/);
  assert.equal(EXAMPLE_PARAMS, 'integral_ki = 6.0\nintegral_limit = 1.5');
  assert.deepEqual(parseParams(EXAMPLE_PARAMS), {integral_ki: 6, integral_limit: 1.5});
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

test('investigation handoff panel labels hypotheses as candidates and escapes text', () => {
  const handoff = {
    schema_version: 'nautilus.studio-handoff.v1' as const,
    reproducibility: {run_id: 'run-<img>', source_kind: 'recorded', ledger_head: 'h', events: 3},
    observations: {episodes: 1, evidence_refs: ['h-obs'], max_abs_observed_y_m: 0.4},
    hypotheses: [{hypothesis: 'thruster_gain_loss', converged: true, parameters: {gain: 0.8},
      weighted_rmse: 0.07, identifiability: {rank: 1, condition: 1e8, qualification: 'weak'},
      evidence_refs: ['h-obs'], status: 'candidate_hypothesis' as const}],
    conclusion: null,
    limitations: ['Hypotheses are candidate explanations, not proven causes.'],
  };
  const html = studioMarkup({...initialStudio(), handoff});
  assert.match(html, /Investigation evidence/);
  assert.match(html, /candidate, not proven/);
  assert.ok(!html.includes('<img>'));
  assert.ok(html.includes('run-&lt;img&gt;'));
  assert.match(studioMarkup(initialStudio()), /No investigation evidence attached/);
});

test('studio diff shows parameter and source changes against the server baseline', () => {
  const baselineSource = 'desired = heading_kp * error\nintegral_term = 0.0';
  const baseline = {policy: {params: {heading_kp: 39, heading_kd: 18, integral_ki: 0}}, source: baselineSource,
    fingerprint: 'b'.repeat(64), supported: {references: [], functions: [], limits: {nodes: 64, depth: 8}}, live_muse: false as const};
  const pristine = {...initialStudio(), baseline, source: baselineSource, params: 'heading_kp = 39\nheading_kd = 18\nintegral_ki = 0'};
  assert.deepEqual(studioDiff(pristine), {params: [], removed: [], added: []});
  assert.match(studioMarkup(pristine), /No changes from the baseline controller yet/);

  const edited = {...pristine, source: 'desired = heading_kp * error\nintegral_term = clamp(integral_ki * error, -1.5, 1.5)', params: EXAMPLE_PARAMS};
  const diff = studioDiff(edited);
  assert.deepEqual(diff.params, [{name: 'integral_ki', from: 0, to: 6}, {name: 'integral_limit', from: null, to: 1.5}]);
  assert.deepEqual(diff.removed, ['integral_term = 0.0']);
  assert.equal(diff.added.length, 1);
  const html = studioMarkup(edited);
  assert.match(html, /Changes from baseline/);
  assert.match(html, /integral_ki/);
  assert.match(html, /integral_term = 0\.0/);
});
