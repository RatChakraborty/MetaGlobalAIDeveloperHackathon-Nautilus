# Nautilus

Evidence-first investigation and controller engineering for simulated underwater robots.

Nautilus connects simulated AUV telemetry to competing physical explanations, bounded controller changes, matched numerical trials, held-out robustness checks, and auditable engineering reports. It distinguishes computed results, recorded studies, scripted agent behavior, and real recorded Meta Muse activity. All robot experiments are simulated; no hardware deployment or safety certification is claimed.

## How it works

Run → Investigate → Engineer → Verify → Report

1. Run: Generate public telemetry for a planar marine-vehicle simulator with disturbances such as lateral current, reduced thruster effectiveness, or heading-sensor bias.
2. Investigate: Fit competing hypotheses, preserve ambiguity where the data do not identify a unique cause, and retain public evidence references.
3. Engineer: Carry an investigated session into Policy Studio using a bounded evidence handoff. Propose a host example or scripted candidate; validate its exact controller source, parameters, and fingerprint.
4. Verify: Run matched baseline/candidate comparisons, predefined acceptance gates, and a distinct held-out robustness check. The trusted host makes the final decision.
5. Report: Export the linked investigation and controller evidence. Hash-sensitive reports preserve host-canonical JSON for verification on reimport.

The browser provides Overview, Run and Investigate, Evidence, Engineer, History, and Reports. The Three.js AUV viewer replays compatible recorded visualization companions; live public telemetry omits longitudinal position, so it cannot be plotted as a fabricated 3D trajectory.

## Demonstrations and provenance

| Study | Execution | Supported conclusion |
|---|---|---|
| Case A ,  Ambiguous drift | Fresh deterministic simulation and passive diagnosis | Five declared hypotheses fit; the protocol reports `kind=ambiguous` and `selected=null`. This is not Muse or an agent abstaining. |
| Case B ,  Bounded integral controller | Host-proposed deterministic controller evaluation | The bounded integral revision passes 8/8 predefined development gates; mean RMS cross-track error improves from 0.994 m to 0.410 m, with a 0.493 m mean held-out improvement. It is not Muse-proposed. |
| Case C ,  Aggressive lookahead rejected | Retained development recording | A predeclared 14 m lookahead candidate performs worse than the 7 m baseline in all three retained development scenarios (approximately 5.02 m vs 2.68 m RMS in the first). The inputs are private; it is a separate study from Case B. |
| Recorded Real Muse | Authentic recorded parameter-engineering session | Shows model proposals and real host-run numerical evaluations; it is not a newly executed live model call and not an unrestricted source-code repair. |

Source artifacts and study details are available through the frontend's evidence panels and [evaluation documentation](docs/EVALUATION.md). Do not combine measurements across the separate studies.

## Run locally

Prerequisites: Python 3.10+ and a recent supported Node.js release (the current frontend uses Vite 7).

```bash
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

In terminal 1, from the repository root:

```bash
.venv/bin/python -m nautilus_api.server 8000
```

In terminal 2:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:3000/`. The development frontend proxies `/api` to `127.0.0.1:8000`.

For offline checks:

```bash
.venv/bin/python -m pytest -q -p no:cacheprovider
cd frontend && npm test && npm run build
```

Use the [engineering-session guide](docs/ENGINEERING_SESSION.md) for the linked investigation → controller workflow and [demo runbook](docs/DEMO_RUNBOOK.md) for a presentation outline. The linked documents provide development and evaluation details.

## Testing and limitations

The integrated release test session reported:

| Check | Result |
|---|---|
| Frontend | 159 tests passed, TypeScript and production build passed |
| Release-critical Python/API | 114 passed |
| Broader Python suite | 646 passed, plus 4 subtests; 9 Git-metadata failures and 30 Redis setup errors occurred during environment setup |
| Canonical JSON export/import | Passed, retaining hashes, session identity, and controller fingerprints |
| Linked numerical workflow | Passed in deterministic verification: investigation, validation, paired trials, robustness, host decision, report |

Results above are from the release integration test session. Tests that require Git metadata or Redis-backed services had environment setup failures.

Diagnostic scores are heuristic rather than calibrated probabilities. Hidden simulator truth is not diagnostic input. A controller passing host gates is a result for declared simulated scenarios, not a physical repair or a safety guarantee. The in-browser session is not durable storage.

## Muse and security

The system includes server-side bounded Meta Muse adapters and an authentic recorded Muse study. Live paid calls are disabled by default and were not used for the release verification. The free deterministic and scripted engineering paths should not be described as live Muse.

Keep `MODEL_API_KEY`, `NAUTILUS_DEMO_TOKEN`, Upstash credentials, evaluator secrets, and private fault-truth files outside version control. Use [`.env.example`](.env.example) only as a list of variable names. The trusted host validates model proposals, executes numerical tools, and enforces its gates; model text never authorizes its own acceptance.


## License

See [LICENSE](LICENSE).
