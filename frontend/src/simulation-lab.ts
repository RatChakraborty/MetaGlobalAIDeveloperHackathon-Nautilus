import {runSimulation, runInvestigation, runMuseInvestigation, ApiError, type Job, type Simulation, type Scenario, type Observation, type SimulationRequest, type MuseRun} from './simulation-api.ts';

export type LabState = {status: 'idle' | 'running' | 'done' | 'error'; message: string; simulation: Simulation | null; job: Job | null; museRun?:MuseRun};

export const initialLab = (): LabState => ({status: 'idle', message: 'Set a disturbance and run it against the simulator.', simulation: null, job: null});

/** Form values, carried across re-renders so results and inputs stay consistent. */
export type LabValues = {current_y: number; port_efficiency: number; starboard_efficiency: number; heading_bias_rad: number; seed: number};

export const DEFAULT_LAB_VALUES: LabValues = {current_y: 1.0, port_efficiency: 1.0, starboard_efficiency: 1.0, heading_bias_rad: 0.0, seed: 42};

/** The overview's example experiment: one controlled lateral current, healthy thrusters. */
export const EXAMPLE_REQUEST = {scenario: {current_y: 1.0, port_efficiency: 1.0, starboard_efficiency: 1.0, heading_bias_rad: 0.0}, seed: 42};

export function labValuesFrom(request: {scenario: Scenario; seed: number}): LabValues {
  return {current_y: request.scenario.current_y ?? 1, port_efficiency: request.scenario.port_efficiency ?? 1,
    starboard_efficiency: request.scenario.starboard_efficiency ?? 1, heading_bias_rad: request.scenario.heading_bias_rad ?? 0, seed: request.seed ?? 42};
}

const escapeText = (x: unknown) => String(x ?? 'n/a').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]!));

