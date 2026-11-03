import test from 'node:test';
import assert from 'node:assert/strict';
import {timelineMarkup, lateralSeries} from '../src/simulation-lab.ts';

test('timeline lists ledger events in order with labels and short hashes', () => {
  const html = timelineMarkup([
    {index: 0, type: 'initial_observation', diagnosis: {kind: 'ambiguous'}, event_hash: 'abcdef0123456789'},
    {index: 1, type: 'stopped', reason: 'identified', tests: 0, event_hash: '999999999999aaaa'},
  ]);
  assert.match(html, /0\. Initial observation/);
  assert.match(html, /1\. Stopped/);
  assert.match(html, /diagnosis ambiguous/);
  assert.match(html, /abcdef012345/);
  assert.doesNotMatch(html, /abcdef0123456789/);
  assert.ok(html.indexOf('0. Initial') < html.indexOf('1. Stopped'));
});

test('timeline escapes server-provided text', () => {
  const html = timelineMarkup([{index: 0, type: 'experiment_error', error: '<img src=x onerror=alert(1)>'}]);
  assert.doesNotMatch(html, /<img/);
  assert.match(html, /&lt;img/);
});

test('lateral series maps time to x and deviation to inverted y within 0..100', () => {
  const s = lateralSeries([{time_s: 0, observed_y_m: -1}, {time_s: 5, observed_y_m: 1}, {time_s: 10, observed_y_m: 0}]);
  assert.equal(s.min, -1);
  assert.equal(s.max, 1);
  assert.equal(s.points, '0.00,100.00 50.00,0.00 100.00,50.00');
});

test('flat lateral series does not divide by zero', () => {
  const s = lateralSeries([{time_s: 0, observed_y_m: 0.2}, {time_s: 1, observed_y_m: 0.2}]);
  assert.doesNotMatch(s.points, /NaN|Infinity/);
});

test('empty lateral series is empty', () => {
  assert.equal(lateralSeries([]).points, '');
});

test('empty ledger shows a clear message', () => {
  assert.match(timelineMarkup([]), /No ledger events recorded/);
});

test('labMarkup renders the configuration panel and hides paid Muse controls when paid execution is off', async () => {
  const {labMarkup, initialLab} = await import('../src/simulation-lab.ts');
  const html = labMarkup(initialLab(), false);
  assert.match(html, /Simulation Configuration/);
  assert.match(html, /Run Simulation/);
  assert.match(html, /Run Investigation/);
  assert.match(html, /Paid execution is disabled/);
  assert.match(html, /name="token"[^>]*disabled/);
  assert.doesNotMatch(html, /<input[^>]*value="[^"]{12,}"[^>]*type="password"/);
});

test('resultMetrics computes peak and RMS cross-track from real observations', async () => {
  const {resultMetrics} = await import('../src/simulation-lab.ts');
  const obs = [0, 1, 2].map(t => ({time_s: t, observed_y_m: t === 1 ? -2 : 0, observed_heading_rad: 0, observed_yaw_rate_radps: 0, port_command_n: 0, starboard_command_n: 0}));
  const html = resultMetrics(obs, {scenario: {current_y: 0.6}, seed: 7});
  assert.match(html, /2\.000 m/);
  assert.match(html, /1\.155 m/);
  assert.match(html, /Lateral current/);
  assert.match(html, /0\.6 m\/s/);
  assert.equal(resultMetrics([]), '');
});

test('validateLabForm reports out-of-range and non-integer seed values', async () => {
  const {validateLabForm} = await import('../src/simulation-lab.ts');
  const base: Record<string, string> = {current_y: '1', port_efficiency: '1', starboard_efficiency: '1', heading_bias_rad: '0', seed: '42'};
  const check = (values: Record<string, string>) => {
    const original = globalThis.FormData;
    (globalThis as {FormData?: unknown}).FormData = class { get(k: string) { return values[k] ?? null; } };
    try { return validateLabForm({} as HTMLFormElement); }
    finally { (globalThis as {FormData?: unknown}).FormData = original; }
  };
  assert.equal(check(base), null);
  assert.match(check({...base, current_y: '9'})!, /between/);
  assert.match(check({...base, seed: '1.5'})!, /integer/);
});
