import test from 'node:test';
import assert from 'node:assert/strict';
import {inspectionView,INSPECTION_MODES,cameraMode} from '../src/replay-math.ts';

test('every inspection mode resolves and is accepted as a camera mode', () => {
  for (const mode of INSPECTION_MODES) {
    const view = inspectionView(mode, 0.7);
    for (const v of [view.eye, view.target]) assert.ok(Number.isFinite(v.x) && Number.isFinite(v.y) && Number.isFinite(v.z));
    assert.equal(cameraMode(mode), mode);
  }
  assert.throws(() => inspectionView('chase' as never, 0));
});

test('bow and stern views sit on opposite sides of the vehicle along its heading', () => {
  const bow = inspectionView('bow', 0), stern = inspectionView('stern', 0);
  assert.ok(bow.eye.x > 0 && stern.eye.x < 0);
});

test('port and starboard views sit on opposite lateral sides', () => {
  const port = inspectionView('port', 0), starboard = inspectionView('starboard', 0);
  assert.ok(port.eye.z > 0 && starboard.eye.z < 0);
  assert.ok(Math.abs(port.eye.z + starboard.eye.z) < 1e-9);
});

test('underside view is below the vehicle and three-quarter view is above', () => {
  assert.ok(inspectionView('underside', 0).eye.y < 0);
  assert.ok(inspectionView('three-quarter', 0).eye.y > 0);
});

test('views rotate with vehicle heading', () => {
  const a = inspectionView('bow', 0), b = inspectionView('bow', Math.PI / 2);
  assert.ok(Math.abs(a.eye.x - b.eye.z) < 1e-9 || Math.abs(a.eye.x + b.eye.z) < 1e-9);
});
