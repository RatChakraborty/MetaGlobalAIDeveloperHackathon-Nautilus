# Frozen Muse evaluation v1 — complete results

Muse Wonder did **not improve exact mechanism identification** over the predeclared resource-matched fixed baseline in this twelve-case sample. Both identified 7/9 representable mechanisms (77.8%; descriptive 95% Wilson interval 45.3–93.7%). Each won one discordant pair. Muse used fewer numerical fits but much more wall time, and its advisory experiments produced corridor excursions in 11/12 cases versus 4/12 for the main baseline. This is not evidence of statistical superiority or safe autonomous deployment.

## Execution and freeze

All 12 planned cases were attempted exactly once; all 12 three-policy case groups closed and were scored. No cases were excluded, repeated, replaced or added. This report uses genuine Meta Responses API calls and actual numerical laboratory fits/simulations. Fake-provider responses were used only for preflight regression tests. Historical development investigations were excluded.

- Candidate: `340d1c12e1f39252a84b4aaae59dd149b1d2b93b` (unchanged Phase C implementation).
- Evaluator/protocol pre-freeze commit: `c54837776ba396158931552f0225c874e5e10917`.
- Model: `muse-wonder-1.0`; endpoint `https://api.meta.ai/v1/responses`; reasoning `low`; tool choice `auto`; parallel calls disabled.
- Complete frozen manifest file SHA-256: `8fd6019dc1d1f2250dcc0befc1ed9b9e210c363e46a9b0114fe78f012b8e48f9`.
- Canonical manifest body fingerprint (excludes its own digest): `19695068bf198fb47c846f49238d1b9c4945979f00eca6a3350617a634411ecd`.
- Prompt fingerprint: `330d744ec07d6c69ae4c90c864586a8f378df07e72015e4a94e6ac29234bbb97`; tool-schema fingerprint: `ee87178576a6638df5047be19a4644b96bb51ae6fc3c92db1eac9721ad37bd73`.
- Python 3.12.14, NumPy 2.5.4, SciPy 1.18.1; Linux-6.18.57-x86_64-with-glibc2.41; OMP/OpenBLAS/MKL thread counts all 1.

The manifest was written to private storage and its two fingerprints reported before physical case generation. Frozen sources/runtime were revalidated after all inference. No frozen source, prompt, numerical method, baseline rule, selection distribution or scoring threshold changed after freeze. The final results commit adds this report only. Private seeds, parameters, answers, traces, structured arguments, ledgers and provider continuation identifiers remain outside Git. Hashes detect inconsistency; they do not prove provider authorship or prevent privileged rewriting.

## Design and comparison contracts

Twelve independent simulated physical cases used a frozen balanced mix: two nominal, two lateral-current, two thruster (port/starboard), two signed sensor-bias, two genuinely simultaneous compounds, and two controller/plant mismatches. Every policy got an independent current `Laboratory`/`SafeBackend` with identical initial public observations, controller declarations and initial evidence hash. Same requested maneuvers had matched deterministic noise. No policy received the injected mechanisms or private generation parameters. Muse additionally received its existing public supervisor-derived summary, not independent measurements.

This is a prospective holdout relative to audited repository/workspace history: exposed historical holdout regions were excluded; new private high-entropy seeds were frozen in a disjoint high range before generation. Inaccessible external experiment history cannot be audited. The sample is purposively balanced, not sampled from deployment prevalence.

The **main comparator, fixed_matched**, is a pre-frozen experiment-first wrapper around the existing fixed registry-order strategy and numerical finalization rules. It uses the first fixed library experiment, then at most eight registry-order fits. It has the same hypothesis/experiment permissions and numerical/action/safety budgets as Muse; its policy covers only the first eight registered hypotheses. It has no oracle fit cache. It is a resource-matched fixed policy, not an optimized greedy or exhaustive benchmark.

The unchanged **fixed_reference** is separately retained: it spends eight fits before its experiment invalidates them, then abstains without refit budget. That structural limitation was documented before freeze; it is not the headline comparator. Older evaluations used different laboratories or cached exhaustive fits and larger budgets, so their scores were not reused.

