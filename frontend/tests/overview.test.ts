import test from 'node:test';
import assert from 'node:assert/strict';
import {overviewMarkup} from '../src/overview.ts';
import {initialSession, recordExperiment, type Session} from '../src/session.ts';

const base = {apiEnabled: true, recordId: null, recordSource: null};

function withRun(): Session {
  return recordExperiment(initialSession(), {
    id: 'sim-1a2b3c4d', kind: 'simulation', request: {scenario: {current_y: 1, port_efficiency: 1, starboard_efficiency: 1, heading_bias_rad: 0}, seed: 42},
    serverId: null, diagnosis: 'single_cause', samples: 600, durationS: 30, peakM: 1.9862, rmsM: 0.0114, finishedAt: '2026-01-01T00:00:00Z',
  });
}

test('an empty session offers the free example and admits there are no results yet', () => {
  const markup = overviewMarkup(initialSession(), base);
  assert.match(markup, /id="start-example"/);
  assert.doesNotMatch(markup, /id="start-example" disabled/);
  assert.match(markup, /No runs yet in this browser session/);
  assert.match(markup, /seed 42 · no model call/);
  assert.doesNotMatch(markup, /\d+\.\d+ m<\/b> · n\/a/);
});

test('session status comes from the recorded run, with its identifier and measured values', () => {
  const markup = overviewMarkup(withRun(), base);
  assert.match(markup, /sim-1a2b3c4d/);
  assert.match(markup, /0\.011 m/);
  assert.match(markup, /1\.986 m/);
  assert.match(markup, /single cause/);
  assert.match(markup, /<li class="done"><small>01<\/small>/);
  assert.match(markup, /<li class="next"><small>02<\/small>/);
  assert.equal((markup.match(/<li [^>]*><small>0[1-5]<\/small>/g) ?? []).length, 5);
  assert.match(markup, /<small>05<\/small><b>Report<\/b>/);
});

test('the overview indexes all five other destinations without inventing data', () => {
  const markup = overviewMarkup(initialSession(), base);
  assert.equal((markup.match(/class="tool-card/g) ?? []).length, 5);
  assert.match(markup, /data-goto="Simulation Lab"/);
  assert.match(markup, /data-goto="Policy Studio"/);
  assert.match(markup, /data-goto="Dashboards"/);
  assert.match(markup, /data-goto="Experiments"/);
  assert.match(markup, /data-goto="Reports"/);
  assert.match(markup, /not a certified safety case/);
});

test('a loaded export is named with its source and truncated run identifier', () => {
  const markup = overviewMarkup(initialSession(), {...base, recordId: 'inv-0123456789abcdef', recordSource: 'trusted_local_run'});
  assert.match(markup, /inv-01234567/);
  assert.match(markup, /trusted local run/);
  assert.match(markup, /Ledger integrity is verified in the browser/);
});

test('with the API disabled the example is disabled and gated tools say so', () => {
  const markup = overviewMarkup(initialSession(), {...base, apiEnabled: false});
  assert.match(markup, /id="start-example" disabled/);
  assert.match(markup, /API disabled in this build/);
  assert.equal((markup.match(/API disabled in this build/g) ?? []).length, 2);
  assert.doesNotMatch(markup, /data-goto="Simulation Lab"/);
});

test('a running example reports progress and cannot be started twice', () => {
  const markup = overviewMarkup(initialSession(), {...base, exampleBusy: true});
  assert.match(markup, /Starting investigation…/);
  assert.match(markup, /Deterministic investigation running on the server/);
  assert.match(markup, /id="start-example" disabled/);
});

test('an example failure is shown as an alert-style status without claiming success', () => {
  const markup = overviewMarkup(initialSession(), {...base, exampleError: 'Simulation API unreachable'});
  assert.match(markup, /Simulation API unreachable/);
  assert.match(markup, /role="status" aria-live="polite"/);
});


test('overview offers one investigation start and separately labels recorded and 3D paths', () => {
  const markup = overviewMarkup(initialSession(), base);
  assert.equal((markup.match(/id="start-example"/g) ?? []).length, 1);
  assert.match(markup, /Start an Investigation/);
  assert.match(markup, /href="#verified-cases"/);
  assert.match(markup, /href="#recorded-muse"/);
  assert.match(markup, /data-goto="Trajectory"/);
  assert.match(markup, /no bundled 3D example/);
  assert.match(markup, /may disappear after refreshing/);
});

test('a trial is evidence of comparison, never evidence that engineering or robustness is complete', () => {
  const session = {...initialSession(), trials:[{id:'trial', fingerprint:'a'.repeat(64), outcome:'Not recommended', meanRmsDifferenceM:1, scenarios:2, finishedAt:'2026-01-01'}]};
  const markup = overviewMarkup(session, base);
  assert.doesNotMatch(markup, /<li class="done"><small>0[345]<\/small>/);
  assert.match(markup, /Export the latest report/);
});
