import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {recordedRunMarkup, eventSummary, loadRecordedRun, type RecordedRun} from '../src/recorded-muse.ts';

const run = JSON.parse(readFileSync(new URL('../public/recorded/muse-engineering-run.json', import.meta.url), 'utf8')) as RecordedRun;

test('recorded run is labelled, complete and recommends the verified candidate', () => {
  assert.equal(run.label, 'Recorded Real Muse');
  assert.equal(run.events.length, 11);
  assert.equal(run.final.decision, 'recommend');
  assert.equal(run.origin.structural_source, false);
  assert.match(run.origin.source_sha256, /^[0-9a-f]{64}$/);
});

test('markup shows the trusted numbers, provenance and cost estimate label', () => {
  const markup = recordedRunMarkup(run);
  assert.match(markup, /RECORDED REAL MUSE/);
  assert.match(markup, /Muse-proposed parameter revision/);
  assert.match(markup, /estimate, not billing/);
  assert.match(markup, /mean RMS 1\.108 m → 0\.484 m/);
  assert.equal((markup.match(/class="trace-event"/g) ?? []).length, 11);
});

test('markup escapes model-supplied text', () => {
  const hostile = {...run, final: {...run.final, rationale: '<img src=x onerror=alert(1)>'}};
  const markup = recordedRunMarkup(hostile as RecordedRun);
  assert.doesNotMatch(markup, /<img src=x/);
  assert.match(markup, /&lt;img src=x/);
});

test('event summary never invents numbers for unknown tools', () => {
  assert.equal(eventSummary({index: 1, tool: 'mystery', arguments: {}, result: {}}), 'Tool mystery executed.');
});


test('recorded engineering keeps the full trace behind an explicit disclosure', () => {
  const markup = recordedRunMarkup(run);
  assert.match(markup, /id="recorded-muse"/);
  assert.match(markup, /Recorded Real Muse — Parameter Engineering/);
  assert.match(markup, /<details class="recorded-trace"><summary>Explore 11 recorded tool events/);
  assert.match(markup, /C1/);
  assert.match(markup, /C2/);
});


test('the authentic recording loads under a nested deployment base without making a provider request', async () => {
  const urls:string[]=[];
  const fetcher:typeof fetch=async url=>{urls.push(String(url));return Response.json(run);};
  const result=await loadRecordedRun(fetcher,'/nautilus/');
  assert.deepEqual(result,run);
  assert.deepEqual(urls,['/nautilus/recorded/muse-engineering-run.json']);
  await assert.rejects(loadRecordedRun(async()=>new Response(null,{status:404})), /unavailable/);
});