Per-policy laboratory ceilings: 8 fits, 16 starts, 1 experiment, 16 simulated seconds, 12 action attempts, configuration evaluation disabled. Muse: at most 12 requests, 4096 output tokens/request, 32768 total output including reasoning, 350000 measured input soft stop, 1 MB cumulative request JSON, 60-second provider timeout, 600-second between-action deadline, zero retries. These are host checks; measured input can cross a threshold on the final accepted response. No model switch or adaptive prompt variant occurred. Every API response contained one structured call, so the candidate’s built-in no-tool recovery path was not exercised.

## Scientific outcomes

Exact physical finding uses the frozen healthy-range-to-nominal mapping. Complete exact identification requires the whole injected mechanism set. Nine cases have singleton/nominal truth representable by the interface; two compounds and the joint-plant mismatch do not. Identifying one constituent is partial, never complete credit. Raw declared-label exact counts also equal 7, 7 and 0 for Muse, matched and reference respectively.

| Outcome | Muse | Fixed matched (main) | Fixed reference |
|---|---:|---:|---:|
| Voluntary terminal decisions / attempted | 12/12 (100%) | 12/12 (100%) | 12/12 (100%) |
| Host terminations / attempted | 0/12 | 0/12 | 0/12 |
| Exact / representable attempted | 7/9 (77.8%) | 7/9 (77.8%) | 0/9 (0%) |
| Exact / all attempted | 7/12 (58.3%) | 7/12 (58.3%) | 0/12 |
| Whole broad family / all attempted | 7/12 (58.3%) | 8/12 (66.7%) | 0/12 |
| Partial constituent / nonrepresentable | 2/3 | 3/3 | 0/3 |
| Partial mixed-family coverage / mixed compounds | 2/2 | 2/2 | 0/2 |
| Tentative decisions / attempted | 7/12 (58.3%) | 0/12 | 0/12 |
| Voluntary abstention / attempted | 3/12 (25.0%) | 2/12 (16.7%) | 12/12 (100%) |
| Truth-inconsistent supported claims / attempted | 0/12 | 0/12 | 0/12 |
| Supported incomplete constituent claims / nonrepresentable | 0/3 | 3/3 | 0/3 |
| Selective exactness / nonabstaining representable diagnoses | 7/7 (100%) | 7/7 (100%) | Not defined (0 diagnoses) |

The completion denominator includes voluntary abstentions: completion means a valid model/policy decision, not a correct diagnosis. Conditional exact yield among the nine representable valid completions is also 7/9 for Muse and matched; all cases completed, so failures do not disappear from this denominator. Nonabstaining representable coverage is 7/9 for both. The reference exact interval is 0–29.9%. Perfect selective accuracy on seven diagnoses is not calibrated confidence or established general reliability.

Paired Muse minus matched: exact 0/12 (0 percentage points); whole family −1/12 (−8.3 points); voluntary abstention +1/12 (+8.3 points). Exact discordance: Muse-only win 1, matched-only win 1, both exact 6, neither exact 4. On the nine representable cases this is one win each, six shared successes and one shared non-success. No significance or superiority claim is made.

Muse made two supported diagnoses, seven tentative diagnoses and three abstentions. The matched policy made ten supported diagnoses and two abstentions, including three incomplete constituent diagnoses. A confidence tag is an investigator claim. Zero truth-inconsistent supported claims does not establish confidence calibration, unique physical identifiability or evidence-warranted certainty.

No independent identifiability reference exists. Abstentions have no binary correct/incorrect score. Numerical ambiguity was recorded in 1/12 Muse and 2/12 matched final decisions, versus 0/12 reference. These are model-family score comparisons, not independent evidence that the physical cause was or was not resolvable.

### Aggregate strata

Each stratum has two cases. Entries show exact / 2; partial constituent / 2; voluntary abstention / 2. All policies completed both cases in every stratum. Per-case labels/stratum mappings are deliberately withheld to preserve private answer keys.

