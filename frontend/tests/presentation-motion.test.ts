import test from 'node:test';
import assert from 'node:assert/strict';
import {QUALITY_TIERS, qualitySettings} from '../src/graphics-quality.ts';
import {interpolatePose} from '../src/replay-math.ts';

// Quality tiers only change rendering cost. The recorded samples and pose interpolation must be identical for every tier.
const samples = [
  {time_s: 0, x_m: 0, y_m: 0, heading_rad: 0},
  {time_s: 1, x_m: 1, y_m: 0.5, heading_rad: 0.2},
  {time_s: 2, x_m: 2.5, y_m: 0.9, heading_rad: 0.4},
] as never;

test('every quality tier leaves recorded pose interpolation unchanged', () => {
  const reference = JSON.stringify([0, 0.5, 1.5, 2].map(t => interpolatePose(samples, t)));
  for (const tier of QUALITY_TIERS) {
    qualitySettings(tier);
    assert.equal(JSON.stringify([0, 0.5, 1.5, 2].map(t => interpolatePose(samples, t))), reference);
  }
});

test('cinematic tier is the only tier with postprocessing and it keeps the heaviest settings', () => {
  const enabled = QUALITY_TIERS.filter(t => qualitySettings(t).postprocessing);
  assert.deepEqual(enabled, ['cinematic']);
  assert.ok(qualitySettings('cinematic').sedimentParticles >= qualitySettings('low').sedimentParticles);
});
