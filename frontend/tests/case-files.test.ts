import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {CASE_A_REQUEST, DEMO_CASES, MODE_LEGEND, caseFilesMarkup, modeLegendMarkup} from '../src/case-files.ts';
import {overviewMarkup} from '../src/overview.ts';
import {initialSession} from '../src/session.ts';

test('the legend names all four execution modes and says every experiment is simulated', () => {
  const markup = modeLegendMarkup();
  assert.deepEqual(MODE_LEGEND.map(m => m.mode), ['recorded', 'live', 'muse', 'mock']);
  for (const mode of ['Recorded demonstration', 'Live deterministic computation', 'Live Meta Muse', 'Mock development session']) {
    assert.match(markup, new RegExp(mode));
  }
  assert.match(markup, /All robot experiments are simulated, including live calculations\./);
  assert.match(markup, /off by default/);
});

test('exactly three cases are exposed, each with complete provenance metadata', () => {
  assert.equal(DEMO_CASES.length, 3);
  assert.deepEqual(DEMO_CASES.map(c => c.id), ['A', 'B', 'C']);
  for (const item of DEMO_CASES) {
    assert.ok(item.title.length > 10, `case ${item.id} title`);
    assert.ok(item.purpose.length > 10, `case ${item.id} purpose`);
    assert.ok(item.provenance.length > 20, `case ${item.id} provenance`);
    assert.ok(item.detail.length > 40, `case ${item.id} detail`);
    assert.ok(item.resultIds.length > 5, `case ${item.id} result ids`);
    assert.match(item.evidence.file, /^evidence\/[\w.-]+\.json$/);
    assert.match(item.evidence.sha256, /^[a-f0-9]{64}$/);
    assert.match(item.browser, /Browser workflow/);
  }
});

test('every declared evidence hash matches the artifact shipped in public/', () => {
  for (const item of DEMO_CASES) {
    const bytes = readFileSync(new URL(`../public/${item.evidence.file}`, import.meta.url));
    const actual = createHash('sha256').update(bytes).digest('hex');
    assert.equal(actual, item.evidence.sha256, `case ${item.id} evidence hash`);
  }
});

test('mode labels are honest: live means deterministic computation, not Muse', () => {
  const [a, b, c] = DEMO_CASES;
  assert.equal(a.mode, 'Live deterministic computation');
  assert.equal(b.mode, 'Live deterministic computation');
  assert.equal(c.mode, 'Recorded demonstration');
  for (const item of DEMO_CASES) {
    assert.doesNotMatch(`${item.mode} ${item.provenance}`, /live Muse|Muse-generated|genuinely proposed by Muse/i);
  }
  assert.match(c.provenance, /Not selected by Muse/);
  assert.match(a.provenance, /no model call/);
  assert.match(a.detail, /kind=ambiguous and selected=null/);
  assert.match(b.detail, /not by Muse/);
});

test('Case B and the 3 m lookahead study stay explicitly separate', () => {
  const b = DEMO_CASES[1];
  const c = DEMO_CASES[2];
  assert.match(b.title, /integral compensation/i);
  assert.equal(b.action, 'studio');
  assert.match(`${b.detail} ${c.detail}`, /must not be merged/i);
  assert.match(c.detail, /14 m/);
  assert.match(c.detail, /separate candidate/);
  assert.equal(c.action, 'none');
});

test('case A is the declared passive scenario and is the only runnable case', () => {
  assert.deepEqual(CASE_A_REQUEST, {
    scenario: {current_y: -0.06, port_efficiency: 1.0, starboard_efficiency: 1.0, heading_bias_rad: 0.0},
    seed: 42,
  });
  const markup = caseFilesMarkup({apiEnabled: true});
  assert.equal((markup.match(/case-card case-/g) ?? []).length, 3);
  assert.equal((markup.match(/id="case-a-run"/g) ?? []).length, 1);
  assert.match(markup, /Run case A now/);
  assert.match(markup, /href="evidence\/case-a-passive-fits\.json"/);
  assert.match(markup, /href="evidence\/case-b-studio-trial\.json"/);
  assert.match(markup, /href="evidence\/case-c-lookahead-14m\.json"/);
  assert.match(markup, /Case A is passive ambiguity, not an agent or Muse abstention/);
});

test('unavailable API and a running case both disable their actions', () => {
  const disabled = caseFilesMarkup({apiEnabled: false});
  assert.match(disabled, /id="case-a-run" disabled/);
  assert.match(disabled, /data-goto="Policy Studio" disabled/);
  const busy = caseFilesMarkup({apiEnabled: true, busy: true});
  assert.match(busy, /id="case-a-run" disabled>Case A running…/);
  assert.match(busy, /data-goto="Policy Studio"/);
});

test('the overview renders the legend once and the three case files', () => {
  const markup = overviewMarkup(initialSession(), {apiEnabled: true, recordId: null, recordSource: null});
  assert.equal((markup.match(/class="case-card case-/g) ?? []).length, 3);
  assert.match(markup, /Case files/);
  assert.match(markup, /THREE VERIFIED RECORDS/);
  assert.doesNotMatch(markup, /<script/i);
});
