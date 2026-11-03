// Free, deterministic Control Policy Studio endpoints. The server compiles controller source
// into a validated IR and executes it in the real simulator; nothing here sends executable Python.
import {ApiError} from './simulation-api.ts';

export type Metrics = {rms_cross_track_m: number; max_abs_cross_track_m: number; fraction_outside_corridor: number;
  command_saturation_fraction: number; mission_success: boolean; effort_proxy_n_s: number; [key: string]: number | boolean};
export type TrialRow = {scenario_id: string; baseline: Metrics; candidate: Metrics};
export type Gate = {id: string; passed: boolean; observed?: number; threshold?: number; description?: string};
export type Outcome = {label: 'Recommended' | 'Rejected' | 'Inconclusive'; mean_rms_difference_m: number;
  failed_gates: string[]; rationale: string};
export type Trace = {time_s: number[]; y_m: number[]; heading_rad: number[]; port_command_n: number[]; starboard_command_n: number[]};
export type Trial = {policy: {params: Record<string, number>}; source: string; fingerprint: string; part: string;
  rows: TrialRow[]; gates: Gate[]; outcome: Outcome; traces: Record<string, Trace>;
  methodology: {matched: boolean; note: string; split: string}};
export type Baseline = {policy: {params: Record<string, number>}; source: string; fingerprint: string;
  supported: {references: string[]; functions: string[]; limits: {nodes: number; depth: number}}; live_muse: false};
export type MuseStep = {tool: string; arguments: Record<string, unknown>; result?: unknown; error?: string};
export type MuseSession = {final: {decision: string; rationale: string; candidate_id: string | null; budget: Record<string, unknown>} | null;
  stopped: string | null; transcript: MuseStep[]; mock: boolean; live_available: false; model: string; provider_calls: number;
  disclosure: string; budget: Record<string, unknown>;
  results: Record<string, {outcome: Outcome; rows: TrialRow[]}>;
  candidates: Record<string, {rationale: string; params: Record<string, number>; source: string}>};

async function post<T>(base: string, body: Record<string, unknown>): Promise<T> {
  let response: Response;
  try {
    response = await fetch(base + '/api/v1/studio', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  } catch {
    throw new ApiError('The Nautilus API is unreachable.');
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(typeof payload.error === 'string' ? payload.error : `API error ${response.status}`);
  return payload as T;
}

export const studioBaseline = (base: string) => post<Baseline>(base, {action: 'baseline'});
export const studioValidate = (base: string, source: string, params?: Record<string, number>) =>
  post<{valid: boolean; source?: string; error?: string; fingerprint?: string}>(base, {action: 'validate', source, params});
export const studioTrial = (base: string, source: string, params?: Record<string, number>) =>
  post<Trial>(base, {action: 'trial', source, params});
export const studioRobustness = (base: string, source: string, params?: Record<string, number>) =>
  post<{part: string; rows: TrialRow[]; gates: Gate[]; outcome: Outcome; note: string}>(base, {action: 'robustness', source, params});
export const studioMuse = (base: string) => post<MuseSession>(base, {action: 'muse'});

export class StudioError extends Error {}
export const parseParams = (text: string): Record<string, number> => {
  const params: Record<string, number> = {};
  for (const line of text.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const match = /^([a-z_]+)\s*=\s*(-?\d+(?:\.\d+)?(?:e-?\d+)?)$/.exec(trimmed);
    if (!match) throw new StudioError(`Unsupported parameter line: "${trimmed}". Use name = number.`);
    params[match[1]] = Number(match[2]);
  }
  return params;
};
