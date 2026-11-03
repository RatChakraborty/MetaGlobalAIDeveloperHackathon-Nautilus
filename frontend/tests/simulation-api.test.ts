import test from 'node:test';
import assert from 'node:assert/strict';
import {runSimulation, runInvestigation, runMuseInvestigation, ApiError} from '../src/simulation-api.ts';

const realFetch = globalThis.fetch;
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {status, headers: {'Content-Type': 'application/json'}});

test.afterEach(() => { globalThis.fetch = realFetch; });

test('unreachable API produces a user-facing error', async () => {
  globalThis.fetch = async () => { throw new TypeError('network down'); };
  await assert.rejects(runSimulation('http://x', {scenario: {}}), (e: unknown) => e instanceof ApiError && /unreachable/.test((e as Error).message));
});

test('server validation errors surface the server message', async () => {
  globalThis.fetch = async () => json({error: 'current_y must be a number in [-2.5, 2.5]'}, 400);
  await assert.rejects(runSimulation('http://x', {scenario: {current_y: 9}}), /current_y must be/);
});

test('investigation polls until success and reports progress', async () => {
  const id = 'a'.repeat(32);
  const states = ['queued', 'running', 'succeeded'];
  const seen: string[] = [];
  globalThis.fetch = async (url) => {
    const isPost = String(url).endsWith('/investigations');
    const status = isPost ? 'queued' : states.shift()!;
    return json({job: {id, status, request: {scenario: {}}, result: status === 'succeeded' ? {observations: [], investigation: {outcome: {kind: 'identified', selected: 'lateral_current', competitive: [], reasons: []}, ledger: [], tests: 0, time_s: 0, decision: 'lateral_current', error: null}, protocol_fingerprint: 'f'} : null, error: null}}, isPost ? 202 : 200);
  };
  const job = await runInvestigation('http://x', {scenario: {}}, j => seen.push(j.status), {intervalMs: 0});
  assert.equal(job.status, 'succeeded');
  assert.deepEqual(seen, ['queued', 'running', 'succeeded']);
});

test('live Muse run sends the token as a Bearer header and never in the body or URL', async () => {
  let seen: {url: string; init: RequestInit} | null = null;
  globalThis.fetch = async (url, init) => { seen = {url: String(url), init: init!}; return json({result: {public_record: {}, provenance: {}}, request: {scenario: {}}, usage: {}}); };
  await runMuseInvestigation('http://x', {scenario: {current_y: 1}}, 'secret-token');
  const headers = seen!.init.headers as Record<string, string>;
  assert.equal(headers.Authorization, 'Bearer secret-token');
  assert.equal(headers['Content-Type'], 'application/json');
  assert.equal(seen!.url, 'http://x/api/muse');
  assert.equal(seen!.init.method, 'POST');
  assert.ok(!String(seen!.url).includes('secret-token'));
  assert.ok(!String(seen!.init.body).includes('secret-token'));
});

test('rejected live Muse run surfaces the server message', async () => {
  globalThis.fetch = async () => json({error: 'unauthorized'}, 401);
  await assert.rejects(runMuseInvestigation('http://x', {scenario: {}}, 'wrong'), /unauthorized/);
});

test('investigation that never finishes times out with a clear message', async () => {
  globalThis.fetch = async (url) => json({job: {id: 'b'.repeat(32), status: String(url).endsWith('investigations') ? 'queued' : 'running', request: {scenario: {}}, result: null, error: null}}, String(url).endsWith('investigations') ? 202 : 200);
  await assert.rejects(runInvestigation('http://x', {scenario: {}}, () => {}, {intervalMs: 0, maxPolls: 3}), /did not finish in time/);
});