| Stratum | Muse exact; partial; abstain | Matched exact; partial; abstain | Reference exact; partial; abstain |
|---|---:|---:|---:|
| compound | 0/2; 2/2; 0/2 | 0/2; 2/2; 0/2 | 0/2; 0/2; 2/2 |
| current | 2/2; 0/2; 0/2 | 2/2; 0/2; 0/2 | 0/2; 0/2; 2/2 |
| mismatch | 0/2; 0/2; 2/2 | 0/2; 1/2; 1/2 | 0/2; 0/2; 2/2 |
| nominal | 1/2; 0/2; 1/2 | 1/2; 0/2; 1/2 | 0/2; 0/2; 2/2 |
| sensor | 2/2; 0/2; 0/2 | 2/2; 0/2; 0/2 | 0/2; 0/2; 2/2 |
| thruster | 2/2; 0/2; 0/2 | 2/2; 0/2; 0/2 | 0/2; 0/2; 2/2 |

Current, thruster and sensor strata each had 2/2 exact findings for both Muse and matched. Nominal had 1/2 for each, on different cases. Both compound cases yielded partial constituent findings for both. Neither policy completely identified either mismatch case; Muse abstained on both, while matched identified one constituent in the joint-plant condition and abstained on the other. There is no complete singleton representation for three of the twelve truths, and no full compound diagnosis can be established by this interface.

### Every attempted case

Exact and partial are distinct frozen scores. All Muse origins are `model` with `model_finalized`; all deterministic origins are `policy`. No host abstention is relabeled scientific abstention. The original fixed reference voluntarily abstained on every case, using 8 fits and 1 experiment per case.

| Case | Muse decision | Muse exact / partial | Matched decision | Matched exact / partial | Muse requests / fits | Muse seconds | Excursion Muse / matched / reference |
|---|---|---|---|---|---:|---:|---|
| E01 | model / abstain | no / no | policy / abstain | no / no | 10 / 7 | 112.63 | 1 / 0 / 0 |
| E02 | model / tentative | yes / no | policy / supported | yes / no | 9 / 7 | 90.58 | 1 / 0 / 0 |
| E03 | model / supported | yes / no | policy / supported | yes / no | 9 / 7 | 79.68 | 1 / 0 / 0 |
| E04 | model / tentative | no / yes | policy / supported | no / yes | 8 / 5 | 85.82 | 1 / 1 / 1 |
| E05 | model / abstain | no / no | policy / supported | no / yes | 9 / 7 | 87.97 | 1 / 0 / 0 |
| E06 | model / tentative | yes / no | policy / supported | yes / no | 10 / 8 | 85.31 | 1 / 1 / 1 |
| E07 | model / tentative | yes / no | policy / abstain | no / no | 10 / 8 | 108.40 | 0 / 0 / 0 |
| E08 | model / tentative | yes / no | policy / supported | yes / no | 10 / 8 | 83.68 | 1 / 0 / 0 |
| E09 | model / abstain | no / no | policy / supported | yes / no | 7 / 5 | 77.71 | 1 / 0 / 0 |
| E10 | model / supported | yes / no | policy / supported | yes / no | 9 / 7 | 92.17 | 1 / 0 / 0 |
| E11 | model / tentative | no / yes | policy / supported | no / yes | 10 / 8 | 120.19 | 1 / 1 / 1 |
| E12 | model / tentative | yes / no | policy / supported | yes / no | 9 / 7 | 131.61 | 1 / 1 / 1 |

## Agency, numerical evidence and continuation

All 110 real requests returned HTTP 200, completed status and one structured function call. All 110 unique actions were accepted: 84 `propose_hypothesis`, 12 `request_experiment`, 2 `get_fit_report`, 12 `finalize`. All 98 continuation requests linked the preceding response and exact returned call ID. There were no provider, protocol, malformed-call, stale-finalization, incomplete-response or host-budget failures; no missing usage records or retries. All 12 finalizations originated with the model.

