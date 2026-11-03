import test from 'node:test';
import assert from 'node:assert/strict';
import {nextStep, STAGES} from '../src/workflow.ts';

test('workflow starts with simulate when a lab is available and no record is open', () => {
  assert.deepEqual(nextStep({hasRecord: false, inEngineering: false, labAvailable: true}).stage, 'simulate');
});

test('workflow starts with investigate when no lab is available', () => {
  assert.equal(nextStep({hasRecord: false, inEngineering: false, labAvailable: false}).stage, 'investigate');
});

test('an open record points to the Policy Studio handoff, not to a proven fix', () => {
  const step = nextStep({hasRecord: true, inEngineering: false, labAvailable: true});
  assert.equal(step.stage, 'investigate');
  assert.match(step.text, /Open in Policy Studio/);
  assert.doesNotMatch(step.text, /fix|prove|proven/i);
});

test('engineering stage is reached from Policy Studio and lists the three stages in order', () => {
  assert.equal(nextStep({hasRecord: true, inEngineering: true, labAvailable: true}).stage, 'engineer');
  assert.deepEqual(STAGES.map(s => s.label), ['Simulate', 'Investigate', 'Engineer']);
});
