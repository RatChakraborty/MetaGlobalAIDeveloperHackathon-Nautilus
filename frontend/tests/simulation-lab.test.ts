import test from 'node:test';
import assert from 'node:assert/strict';
import {timelineMarkup, lateralSeries} from '../src/simulation-lab.ts';

test('timeline lists ledger events in order with labels and short hashes', () => {
  const html = timelineMarkup([
    {index: 0, type: 'initial_observation', diagnosis: {kind: 'ambiguous'}, event_hash: 'abcdef0123456789'},
    {index: 1, type: 'stopped', reason: 'identified', tests: 0, event_hash: '999999999999aaaa'},
  ]);
  assert.match(html, /0\. Initial observation/);
  assert.match(html, /1\. Stopped/);
  assert.match(html, /diagnosis ambiguous/);
  assert.match(html, /abcdef012345/);
  assert.doesNotMatch(html, /abcdef0123456789/);
  assert.ok(html.indexOf('0. Initial') < html.indexOf('1. Stopped'));
});

test('timeline escapes server-provided text', () => {
  const html = timelineMarkup([{index: 0, type: 'experiment_error', error: '<img src=x onerror=alert(1)>'}]);
  assert.doesNotMatch(html, /<img/);
  assert.match(html, /&lt;img/);
});

test('lateral series maps time to x and deviation to inverted y within 0..100', () => {
  const s = lateralSeries([{time_s: 0, observed_y_m: -1}, {time_s: 5, observed_y_m: 1}, {time_s: 10, observed_y_m: 0}]);
  assert.equal(s.min, -1);
  assert.equal(s.max, 1);
  assert.equal(s.points, '0.00,100.00 50.00,0.00 100.00,50.00');
});

test('flat lateral series does not divide by zero', () => {
  const s = lateralSeries([{time_s: 0, observed_y_m: 0.2}, {time_s: 1, observed_y_m: 0.2}]);
  assert.doesNotMatch(s.points, /NaN|Infinity/);
});

test('empty lateral series is empty', () => {
  assert.equal(lateralSeries([]).points, '');
});

test('empty ledger shows a clear message', () => {
  assert.match(timelineMarkup([]), /No ledger events recorded/);
});
