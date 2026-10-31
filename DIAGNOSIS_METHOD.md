# Public-telemetry diagnosis

Use the measured-state observer explicitly:

```python
from nautilus.diagnosis import FitConfig, diagnose

# rows contains exactly the simulator's six public observation fields.
result = diagnose(rows, config=FitConfig(method="observer", dt_s=0.05))
```

The original `FitConfig()` default remains `method="replay"` so prior experiments
and regression tests retain their meaning. The observer is an opt-in correction,
not a silent change to previously reported experimental methods. Both modes
return the same result schema; `FitResult.method` identifies the prediction task.

## Why the prediction task matters

Free-running replay integrates the recorded noisy closed-loop commands through
a nominal plant. It is exact when the physical model matches. Under discrepancy,
its own yaw and lateral state can drift away from the hidden system, while the
recorded controller actions correct only the hidden system. Optimizing these
long-horizon errors can favor a surrogate fault instead of the actual mechanism.
Changing a score threshold does not repair that prediction error.

The partial measured-state observer performs these steps at each timestamp:

1. Score the predicted y, biased heading and yaw rate against the current public
   measurements. Heading residuals use circular differences.
2. Correct y to observed y, physical heading to observed heading minus the
   candidate bias, and yaw rate to observed gyro rate.
3. Integrate one RK4 step with the recorded commands. Surge and sway velocities
   evolve as latent dynamic states; they are never read from truth or reset using
   hidden information. The x coordinate is neither observed nor scored.

Predictions are therefore causal one-step predictions, **not a free-running
mission trajectory**. They must not be plotted or described as such. Measurements
are used only after scoring their prior prediction. The method does not establish
closed-loop predictive accuracy for a new experiment or a repair.

Known zero initial heading/velocity is an explicit simulator reset assumption.
In particular, the first heading reading is an absolute reference for bias. The
method must not claim the same identifiability for unknown initial heading or
continuous deployment logs. Timestamp zero alone cannot establish a physical reset.

## Objective, noise and comparisons

The loss is a sum of squared sensor residuals divided by configured sensor
standard deviations. For observer modes, residuals after the initial measurement
are additionally divided by sqrt(2): independent noise in successive measured
state corrections and observations contributes approximately twice the sensor
variance. The first measurement retains the original scale because its prediction
comes from the known reset. Process uncertainty, integration effects and temporal
correlations are not fully modeled. This is an approximate innovation score,
not a calibrated likelihood. No seeds or synthetic noise enter optimization.

The numerical ranking adds `k * log(3 * sample_count)`, counting **all** estimated
fault and common nuisance parameters. Scores only compare candidates using the
same method, window, channels and scales. Replay and observer scores describe
different prediction tasks and must not be treated as comparable likelihoods.
Existing ambiguity and fit-adequacy heuristics are unchanged; neither is a
validated confidence threshold. Report raw winners, abstentions, and nominal
false positives separately. Nominal is an explicit candidate with all fault
parameters fixed to no-fault values, not an absence of candidate models.

## Approaches considered

| Approach | Benefit | Limitation / status |
| --- | --- | --- |
| Free-running replay | Preserves full trajectory constraints; no state corrections | Accumulates discrepancy; retained as baseline |
| Partial measured-state observer | Small deterministic correction; no added fitted states or process forcing | Approximate noise covariance; noisy measured states drive latent dynamics; implemented |
| Observer with common bounded physical nuisances | Estimates lag, shared dead zone and drag scale from public evidence | Additional confounding and boundary solutions; experimental comparison mode |
| Full multiple shooting / state estimation | Can estimate latent knot states with measurement and continuity constraints | Requires justified process covariance or continuity penalties, sparse optimization and additional identifiability checks; not implemented |
| Arbitrary time-varying force corrections | Flexible trajectory fit | Can absorb the very faults being diagnosed unless independently constrained; not adopted |

The common physical nuisance envelope is declared in `DISCREPANCY_BOUNDS`. The
diagnosis module never imports `HIDDEN_PLANT`. Every candidate, including nominal,
gets the same envelope; fitted nuisance values are separate from fault parameters
in the result. Bounds are engineering assumptions, not recovered private settings
or uncertainty intervals. A nuisance hitting a bound is reported, not concealed.

Direct multiple shooting introduces state decision variables at shooting nodes
and continuity constraints; see the [CasADi documentation](https://web.casadi.org/docs/#direct-multiple-shooting).
The bounded optimizer used here is documented in [SciPy least_squares](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html).
No extra runtime dependence on CasADi was introduced.

## Evidence boundary and limitations

Inputs must contain exactly the six public fields, start at the documented reset,
and include every command sample at the supplied cadence. No truth object,
injected faults, private plant values, x position or noise seed is accepted.
All candidates use the same regular interval; a final fractional step is excluded
because public telemetry does not distinguish endpoint interpolation from timeout
truncation. Missing intermediate commands are rejected.

Longitudinal current is fixed to zero; its identifiability without x observations
has not been established. Controller and compound faults remain unsupported.
Systematic unknown mechanisms, non-Gaussian noise, unknown resets and missing
telemetry require further validation. The dashboard and any agent integration
remain deferred.

## Private development evaluation

```bash
python -m pytest -q
python evaluate_diagnosis.py --compare --output ../private-results/comparison.json
python evaluate_diagnosis.py --compare --methods observer_discrepancy \
  --nominal-controls 1 --output ../private-results/discrepancy.json
```

These commands regenerate matched public traces using development seeds only.
Injected values are consulted only by the evaluator after fitting. Reports must
stay outside the repository; the CLI refuses in-repository output and refuses
to overwrite existing results. No oracle outputs, parameter-recovery tables or
private reports should be staged for a source commit.
