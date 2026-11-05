import {test} from 'node:test';
import assert from 'node:assert/strict';
import {studioHandoff} from '../src/studio-handoff.ts';

const record = (events: Record<string, unknown>[]) => ({
  file: {schema_version: 'nautilus.public-investigation.v2', run_id: 'run-1', source_kind: 'recorded', disclosure: '', ledger: []},
  events,
}) as never;

const observation = {type: 'observation', hash: 'h-obs', observations: [
  {time_s: 0, observed_y_m: 0.1}, {time_s: 1, observed_y_m: -0.4}]};
const fit = {type: 'fit', hash: 'h-fit', report: {hypothesis: 'thruster_gain_loss', converged: true,
  parameters: {gain: 0.8, bias: 0.02}, weighted_rmse: 0.07, identifiability: {rank: 1, condition: 1e8, qualification: 'weak'},
  evidence_refs: ['h-obs']}};
const finalized = {type: 'finalized', hash: 'h-final', diagnosis: {hypothesis: 'unresolved', confidence: 'low',
  ambiguity_statement: 'two explanations fit equally', evidence_refs: ['h-obs']}};

test('handoff carries observations, hypotheses, fit, uncertainty and reproducibility', () => {
  const h = studioHandoff(record([observation, fit, finalized]));
  assert.equal(h.schema_version, 'nautilus.studio-handoff.v1');
  assert.equal(h.reproducibility.run_id, 'run-1');
  assert.equal(h.reproducibility.ledger_head, 'h-final');
  assert.equal(h.observations.episodes, 1);
  assert.equal(h.observations.max_abs_observed_y_m, 0.4);
  assert.equal(h.hypotheses[0].status, 'candidate_hypothesis');
  assert.deepEqual(h.hypotheses[0].parameters, {gain: 0.8, bias: 0.02});
  assert.equal(h.hypotheses[0].identifiability.qualification, 'weak');
  assert.equal(h.conclusion?.status, 'recorded_conclusion_not_proof');
  assert.ok(h.limitations.some(l => /not proven causes/.test(l)));
});

test('no hypothesis is presented as proven and no truth-like key is emitted', () => {
  const h = studioHandoff(record([observation, fit]));
  const text = JSON.stringify(h);
  assert.doesNotMatch(text, /truth|hidden|private|evaluator|true_fault/i);
  assert.equal(h.conclusion, null);
  assert.ok(h.hypotheses.every(x => x.status === 'candidate_hypothesis'));
});

test('missing fit is stated as a limitation rather than invented', () => {
  const h = studioHandoff(record([observation]));
  assert.equal(h.hypotheses.length, 0);
  assert.ok(h.limitations.some(l => /No numerical fit/.test(l)));
});

test('repeated fits transfer only the latest bounded hypothesis set and actual final confidence',()=>{
  const fits=Array.from({length:7},(_,i)=>({...fit,hash:`fit-${i}`,report:{...fit.report,hypothesis:`hyp-${i%5}`,weighted_rmse:7-i}}));
  const h=studioHandoff(record([observation,...fits,{...finalized,confidence:'abstain',ambiguity_statement:'Further evidence required.'}]));
  assert.equal(h.hypotheses.length,4);
  assert.equal(h.hypotheses[0].weighted_rmse,1);
  assert.equal(h.conclusion?.confidence,'abstain');
  assert.equal(h.conclusion?.ambiguity_statement,'Further evidence required.');
});
