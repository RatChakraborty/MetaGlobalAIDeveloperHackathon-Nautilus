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

Deploy only `dist/` after approval. These local commands do not deploy. Serve the directory over local HTTP for offline use;
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
uses simpler lighting. No demonstration records are bundled; ordinary builds make no startup data requests.

`NAUTILUS_DEMO_ENABLED` defaults to disabled. Only after dataset approval, build
with `NAUTILUS_DEMO_ENABLED=true` and place the four approved records under
`public/demo/`. The default disturbance and nominal reference use the same schema
validators and time alignment as manual imports; the initial tab is Trajectory.
Loading is atomic and does not replace a manual selection made during startup.
A missing or invalid demo leaves local import available. No sample files are
currently included. Browser users can inspect every downloaded visualization file.

The manual `Dashboard Pages` workflow installs the lockfile, runs frontend tests
and validates TypeScript through the production build. Its default `publish=false`
only verifies the build. It always disables demo loading. Publication is restricted
to `main` and requires a separately approved manual invocation with `publish=true`,
Pages configured for Actions, and any repository environment approvals. Do not
invoke publication yet. Treat any Pages site as publicly accessible regardless of
repository visibility. No site or demonstration dataset is currently deployed by
this milestone. A future approved dataset change must install only the four
reviewed JSON exports and explicitly enable the build flag.

The proposed demonstration is synthetic simulation-only development telemetry.
The nominal reference is not a repaired run. Fit reports and agent conclusions
are unavailable. Exact publication hashes remain in the separate private review
package; do not copy its source configurations or raw CSVs into this repository.
See [the future replay contract](../PRE_MUSE_INTERFACE_CONTRACT.md).

Controller-aware public exports use `nautilus.public-investigation.v2`; separate
trajectory exports use `nautilus.visualization-only.v2`. Historical v1 records
remain supported. The controller provenance inspector shows approved identities,
configuration values and differences; old records show `Controller not recorded`.
New visualization metadata must match the public context event. The renderer still
only interpolates recorded samples. `export_configuration_evaluation` in the
exporter writes matched evaluation records outside the repository; it does not
claim repairs or publish data. Private comparison records require separate review.

After loading a finalized investigation, **Open configuration evaluation** accepts
a separately exported `nautilus.post-investigation.v1` sidecar. Its hash and final
ledger anchor must match. It shows real host-side outcomes and simulation-only
metrics, not diagnosis evidence or verified repairs. `export_host_evaluation` writes
the public investigation, sidecar and genuine comparison files outside the source
tree. Use candidate as primary and baseline as reference in the existing Trajectory
imports. Absent, skipped, rejected and failed evaluations contain no invented metrics.

## Supervisor events and downloads

Add `--supervisor-directory /private/companions` to the existing exporter to write
Python-derived public events and, when visual data is supplied, separate truth
markers. `--episode-ref OBSERVATION_HASH` explicitly binds a new visualization v3
file to one reset-aligned episode. Legacy multi-episode files still load, but
ambiguous command overlays remain unavailable. Never append these companions to
the laboratory ledger. See [the milestone report](../SUPERVISOR_AND_EXPORT_REPORT.md).

The Investigator tab imports public supervisor events and offers validated
`investigation_report.md` and, with an accepted recorded proposal, `config_diff.json`
downloads. Reports omit controller source and raw truth trajectories; narratives
are encoded as data. Diffs require operator review and are not deployment-ready.
The Trajectory tab separately imports visualization-only markers and has an opt-in
command-arrow overlay. Commands are held between logged samples and hidden beyond
each run's interval; they are requested newtons, never measured force or RPM.
