import test from 'node:test';
import assert from 'node:assert/strict';
import {controllerComparison, dashboardsHeader, experimentsView, faultEvidence, reportsView} from '../src/destinations.ts';
import {initialSession, recordExperiment, recordTrial, type Session} from '../src/session.ts';
import type {LabState} from '../src/simulation-lab.ts';
import type {Trial} from '../src/studio-api.ts';
import type {Investigation} from '../src/records.ts';

const idleLab: LabState = {status: 'idle', message: '', simulation: null, job: null};
const sessionWithRun = (): Session => recordExperiment(initialSession(), {
  id: 'sim-1a2b3c4d', kind: 'simulation', request: {scenario: {current_y: 1, port_efficiency: 1, starboard_efficiency: 1, heading_bias_rad: 0}, seed: 42},
  serverId: null, diagnosis: 'single_cause', samples: 600, durationS: 30, peakM: 1.9862, rmsM: 0.0114, finishedAt: '2026-01-01T00:00:00Z',
});

const record = {file: {run_id: 'inv-0123456789abcdef', source_kind: 'trusted_local_run'}, events: [{type: 'observation'}, {type: 'fit'}]} as unknown as Investigation;

test('Experiments separates session-only results from a loaded file and fabricates nothing', () => {
  const empty = experimentsView(initialSession(), null);
  assert.match(empty, /SESSION ONLY/);
  assert.match(empty, /No experiments in this session/);
  assert.match(empty, /nothing from this session is stored on a server/i);
  assert.doesNotMatch(empty, /\d+\.\d{3} m/);

  const loaded = experimentsView(initialSession(), record);
  assert.match(loaded, /inv-01234567/);
  assert.match(loaded, /verified ledger events/);
  assert.match(loaded, /not a server archive/);
  assert.match(loaded, /SHA-256 chain verified on load/);
});

test('a session run appears with its parameters, run id and session-only warning', () => {
  const markup = experimentsView(sessionWithRun(), null);
  assert.match(markup, /sim-1a2b3c4d/);
  assert.match(markup, /1\.000 m\/s/);
  assert.match(markup, /seed 42/);
  assert.match(markup, /0\.011/);
  assert.match(markup, /Session only/);
});

test('Reports disables every export until its source data exists', () => {
  const empty = reportsView(initialSession(), {recordLoaded: false, hasEngineeringReport: false});
  assert.equal((empty.match(/id="report-download-[a-z-]+" disabled/g) ?? []).length, 5);
  assert.match(empty, /Each file is generated from data already in this browser/);
  assert.match(empty, /no formal stability or safety guarantee/);

  const ready = reportsView(recordTrial(sessionWithRun(), {id: 'trial-1', fingerprint: 'abcdef0123456789', outcome: 'recommended', meanRmsDifferenceM: -0.0002, scenarios: 4, finishedAt: '2026-01-01T00:10:00Z'}), {recordLoaded: true, hasEngineeringReport: true});
  assert.doesNotMatch(ready, /id="report-download-report" disabled/);
  assert.doesNotMatch(ready, /id="report-download-engineering" disabled/);
  assert.doesNotMatch(ready, /id="report-download-session" disabled/);
  assert.match(ready, /1 experiment\(s\) and 1 paired trial\(s\)/);
});

test('fault evidence stays empty until the server returns an investigation', () => {
  const markup = faultEvidence(idleLab);
  assert.match(markup, /NO INVESTIGATION YET/);
  assert.match(markup, /never infer a cause from the plots alone/);
  assert.doesNotMatch(markup, /selected/i);
});

test('server fault evidence keeps reasons, competing hypotheses and the not-proven caveat', () => {
  const lab = {status: 'done', message: '', simulation: null, job: {id: 'job-0123456789abcdef', status: 'done', request: {scenario: {}, seed: 42}, result: {observations: [], investigation: {outcome: {kind: 'single_cause', selected: 'current_bias', competitive: ['thruster_loss'], reasons: ['lateral drift persisted with healthy thrusters']}, ledger: [], tests: 3, time_s: 0.42}}}} as unknown as LabState;
  const markup = faultEvidence(lab);
  assert.match(markup, /current_bias/);
  assert.match(markup, /thruster_loss/);
  assert.match(markup, /lateral drift persisted with healthy thrusters/);
  assert.match(markup, /job-01234567/);
  assert.match(markup, /3 tests/);
  assert.match(markup, /not a proven cause/);
});

test('controller comparison points at Policy Studio before any trial exists', () => {
  const markup = controllerComparison(initialSession(), null);
  assert.match(markup, /NO TRIAL YET/);
  assert.match(markup, /free paired trials on identical scenarios, seeds and noise streams/);
  assert.match(markup, /data-goto="Policy Studio"/);
  assert.doesNotMatch(markup, /improved|verified fix/i);
});

test('dashboards name the runs in play and never invent a diagnosis', () => {
  const empty = dashboardsHeader(initialSession(), null, idleLab, null);
  assert.match(empty, /LAST RUN ID<\/small><b class="hash">n\/a/);
  assert.match(empty, /no investigation yet/);
  assert.match(empty, /not run/);
  const header = dashboardsHeader(sessionWithRun(), record, idleLab, {outcome: {label: 'Recommended'}} as unknown as Trial);
  assert.match(header, /sim-1a2b3c4d/);
  assert.match(header, /inv-01234567/);
  assert.match(header, /Recommended/);
});
