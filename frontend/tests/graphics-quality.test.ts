import {test} from 'node:test';
import assert from 'node:assert/strict';
import {QUALITY_TIERS, qualitySettings, qualityTier} from '../src/graphics-quality.ts';

test('quality tiers are closed, ordered by cost and accept only known names', () => {
  assert.deepEqual([...QUALITY_TIERS], ['low', 'balanced', 'high', 'cinematic']);
  assert.throws(() => qualityTier('ultra'), /Unknown graphics quality tier/);
  const cost = QUALITY_TIERS.map(t => qualitySettings(t).sedimentParticles);
  assert.deepEqual(cost, [...cost].sort((a, b) => a - b));
});

test('low tier disables shadows and postprocessing; cinematic enables postprocessing only', () => {
  assert.equal(qualitySettings('low').shadows, false);
  assert.equal(qualitySettings('low').postprocessing, false);
  assert.equal(qualitySettings('cinematic').postprocessing, true);
  assert.equal(qualitySettings('high').postprocessing, false);
});

test('pixel ratio cap never exceeds 2', () => {
  for (const tier of QUALITY_TIERS) assert.ok(qualitySettings(tier).pixelRatioCap <= 2);
});
