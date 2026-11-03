# V7 Cinematic Rendering Report

Scope: presentation-only rendering on the Three.js replay. Recorded samples, metrics, evidence and the 3-DOF planar motion model are unchanged. No pitch, roll, heave, forces, depth or collisions are synthesized.

## What was built

- **Inspection camera presets** (`replay-math.ts`, `replay.ts`, `trajectory.ts`): bow, stern, port side, starboard side, underside, three-quarter and close-up. Each is a fixed offset from the vehicle, rotated with its heading, so it follows the recorded pose. The existing chase, onboard, top-down and free-orbit modes are unchanged.
- **Component registry** (`component-registry.ts`): names the rendered research-vehicle parts (hull, thrusters, lamp, tether, sensor head, skid, frame) and maps each to the inspection modes that show it. `componentsForMode` rejects evidence refs not present in the loaded record. **Limitation:** no component currently carries evidence refs, because the loaded record has no per-component evidence. The entries are empty rather than invented.
- **Postprocessing** (`replay.ts`): the cinematic tier renders through an EffectComposer with a bloom pass and output pass. Other tiers use direct rendering. The composer is disposed when the tier changes or the replay is disposed.
- **WebGL context-loss handling** (`replay.ts`): on `webglcontextlost` the default is prevented and drawing is skipped; on `webglcontextrestored` the current frame is redrawn. Listeners are removed on dispose.
- **Scientific / cinematic split and presentation view** (`trajectory.ts`, `main.ts`, `trajectory.css`): the Presentation view button hides the controls and selects the cinematic tier; toggling it off returns to the high tier. Only rendering cost and image change.

## Tests run

| Check | Result |
| --- | --- |
| `npx tsc --noEmit` (frontend) | pass (exit 0) |
| `npm run build` (tsc + vite) | pass (exit 0); only a pre-existing chunk-size warning |
| `npm test` (node test runner) | 76 pass, 0 fail |

New tests: `tests/inspection-views.test.ts` (5 tests: all modes resolve, bow/stern and port/starboard opposition, underside/three-quarter height, heading rotation) and `tests/presentation-motion.test.ts` (2 tests: pose interpolation is identical across tiers; only cinematic enables postprocessing).

**Limitation of the motion test:** it shows the pure pose math does not read the quality tier. It is not a rendered-frame comparison.

## Not verified

- **Browser screenshots and rendering behaviour:** not captured. The Playwright Chromium binary could not be downloaded in this environment (download timed out twice; no system Chromium is installed; no root access). Visual results of the bloom pass, presentation view and inspection presets are unverified.
- **Measured performance:** no frame-time or render-cost measurements were taken, so no speedup or cost claim is made for any tier.
- **Context-loss recovery:** the handlers are in place and type-check, but were not exercised in a real browser context-loss event.
- **Scientific vs cinematic identical-motion check at render level:** pending a browser run.

## Recommended next step

Run the frontend in a browser with WebGL, capture each inspection preset and the presentation view, and record per-tier render times from `data-render-ms`. Only then add performance claims to this report.
