import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readControlLab,controlLabMarkup,controlLabDiff,PARAMETERS,SCOPE} from '../src/control-lab.ts';

const run = await promisify(execFile)('.venv/bin/python',['frontend/tests/control_lab_fixture.py'],
  {cwd:'..',env:{...process.env,PYTHONPATH:'.',OMP_NUM_THREADS:'1',OPENBLAS_NUM_THREADS:'1',MKL_NUM_THREADS:'1'},encoding:'utf8'});
const raw = JSON.parse(run.stdout);
const clone = () => JSON.parse(JSON.stringify(raw));

test('real exported artifact validates with approved differences inside declared bounds', () => {
  const lab = readControlLab(raw);
  assert.equal(lab.schema_version,'nautilus.control-lab-recommendation.v1');
  assert.equal(lab.scope,SCOPE);
  const [name,change] = Object.entries(lab.approved_differences)[0] as [keyof typeof PARAMETERS,any];
  const [low,high] = PARAMETERS[name].bounds;
  assert.ok(change.candidate >= low && change.candidate <= high);
  assert.equal(change.baseline,lab.controller.baseline_configuration[name]);
  assert.equal(lab.human_review.status,'required');
  assert.equal(lab.human_review.performed,false);
  assert.ok(['accept','reject'].includes(lab.robustness.decision));
});

test('panel renders the decision, proposal and qualifications', () => {
  const html = controlLabMarkup(readControlLab(raw));
  assert.match(html,/V6 control lab/);
  assert.match(html,/not a deployed repair/);
  assert.match(html,/Declared gates/);
  assert.match(html,/Unresolved risks/);
  assert.match(html,/Accepted on a fixed development suite|Rejected by the predeclared acceptance rule/);
  assert.match(html,/screen candidate selection|never consulted/i);
  assert.match(html,/no pitch, roll|duration cap|completed/);
  assert.match(controlLabMarkup(null),/Open control-lab recommendation/);
});

test('diff download mirrors the approved differences', () => {
  const diff = controlLabDiff(readControlLab(raw));
  assert.equal(diff.schema_version,'nautilus.configuration-diff.v1');
  assert.equal(diff.scope,'Review artifact only; applying it is a separate human decision. Not a deployed repair.');
  assert.deepEqual(diff.approved_differences,raw.approved_differences);
  assert.equal(diff.human_review,'required');
});

test('rejects a decision that contradicts the host rule', () => {
  const bad = clone();bad.recommendation.decision = bad.robustness.decision==='accept'?'reject':'accept';
  assert.throws(()=>readControlLab(bad),/follow the host rule/);
});

test('rejects out-of-bounds, unchanged or unbacked differences', () => {
  const outOfBounds = clone();
  for(const change of Object.values(outOfBounds.approved_differences) as any[])change.candidate = 999;
  assert.throws(()=>readControlLab(outOfBounds),/out of bounds/);
  const noProposal = clone();noProposal.proposal = null;
  assert.throws(()=>readControlLab(noProposal),/validated proposal/);
  const mismatched = clone();
  for(const change of Object.values(mismatched.approved_differences) as any[])change.baseline = -1;
  assert.throws(()=>readControlLab(mismatched),/match the baseline/);
});

test('rejects a weakened scope or human-review claim', () => {
  const scope = clone();scope.scope = 'Deployed repair with verified improvement.';
  assert.throws(()=>readControlLab(scope),/not a deployed repair/);
  const review = clone();review.human_review.performed = true;
  assert.throws(()=>readControlLab(review),/must remain required/);
  const executed = clone();executed.patch = {...executed.patch,status:'executed',certified:false};
  assert.throws(()=>readControlLab(executed),/not implemented/);
  const certified = clone();certified.patch = {...certified.patch,certified:true};
  assert.throws(()=>readControlLab(certified),/cannot be certified/);
});

test('rejects unknown fields, unserialisable references and empty evidence', () => {
  const extra = clone();extra.metrics = {rms:0.01};
  assert.throws(()=>readControlLab(extra),/Invalid control-lab artifact fields/);
  const hash = clone();hash.artifact_hash = 'not-a-hash';
  assert.throws(()=>readControlLab(hash),/reference/);
  const evidence = clone();evidence.evidence_refs = [];
  assert.throws(()=>readControlLab(evidence),/evidence references/);
  const gates = clone();gates.robustness.gates = [];
  assert.throws(()=>readControlLab(gates),/Declared gates required/);
  assert.throws(()=>readControlLab({...clone(),schema_version:'nautilus.control-lab.v2'}),/Unsupported control-lab schema/);
});
