/**
 * Session history: experiments and paired trials produced by the server during this browser
 * session. It lives only in memory. Nothing here is persisted, uploaded or presented as an
 * archive; the Experiments page says so explicitly.
 */
import type {Observation, SimulationRequest} from './simulation-api.ts';

export type SessionExperiment = {
  id: string;
  kind: 'simulation' | 'investigation';
  request: SimulationRequest;
  /** Server job identifier for investigations; null for direct simulations, which have none. */
  serverId: string | null;
  diagnosis: string | null;
  samples: number;
  durationS: number;
  peakM: number;
  rmsM: number;
  finishedAt: string;
};

export type SessionTrial = {
  id: string;
  fingerprint: string;
  outcome: string;
  meanRmsDifferenceM: number | null;
  scenarios: number;
  finishedAt: string;
};

export type Session = {experiments: SessionExperiment[]; trials: SessionTrial[]};

export const initialSession = (): Session => ({experiments: [], trials: []});

const escapeText = (x: unknown) => String(x ?? 'n/a').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]!));

/** Deterministic short identifier from the request, so the same experiment reads the same. */
export function sessionId(prefix: string, value: unknown): string {
  const text = JSON.stringify(value);
  let hash = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) hash = Math.imul(hash ^ text.charCodeAt(i), 0x01000193) >>> 0;
  return `${prefix}-${hash.toString(16).padStart(8, '0')}`;
}

export function summarizeObservations(observations: Observation[]): {peakM: number; rmsM: number; samples: number; durationS: number} {
  if (!observations.length) return {peakM: 0, rmsM: 0, samples: 0, durationS: 0};
  const ys = observations.map(o => o.observed_y_m);
  const peakM = Math.max(...ys.map(Math.abs));
  const rmsM = Math.sqrt(ys.reduce((a, y) => a + y * y, 0) / ys.length);
  return {peakM, rmsM, samples: observations.length, durationS: observations[observations.length - 1].time_s - observations[0].time_s};
}

export function recordExperiment(session: Session, experiment: SessionExperiment): Session {
  return {...session, experiments: [experiment, ...session.experiments].slice(0, 50)};
}

export function recordTrial(session: Session, trial: SessionTrial): Session {
  return {...session, trials: [trial, ...session.trials].slice(0, 50)};
}

const num = (value: number | null | undefined, digits = 3) => typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : 'n/a';

export function experimentsMarkup(session: Session): string {
  const note = '<p class="muted"><b>Session only.</b> These results exist in this browser tab and are lost on reload. Nothing is saved to a server or archive. Download a report to keep them.</p>';
  if (!session.experiments.length) {
    return `<section class="empty-state" aria-label="No experiments yet"><h3>No experiments in this session</h3>${note}<p>Run a simulation in the Workspace or start the example experiment from Overview. Each run appears here with its parameters and results.</p></section>`;
  }
  const rows = session.experiments.map(e => {
    const s = e.request.scenario;
    return `<tr><td>${escapeText(e.kind === 'simulation' ? 'Simulation' : 'Investigation')}</td><td><code>${escapeText(e.id)}</code>${e.serverId ? ` <span class="muted">job ${escapeText(e.serverId.slice(0, 12))}</span>` : ''}</td><td>${num(s.current_y)} m/s · η port ${num(s.port_efficiency, 2)} · η stbd ${num(s.starboard_efficiency, 2)} · bias ${num(s.heading_bias_rad, 2)} rad · seed ${escapeText(e.request.seed ?? 42)}</td><td>${num(e.peakM)}</td><td>${num(e.rmsM)}</td><td>${escapeText(e.diagnosis ?? 'n/a')}</td><td>${escapeText(e.finishedAt)}</td></tr>`;
  }).join('');
  return `<section aria-label="Session experiments">${note}<div class="table-wrap"><table><thead><tr><th>TYPE</th><th>RUN ID</th><th>SCENARIO</th><th>PEAK · m</th><th>RMS · m</th><th>DIAGNOSIS</th><th>FINISHED</th></tr></thead><tbody>${rows}</tbody></table></div></section>`;
}

export function trialsMarkup(session: Session): string {
  if (!session.trials.length) return '<p class="muted">No paired Policy Studio trials in this session.</p>';
  const rows = session.trials.map(t => `<tr><td><code>${escapeText(t.fingerprint.slice(0, 16))}</code></td><td>${escapeText(t.outcome)}</td><td>${num(t.meanRmsDifferenceM)} m</td><td>${t.scenarios}</td><td>${escapeText(t.finishedAt)}</td></tr>`).join('');
  return `<div class="table-wrap"><table><thead><tr><th>CANDIDATE FINGERPRINT</th><th>OUTCOME</th><th>MEAN RMS CHANGE</th><th>SCENARIOS</th><th>FINISHED</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}