Muse selected five experiment families: differential step 5, coast down 3, heading response 2, amplitude ramp 1, thrust step 1. All were actual numerical experiments, not mocked tool outputs. It fit 5–8 distinct hypotheses per case, with 58 post-experiment fits across all 12 cases. Evidence references and final current-fit linkage validated. Repeated fits count as work, not additional independent cases. All 110 original tool results were checked against their lossless presentations and restoration hashes.

| Work / evidence | Muse | Fixed matched | Fixed reference |
|---|---:|---:|---:|
| Fit calls / converged reports | 84 / 84 | 96 / 96 | 96 / 96 |
| Optimization starts | 100 | 168 | 168 |
| Saturated reports / fits | 18/84 (21.4%) | 36/96 (37.5%) | 44/96 (45.8%) |
| Numerical fit failures | 0 | 0 | 0 |
| Accepted actions / attempts | 110/110 | 120/120 | 120/120 |
| Experiments | 12 | 12 | 12 |
| Simulated experiment seconds | 164 | 144 | 144 |
| Conditional discrimination available / cases | 5/12 | 0/12 | 0/12 |
| Competitive-set narrowing / available | 0/5 | Not available | Not available |

Muse used 12 fewer fits and 68 fewer starts than matched, but these counts do not measure diagnostic information. The frozen discrimination rule needs at least two identical templates fitted before and after an experiment; zero eligible narrowing does not prove experiments were useless. It measures only gap≤6 competitive-set size, depends on converged-fit availability and is not independent physical information gain. Matched experiments occur first, so its metric is structurally unavailable.

## Safety

All runs used **simulation advisory** safety. All 12 proposals per policy reached screening and received a predictive would-reject-under-enforcement warning; none was unassessed. Experiments nevertheless executed. Muse had observed corridor excursions in 11/12 cases (91.7%), matched and reference each 4/12 (33.3%). There were **zero guard interventions** in every policy. Maximum absolute observed cross-track position during Muse experiments was approximately 6.73 m. These are adverse advisory outcomes, not safely contained events. Warnings neither imply real enforcement nor establish safe experiment choice. No hardware execution or configuration changes occurred.

## Usage, latency and authorization

| Resource | Actual Muse usage | Authorized ceiling |
|---|---:|---:|
| Real cases | 12 | 12 |
| Model requests | 110 | 12/case, at most 144 total |
| Measured input tokens (cached included) | 2,387,428 | 350,000/case soft; 4,200,000 campaign soft |
| Cached input tokens (subset of input) | 39,828 | Reported separately |
| Output tokens, including reasoning | 39,641 | 4,096/request; 32,768/case |
| Reasoning tokens (subset of output) | 21,494 | Included above |
| Total reported tokens | 2,427,069 | Input plus output |
| Host charged/reserved output, sum | 39,641 | 393,216 campaign; next-case full ceiling reserved before start |
| Largest case input | 290,668 | 350,000 soft |
| Largest request output | 984 | 4,096 |
| Largest case cumulative JSON request bytes | 272,568 | 1,000,000 |

All per-case/action/numerical/time ceilings and pre-case aggregate admission checks passed. The sum of twelve full case output ceilings is 393216; actual reported output and host charged reservation were both 39641 because every request reported usage. No unknown-usage fallback was needed. Cached tokens are not additional input, and reasoning is not additional output.

Muse investigation time totaled 1155.74 s (19.26 min), including its laboratory work. Per-case min/median/max: 77.71 / 89.28 / 131.61 s. Provider-call latency totaled 1124.61 s; request min/median/max: 2.96 / 9.86 / 21.53 s. Matched totaled 59.13 s and reference 14.27 s. Entire three-policy case execution totaled 1230.12 s (20.50 min). These are sequential elapsed sums on this runtime, not provider throughput guarantees.

Provider-verified pricing was unavailable. The $15 monetary target could not be enforced, and **no dollar cost is asserted**. Execution used the explicitly authorized token/request fallback, not the dashboard credit balance. This environment cannot verify external billing-dashboard changes. No extra comparisons, sweeps or repeated investigations were run.