export function labMarkup(state: LabState, paidEnabled = false, values: LabValues = DEFAULT_LAB_VALUES): string {
  const busy = state.status === 'running';
  const paidOff = !paidEnabled;
  const diagnosis = state.simulation?.diagnosis ?? state.job?.result?.investigation.outcome;
  const decision = state.job?.result?.investigation.decision;
  const requestNow = state.simulation?.request ?? state.job?.request ?? null;
  const runLine = state.job ? `Investigation job <code>${escapeText(state.job.id.slice(0, 12))}</code> · ${escapeText(state.job.status)}`
    : state.simulation ? `Simulation run · seed ${escapeText(requestNow?.seed ?? values.seed)} · ${state.simulation.observations.length} samples`
    : '';
  const v = (value: number) => escapeText(Number(value).toString());
  return `<section class="lab" aria-label="Simulation lab">
    <div class="lab-panel">
    <form id="lab-form" class="lab-config" novalidate>
      <div class="section-head"><h3>Simulation Configuration</h3><span class="eyebrow">FREE · DETERMINISTIC</span></div>
      <fieldset class="lab-group"><legend>Disturbance</legend>
        <label for="lab-current">Lateral current <span class="unit">(m/s)</span><input id="lab-current" name="current_y" type="number" step="0.1" min="-2.5" max="2.5" value="${v(values.current_y)}" aria-describedby="hint-current"></label>
        <p id="hint-current" class="hint">Range −2.5 to 2.5 m/s. Positive pushes toward port.</p>
      </fieldset>
      <fieldset class="lab-group"><legend>Thruster health</legend>
        <label for="lab-port">Port efficiency <span class="unit">(0.1–1.0)</span><input id="lab-port" name="port_efficiency" type="number" step="0.05" min="0.1" max="1" value="${v(values.port_efficiency)}" aria-describedby="hint-efficiency"></label>
        <label for="lab-starboard">Starboard efficiency <span class="unit">(0.1–1.0)</span><input id="lab-starboard" name="starboard_efficiency" type="number" step="0.05" min="0.1" max="1" value="${v(values.starboard_efficiency)}"></label>
        <p id="hint-efficiency" class="hint">1.0 is a healthy thruster; lower values model a degraded one.</p>
      </fieldset>
      <fieldset class="lab-group"><legend>Heading and reproducibility</legend>
        <label for="lab-bias">Heading bias <span class="unit">(rad)</span><input id="lab-bias" name="heading_bias_rad" type="number" step="0.01" min="-0.8" max="0.8" value="${v(values.heading_bias_rad)}" aria-describedby="hint-seed"></label>
        <label for="lab-seed">Random seed <span class="unit">(integer)</span><input id="lab-seed" name="seed" type="number" step="1" min="0" value="${v(values.seed)}" aria-describedby="hint-seed"></label>
        <p id="hint-seed" class="hint">The same scenario and seed reproduce the same run.</p>
      </fieldset>
      <p class="lab-scenario">Scenario · current ${v(values.current_y)} m/s · η port ${v(values.port_efficiency)} · η stbd ${v(values.starboard_efficiency)} · bias ${v(values.heading_bias_rad)} rad · seed ${v(values.seed)}</p>
      <p id="lab-error" class="lab-error" role="alert"></p>
      <div class="lab-actions">
        <button type="submit" class="primary" data-action="simulate" ${busy ? 'disabled' : ''}>Run Simulation</button>
        <button type="button" data-action="investigate" ${busy ? 'disabled' : ''}>Run Investigation</button>
        <button type="button" class="secondary" data-action="example" ${busy ? 'disabled' : ''}>Load example scenario</button>
      </div>
      <p class="hint">Run Simulation returns public telemetry. Run Investigation additionally selects experiments, runs its tests and records a diagnosis ledger.</p>
    </form>
    <details class="lab-muse">
      <summary>Live Muse investigation <span class="tag">Paid · operator only</span></summary>
      <p class="muted">Uses a paid model call, requires operator authorization and is capped by the server budget. Not available in Preview unless paid execution is enabled.</p>
      <form id="muse-form" class="muse-live">
        <label>Operator token<input name="token" type="password" autocomplete="off" ${paidOff ? 'disabled' : 'required'}></label>
        <button type="submit" data-action="muse" ${busy || paidOff ? 'disabled' : ''}>Run live Muse investigation (paid)</button>
        ${paidOff ? '<p class="hint">Paid execution is disabled on this deployment.</p>' : ''}
      </form>
    </details>
    </div>
    <div class="lab-results" aria-label="Simulation results">
    <p class="lab-status" role="status" aria-live="polite" data-state="${state.status}">${escapeText(busy ? 'Running on the server…' : state.message)}</p>
    ${runLine ? `<p class="lab-run">${runLine}</p>` : ''}
    ${state.simulation || state.job?.result ? resultMetrics(state.simulation?.observations ?? state.job?.result?.observations ?? [], state.simulation?.request ?? state.job?.request) : ''}
    ${diagnosis ? `<div class="lab-result"><h3>Diagnosis: ${escapeText(diagnosis.kind)}</h3>
      <p>Selected: ${escapeText(diagnosis.selected ?? 'none (abstained)')}</p>
      ${diagnosis.competitive.length ? `<p>Competitive: ${escapeText(diagnosis.competitive.join(', '))}</p>` : ''}
      ${diagnosis.reasons.length ? `<ul>${diagnosis.reasons.map(r => `<li>${escapeText(r)}</li>`).join('')}</ul>` : ''}
      ${decision !== undefined && state.job ? `<p>Investigation tests run: ${escapeText(state.job.result?.investigation.tests)}</p>` : ''}
    </div>` : ''}
    ${state.job?.result ? `<h3>Observed lateral deviation</h3><p class="muted">Observed cross-track position from public telemetry · ${state.job.result.observations.length} samples · not a plan-view replay.</p><svg class="lab-trace" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Observed lateral deviation over time"><polyline fill="none" stroke="currentColor" stroke-width="0.8" points="${lateralSeries(state.job.result.observations).points}"/></svg>` : ''}
    ${state.job?.result ? `<h3>Evidence ledger</h3>${timelineMarkup(state.job.result.investigation.ledger)}` : ''}
    ${(state.simulation?.engineering_context||state.job?.result?.engineering_context||state.museRun?.result.engineering_context)?'<button class="button primary" id="engineer-failure" type="button">Engineer this failure</button><p class="muted">Transfer public telemetry, fits and evidence into Policy Studio. Generation inputs stay on the trusted host path.</p>':''}
    <p class="hint">The three-dimensional replay in Workspace replays recorded public telemetry from an export. A simulator run here records planar observations without a world-frame pose, so it is plotted above rather than shown in 3D.</p>
    </div>
  </section>`;
}

export function resultMetrics(observations: Observation[], request?: SimulationRequest): string {
  if (!observations.length) return '';
  const ys = observations.map(o => o.observed_y_m);
  const peak = Math.max(...ys.map(Math.abs));
  const rms = Math.sqrt(ys.reduce((a, y) => a + y * y, 0) / ys.length);
  const duration = observations[observations.length - 1].time_s - observations[0].time_s;
  const s = request?.scenario ?? {};
  const params = [['Lateral current', s.current_y ?? 0, 'm/s'], ['Port efficiency', s.port_efficiency ?? 1, ''], ['Starboard efficiency', s.starboard_efficiency ?? 1, ''], ['Heading bias', s.heading_bias_rad ?? 0, 'rad'], ['Seed', request?.seed ?? 42, '']];
  return `<div class="lab-metrics" aria-label="Simulation metrics">
    <div><small>PEAK CROSS-TRACK</small><b>${peak.toFixed(3)} m</b></div>
    <div><small>RMS CROSS-TRACK</small><b>${rms.toFixed(3)} m</b></div>
    <div><small>SAMPLES</small><b>${observations.length}</b></div>
    <div><small>DURATION</small><b>${duration.toFixed(1)} s</b></div>
  </div>
  <dl class="lab-params" aria-label="Simulation parameters">${params.map(([k, v, u]) => `<div><dt>${escapeText(k)}</dt><dd>${escapeText(Number(v).toString())}${u ? ` ${escapeText(u)}` : ''}</dd></div>`).join('')}</dl>`;
}

const LEDGER_LABELS: Record<string, string> = {
  initial_observation: 'Initial observation',
  experiment_selected: 'Experiment selected',
  experiment_observed: 'Experiment observed',
  experiment_error: 'Experiment error',
  stopped: 'Stopped',
};

export function timelineMarkup(ledger: unknown[]): string {
  if (!ledger.length) return '<p class="muted">No ledger events recorded.</p>';
  const rows = ledger.map(e => {
    const event = e as Record<string, unknown>;
    const type = String(event.type ?? 'unknown');
    const detail = type === 'stopped' ? `reason ${escapeText(event.reason)} · tests ${escapeText(event.tests)}`
      : type === 'experiment_error' ? escapeText(event.error)
      : type === 'initial_observation' || type === 'experiment_observed' ? `diagnosis ${escapeText((event.diagnosis as {kind?: unknown})?.kind)}`
      : '';
    return `<li><b>${escapeText(event.index)}. ${escapeText(LEDGER_LABELS[type] ?? type)}</b> ${detail}<code title="event hash">${escapeText(String(event.event_hash ?? '').slice(0, 12))}</code></li>`;
  });
  return `<ol class="lab-timeline" aria-label="Evidence ledger">${rows.join('')}</ol>`;
}

export function lateralSeries(observations: {time_s: number; observed_y_m: number}[]): {points: string; min: number; max: number} {
  if (!observations.length) return {points: '', min: 0, max: 0};
  const ys = observations.map(o => o.observed_y_m);
  const min = Math.min(...ys), max = Math.max(...ys);
  const t0 = observations[0].time_s, t1 = observations[observations.length - 1].time_s;
  const span = max - min || 1, tspan = t1 - t0 || 1;
  const points = observations.map(o => `${(((o.time_s - t0) / tspan) * 100).toFixed(2)},${(100 - ((o.observed_y_m - min) / span) * 100).toFixed(2)}`).join(' ');
  return {points, min, max};
}

const LIMITS: Record<string, [number, number]> = {current_y: [-2.5, 2.5], port_efficiency: [0.1, 1], starboard_efficiency: [0.1, 1], heading_bias_rad: [-0.8, 0.8], seed: [0, 2147483647]};

// Returns a message for the first invalid field, or null. Limits mirror nautilus_api/schema.py.
export function validateLabForm(form: HTMLFormElement): string | null {
  const data = new FormData(form);
  for (const [key, [lo, hi]] of Object.entries(LIMITS)) {
    const raw = String(data.get(key) ?? '').trim();
    const value = Number(raw);
    if (raw === '' || !Number.isFinite(value)) return `${key.replace(/_/g, ' ')} must be a number.`;
    if (key === 'seed' && !Number.isInteger(value)) return 'Random seed must be an integer.';
    if (value < lo || value > hi) return `${key.replace(/_/g, ' ')} must be between ${lo} and ${hi}.`;
  }
  return null;
}

export function readLabForm(form: HTMLFormElement): {scenario: Scenario; seed: number} {
  const data = new FormData(form);
  const num = (k: string) => Number(data.get(k));
  return {scenario: {current_y: num('current_y'), port_efficiency: num('port_efficiency'), starboard_efficiency: num('starboard_efficiency'), heading_bias_rad: num('heading_bias_rad')}, seed: num('seed')};
}

export async function simulateLab(base: string, request: ReturnType<typeof readLabForm>, set: (s: LabState) => void) {
  set({status: 'running', message: '', simulation: null, job: null});
  try {
    const simulation = await runSimulation(base, request);
    set({status: 'done', message: 'Simulation complete.', simulation, job: null});
  } catch (error) {
    set({status: 'error', message: error instanceof ApiError ? error.message : 'Simulation failed.', simulation: null, job: null});
  }
}

// Paid, protected live Muse run. One synchronous request; the token is passed in at click time only.
export async function museLab(base: string, request: ReturnType<typeof readLabForm>, token: string, set: (s: LabState) => void) {
  set({status: 'running', message: 'Running live Muse investigation (paid)…', simulation: null, job: null});
  try {
    const run = await runMuseInvestigation(base, request, token);
    set({status: 'done', message: `Live Muse investigation complete (paid). Public record returned by the server: ${Object.keys(run.result.public_record ?? {}).length} fields.`, simulation: null, job: null, museRun:run});
  } catch (error) {
    set({status: 'error', message: error instanceof ApiError ? error.message : 'Live Muse investigation failed.', simulation: null, job: null});
  }
}

export async function investigateLab(base: string, request: ReturnType<typeof readLabForm>, set: (s: LabState) => void) {
  set({status: 'running', message: '', simulation: null, job: null});
  try {
    const job = await runInvestigation(base, request, j => set({status: 'running', message: `Investigation ${j.status}…`, simulation: null, job: j}));
    if (job.status !== 'succeeded') throw new ApiError(job.error ?? `Investigation ${job.status}.`);
    set({status: 'done', message: 'Investigation complete.', simulation: null, job});
  } catch (error) {
    set({status: 'error', message: error instanceof ApiError ? error.message : 'Investigation failed.', simulation: null, job: null});
  }
}
