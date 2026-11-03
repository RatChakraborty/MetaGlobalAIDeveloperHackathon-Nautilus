import test from 'node:test';
import assert from 'node:assert/strict';
import {nextStep, STAGES} from '../src/workflow.ts';

const base = {hasRecord: false, inEngineering: false, hasTrialResult: false, labAvailable: true};

test('workflow starts with simulate when a lab is available and no record is open', () => {
  assert.equal(nextStep(base).stage, 'simulate');
});

test('workflow starts with investigate when no lab is available', () => {
  assert.equal(nextStep({...base, labAvailable: false}).stage, 'investigate');
});

test('an open record points to the Policy Studio handoff, not to a proven fix', () => {
  const step = nextStep({...base, hasRecord: true});
  assert.equal(step.stage, 'investigate');
  assert.match(step.text, /Open in Policy Studio/);
  assert.doesNotMatch(step.text, /fix|prove|proven/i);
});

test('a session run without an export points to Policy Studio navigation instead of a handoff', () => {
  const step = nextStep({...base, hasRecord: true, canHandoff: false});
  assert.equal(step.stage, 'investigate');
  assert.match(step.text, /open Policy Studio from the navigation/);
  assert.doesNotMatch(step.text, /Open in Policy Studio/);
});

test('engineering moves to evaluate until a trial exists, then to report', () => {
  assert.equal(nextStep({...base, hasRecord: true, inEngineering: true}).stage, 'evaluate');
  assert.equal(nextStep({...base, hasRecord: true, inEngineering: true, hasTrialResult: true}).stage, 'report');
});

test('the workflow lists the five stages in order', () => {
  assert.deepEqual(STAGES.map(s => s.label), ['Simulate', 'Investigate', 'Engineer', 'Evaluate', 'Report']);
});
