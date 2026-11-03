// Client for the Nautilus API. Only public scenario knobs are sent; responses are
// public telemetry, protocol outcomes and the investigation ledger.

export type Scenario = {current_y?: number; port_efficiency?: number; starboard_efficiency?: number; heading_bias_rad?: number};
export type SimulationRequest = {scenario: Scenario; seed?: number; duration_s?: number};
export type Observation = {time_s: number; observed_y_m: number; observed_heading_rad: number; observed_yaw_rate_radps: number; port_command_n: number; starboard_command_n: number};
export type Diagnosis = {kind: string; selected: string | null; competitive: string[]; reasons: string[]};
export type Simulation = {request: SimulationRequest; observations: Observation[]; diagnosis: Diagnosis};
export type Job = {id: string; status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'; request: SimulationRequest; result: {observations: Observation[]; investigation: {outcome: Diagnosis; ledger: unknown[]; tests: number; time_s: number; error: string | null; decision: string | null}; protocol_fingerprint: string} | null; error: string | null};

export class ApiError extends Error {}

async function call<T>(base: string, path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(base + path, {...init, headers: {'Content-Type': 'application/json'}});
  } catch {
    throw new ApiError('The Nautilus API is unreachable.');
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(typeof body.error === 'string' ? body.error : `API error ${response.status}`);
  return body as T;
}

export function runSimulation(base: string, request: SimulationRequest): Promise<Simulation> {
  return call<Simulation>(base, '/api/v1/simulations', {method: 'POST', body: JSON.stringify(request)});
}

export async function runInvestigation(base: string, request: SimulationRequest, onUpdate: (job: Job) => void, {intervalMs = 1000, maxPolls = 300} = {}): Promise<Job> {
  const {job} = await call<{job: Job}>(base, '/api/v1/investigations', {method: 'POST', body: JSON.stringify(request)});
  let current = job;
  for (let i = 0; i < maxPolls && (current.status === 'queued' || current.status === 'running'); i++) {
    await new Promise(resolve => setTimeout(resolve, intervalMs));
    current = (await call<{job: Job}>(base, `/api/v1/investigations/${current.id}`)).job;
    onUpdate(current);
  }
  if (current.status === 'queued' || current.status === 'running') {
    throw new ApiError('The investigation did not finish in time. It may still complete on the server.');
  }
  return current;
}