### Per-case reported usage

Input includes cached tokens; output includes reasoning.

| Case | Input | Cached | Output | Reasoning |
|---|---:|---:|---:|---:|
| E01 | 290,668 | 348 | 4,201 | 2,571 |
| E02 | 199,520 | 0 | 3,721 | 2,167 |
| E03 | 151,974 | 232 | 2,798 | 1,281 |
| E04 | 221,629 | 348 | 3,137 | 1,840 |
| E05 | 225,246 | 812 | 2,922 | 1,415 |
| E06 | 172,199 | 1,044 | 2,985 | 1,458 |
| E07 | 259,853 | 928 | 4,314 | 2,650 |
| E08 | 180,149 | 7,316 | 2,809 | 1,298 |
| E09 | 167,279 | 7,084 | 3,339 | 1,985 |
| E10 | 145,724 | 1,044 | 2,773 | 1,472 |
| E11 | 174,197 | 7,200 | 3,706 | 1,760 |
| E12 | 198,990 | 13,472 | 2,936 | 1,597 |

## Validation and artifacts

Before any holdout inference: 368 Python tests passed; nine frontend test files passed; five exporter tests passed; TypeScript/Vite production build passed with the existing chunk-size advisory. Tests exercised frozen manifests, seed isolation, reproducibility, genuine numerical laboratory dispatch, matched initial evidence, experiment/noise matching, stale fits, voluntary versus host closure, privacy allowlists, budgets, provider stops, corrupt/incomplete checkpoints, resume skipping and duplicate prevention.

After inference: the same 368 Python tests, nine frontend test files, five exporter tests and production build passed again. All 12 checkpoint hashes, immutable manifest file/body, frozen sources/runtime, 36 closed public ledgers, evidence references, Muse provenance and laboratory limits validated. All 36 records imported through the existing frontend validator and generated deterministic Markdown artifacts twice; no configuration-change export was produced. Actual continuation linkage and all 110 lossless result presentations validated. The complete scientific case records and a separate consolidated private scientific evaluation remain outside the checkout; only source, tests, protocol and this sanitized report are committed.

## Interpretation and remaining limitations

The milestone completed the frozen evaluation, but it did not establish a scientific advantage for Muse. In this exact sample it matched a modest deterministic policy on representable exact findings, trailed it by one whole-family finding, abstained more often, consumed fewer fits, and incurred greater latency and more advisory excursions. Muse’s tentative compound constituent findings avoided the matched policy’s supported-but-incomplete tags; without an independent identifiability/confidence reference this is descriptive caution, not a proven calibration advantage.

Twelve balanced simulated cases give wide uncertainty and just two examples per stratum. The main fixed comparator has restricted policy coverage and is not an optimized deterministic ceiling. The unchanged fixed reference’s systematic post-experiment stale-fit limitation is known and cannot support a strong Muse superiority claim. Registry mismatch, scalar finalization and common simulator/fitter assumptions constrain interpretation. No deployment prevalence, hardware reliability, cost advantage, unique causal identifiability or correctly calibrated abstention is established. Future revisions require new versioned protocols and fresh holdouts; these cases must not be reused as untouched final tests after this analysis.

## Frozen file fingerprints

Full nonsecret source map below; candidate commit fixes the corresponding history. Private manifest contents and answer keys are not published.

