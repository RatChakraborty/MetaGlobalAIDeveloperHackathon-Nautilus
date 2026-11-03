import {runSimulation, runInvestigation, ApiError, type Job, type Simulation, type Scenario} from './simulation-api.ts';

export type LabState = {status: 'idle' | 'running' | 'done' | 'error'; message: string; simulation: Simulation | null; job: Job | null};

export const initialLab = (): LabState => ({status: 'idle', message: 'Set a disturbance and run it against the simulator.', simulation: null, job: null});

const escapeText = (x: unknown) => String(x ?? 'n/a').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]!));

export function labMarkup(state: LabState): string {
  const busy = state.status === 'running';
  const diagnosis = state.simulation?.diagnosis ?? state.job?.result?.investigation.outcome;
  const decision = state.job?.result?.investigation.decision;
  return `<section class="lab" aria-label="Simulation lab">
    <form id="lab-form">
      <label>Lateral current (m/s)<input name="current_y" type="number" step="0.1" min="-2.5" max="2.5" value="1.0"></label>
      <label>Port efficiency<input name="port_efficiency" type="number" step="0.05" min="0.1" max="1" value="1.0"></label>
      <label>Starboard efficiency<input name="starboard_efficiency" type="number" step="0.05" min="0.1" max="1" value="1.0"></label>
      <label>Heading bias (rad)<input name="heading_bias_rad" type="number" step="0.01" min="-0.8" max="0.8" value="0.0"></label>
      <label>Seed<input name="seed" type="number" step="1" min="0" value="42"></label>
      <button type="submit" data-action="simulate" ${busy ? 'disabled' : ''}>Run simulation</button>
      <button type="button" data-action="investigate" ${busy ? 'disabled' : ''}>Run investigation</button>
    </form>
    <p class="lab-status" role="status">${escapeText(busy ? 'Running on the server…' : state.message)}</p>
    ${diagnosis ? `<div class="lab-result"><h3>Diagnosis: ${escapeText(diagnosis.kind)}</h3>
      <p>Selected: ${escapeText(diagnosis.selected ?? 'none (abstained)')}</p>
      ${diagnosis.competitive.length ? `<p>Competitive: ${escapeText(diagnosis.competitive.join(', '))}</p>` : ''}
      ${diagnosis.reasons.length ? `<ul>${diagnosis.reasons.map(r => `<li>${escapeText(r)}</li>`).join('')}</ul>` : ''}
      ${decision !== undefined && state.job ? `<p>Investigation tests run: ${escapeText(state.job.result?.investigation.tests)}</p>` : ''}
    </div>` : ''}
    ${state.job?.result ? `<h3>Observed lateral deviation</h3><p class="muted">Observed cross-track position from public telemetry · ${state.job.result.observations.length} samples · not a plan-view replay.</p><svg class="lab-trace" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Observed lateral deviation over time"><polyline fill="none" stroke="currentColor" stroke-width="0.8" points="${lateralSeries(state.job.result.observations).points}"/></svg>` : ''}
    ${state.job?.result ? `<h3>Evidence ledger</h3>${timelineMarkup(state.job.result.investigation.ledger)}` : ''}
  </section>`;
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
