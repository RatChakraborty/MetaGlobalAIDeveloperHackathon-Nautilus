import test from 'node:test';
import assert from 'node:assert/strict';
import {initialSession, recordExperiment, recordTrial, sessionId, summarizeObservations, experimentsMarkup, trialsMarkup} from '../src/session.ts';

const obs = [0, 1, 2].map(i => ({time_s: i, observed_y_m: i - 1, observed_heading_rad: 0, observed_yaw_rate_radps: 0, port_command_n: 0, starboard_command_n: 0}));

test('sessionId is deterministic for the same request and differs otherwise', () => {
  assert.equal(sessionId('sim', {a: 1}), sessionId('sim', {a: 1}));
  assert.notEqual(sessionId('sim', {a: 1}), sessionId('sim', {a: 2}));
});

test('summarizeObservations reports peak, RMS and duration from observed samples only', () => {
  const s = summarizeObservations(obs);
  assert.equal(s.peakM, 1);
  assert.ok(Math.abs(s.rmsM - Math.sqrt(2 / 3)) < 1e-12);
  assert.equal(s.durationS, 2);
  assert.equal(summarizeObservations([]).samples, 0);
});

test('an empty session says it is not persisted', () => {
  assert.match(experimentsMarkup(initialSession()), /No experiments in this session/);
  assert.match(experimentsMarkup(initialSession()), /Session only/);
});

test('recorded experiments and trials appear with their run identifiers', () => {
  let session = recordExperiment(initialSession(), {id: 'sim-1', kind: 'simulation', request: {scenario: {current_y: 1}, seed: 7}, serverId: null, diagnosis: 'current', samples: 3, durationS: 2, peakM: 1, rmsM: 0.8, finishedAt: 't'});
  session = recordTrial(session, {id: 't1', fingerprint: 'abcdef0123456789xyz', outcome: 'Recommended', meanRmsDifferenceM: -0.1, scenarios: 4, finishedAt: 't'});
  assert.match(experimentsMarkup(session), /sim-1/);
  assert.match(trialsMarkup(session), /abcdef0123456789/);
  assert.match(trialsMarkup(session), /Recommended/);
});

test('session escapes markup from identifiers', () => {
  const session = recordExperiment(initialSession(), {id: '<img>', kind: 'investigation', request: {scenario: {}}, serverId: '<b>', diagnosis: null, samples: 0, durationS: 0, peakM: 0, rmsM: 0, finishedAt: 't'});
  assert.doesNotMatch(experimentsMarkup(session), /<img>/);
});