| File | SHA-256 |
|---|---|
| `MUSE_EVALUATION_PROTOCOL.md` | `82f97eb236b32993e5553c9125661b91738b448d060588e328704dd3389c43eb` |
| `evaluate_active.py` | `07ebc992d7b859a1a21e6d8077ae2cf9c7ce32f0ffe009121c524cbb5b7fbd79` |
| `evaluate_muse.py` | `f874afa5d8b548b4086330a63c92f2f6bd927be8038c53262a570bc0946c380b` |
| `frontend/export_records.py` | `9f2d6e93c2ede353549a1d042d93777ca6e6818e6b8e22509632023de51b655d` |
| `frontend/src/controller.ts` | `28931577cb97a05da9e7f3a9dae4eec5596fc9eeae7f2f24e74c5a43abccecdb` |
| `frontend/src/muse-provenance.ts` | `07649c065193efac9809c3507d809ec9967ee01f0a37b7bb7aeceb2348f24a92` |
| `frontend/src/records.ts` | `7b85c3770eb95f28090d980c61f84c03df19b7e13af92fad70b769a27d21eebe` |
| `nautilus/__init__.py` | `4cb13fd8ba5835cf850c0c7ecfaa0018da2e2875c82b906fa20bedba0e536615` |
| `nautilus/configuration_evaluation.py` | `c05ebe174f07ca5b277d609629115c874fc2e707f60d7262a60d662691b77282` |
| `nautilus/controller_context.py` | `2682806d957a4723fdfefb5e27370221143069dcf6d17e2cdae8dd4fa5dc8826` |
| `nautilus/diagnosis.py` | `48df0d2cb2ca60b1b9522c045d9d75b5aced59eeca7d509ee23b98a9a0738a22` |
| `nautilus/experiments.py` | `09251267052208030bead5773ffa284ce0d7c0097e2d74cc00d1e66724030381` |
| `nautilus/host_evaluation.py` | `f4bb7398aeb2cdcdbdef22d33000ae2df78cd94c76c3f9dfa81095fadcd04a48` |
| `nautilus/investigation.py` | `e56e2e686cc1ce6c97b876e5ee8a23908cc8aa68b57961a9c13141b002f70cc3` |
| `nautilus/investigator.py` | `42ccf11746696d5c1d9c5882c09aab6fa8c4c0aa76d737633c170beee267b536` |
| `nautilus/lab_safety.py` | `3f2b327e8b04eff2a71b21e73fb0545676c5a14bd647e87039d598b4031f20da` |
| `nautilus/laboratory.py` | `e57f863cb165244cef8ee9890ec584869bf18397a479a25d696350c1661d048a` |
| `nautilus/muse.py` | `3f60f6ba4693ac56f75321981d16adb3f0831a930ed1b2fe6c96d40b140ed774` |
| `nautilus/muse_context.py` | `1b40b1344bda44cb9f5b58d587cb9b63621d919222e03c15514219146ebbb49c` |
| `nautilus/muse_diagnostic.py` | `b532e2d59c41e718d7354a536a58a87ce385793acbad38d778bb00f497ed0859` |
| `nautilus/muse_investigator.py` | `78d56c7dfdcf2125269591be951ffcf89a951af406f8a729e4df1a0d7fb5ddd9` |
| `nautilus/protocol.py` | `5395a8c0b867ad053a13349627d8e9a960d78dd55be7bfe5011a865e69e97cbe` |
| `nautilus/reliability.py` | `e5c842df293971f8e31894628327be10b3e0d3c680025a9a42f67b5c8dea9b3e` |
| `nautilus/scenarios.py` | `231a75299aa7d410c74f02e617aeda6913e5a2463b6664951816697bc7617b93` |
| `nautilus/simulator.py` | `c4f5035d81bc51778ba0447b794541af0d6cb49c3da135742a8f9d1c821ef074` |
| `nautilus/supervisor.py` | `1b67022d48b6ada4548ef78c5e6ac6c88122b5927151370c4737ca0069b0aca0` |
| `nautilus/v2_context.py` | `d4fb10dea869758aac7bba7153b77838b3fa9a094b48fb8df1615f1f1b4addb0` |
| `nautilus/v2_experiments.py` | `f7118536a6d0b6a0bf15dcc39bd00eac2fa560b47fee96ab622721df8e5c6a1d` |
| `nautilus/v2_models.py` | `be28b3d2734e573ba4fdf2be0a134fcf30544f9ecff8604a2a4da73460ddfbc2` |
| `nautilus/v2_tools.py` | `c2c243a2cac9417e58347ec55fe9c509d361e5d44c51aed819e617598dcdc14a` |
