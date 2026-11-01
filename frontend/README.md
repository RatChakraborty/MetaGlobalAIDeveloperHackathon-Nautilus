# Nautilus recorded-investigation dashboard

Static Vite/TypeScript app with Investigator, Analytics and planar Trajectory tabs.
It has no live backend, agent, keys or client API calls. No datasets ship in the build.

```bash
cd frontend
npm ci
npm test
python -m unittest discover -s tests -p 'test_*.py'
npm run dev
npm run build
```

Open a local public export with **Open investigation**. The evidence timeline
selects the visible stage; new observations invalidate prior fit scores. Shared
play/pause, speed and seek controls replay recorded samples without integrating
physics. Fits, residuals, scores, convergence and conclusions come from records.
Missing fields show `n/a`. Singleton logs currently lack stored prediction curves.

Export outside the repository:

```bash
python frontend/export_records.py /path/to/record.json --output /private/replay/investigation.json
python frontend/export_records.py /run/observed_telemetry.csv --output /private/replay/investigation.json \
  --visualization-source /run/telemetry.csv --visualization-output /private/replay/visualization.json
```

The exporter supports the recorded laboratory history (including the end-to-end
validation wrapper) and actual six-channel simulator CSVs. It validates hashes,
references and observation schemas. Unknown event/report fields fail closed.
Original event bytes are preserved as canonical strings so Python float spelling
cannot break browser SHA-256 checks. A recorded final conclusion is separately
exported with validated observation references; it is not claimed to have been
present in a pre-finalization ledger. CSV runs have explicitly export-generated
observation references, with no invented investigator actions or fits.

Visualization files contain recorded time/x/y/heading from the same CSV run and,
when present, allowlisted cable dimensions from its recorded mission metadata. They
are bound to its run ID and must be loaded separately. The scene is planar3-DOF,
with fixed depth, a schematic marker and no roll/pitch. Public observations lack
x; their full path cannot be reconstructed. The GPU renderer uses Three.js; an
explicit Three.js SVG software fallback supports machines without WebGL. Neither
renderer calculates dynamics. Trajectory positions interpolate linearly and headings use the shortest arc.
Outside each recorded interval, its endpoint is held. Samples remain unchanged.

Never put private evaluator records, configuration, answers or generated traces
in `public/` or `dist/`. A truth-visibility toggle is not access control. Local file
loading sends no file to a server, but publication of any demonstration data still
requires separate approval. The default build is dataset-free. Human review is
required for free-text operator notes and newly approved exports.

For GitHub Pages, set the repository base path when building:

```bash
NAUTILUS_BASE=/MetaGlobalAIDeveloperHackathon-Nautilus/ npm run build
```

Deploy only `dist/` after approval. No workflow, commit, push or deployment is
performed by these commands. Serve the directory over local HTTP for offline use;
opening `index.html` using `file://` is unsupported. Dependencies are pinned and
locked. IBM Plex Sans and Mono are bundled locally under OFL; notices are in `public/licenses/`.
Three.js0.180.0 was published2025-09-03, satisfying the version-age requirement.

Deferred: Muse/Q&A, live APIs, repairs, corrected trajectories, confidence
probabilities, private truth access, invented forces/currents/states, and model
prediction overlays until genuine compatible stored samples exist. No simulator,
fitter, evaluator or frozen manifest is modified by this frontend.

Principal UI tokens live in `src/theme.css`. Sans serves general text; Mono is
reserved for technical values. The procedural seabed, rocks, vegetation, sediment
and optional fish are decorative. They do not represent depth, obstacles or
measured current. Their motion follows replay time deterministically and freezes
under reduced-motion preferences. Cable/corridor lines require recorded dimensions.

Trajectory cameras: chase, virtual onboard inspection, top-down and free orbit.
Only cameras are smoothed. Lateral exaggeration defaults to 1× and changes rendering
only; measurements remain physical. A reference needs its own validated public
record and visualization with matching cable/corridor dimensions. Runs align by
recorded elapsed seconds and hold endpoints; a reference is not a verified repair.
The detailed hull, cable thickness, propellers, wash and water effects are illustrative.
Hardware WebGL2 adds fog, headlights, shadows and sand bump detail; the SVG fallback
uses simpler lighting. No demonstration records are bundled or automatically fetched.
