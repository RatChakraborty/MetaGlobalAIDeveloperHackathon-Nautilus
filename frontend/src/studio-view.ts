/** Control Policy Studio: readable controller source, validated IR, real simulator comparison.
 *
 * The browser never executes controller code. Source is sent to the free Python endpoint, which
 * compiles a whitelisted expression subset into a bounded IR and evaluates it in the simulator.
 * Every number rendered here came back from that server run.
 */
import {studioBaseline, studioMuse, studioRobustness, studioTrial, studioValidate, parseParams,
  type Baseline, type Gate, type MuseSession, type Trial, type TrialRow, type Trace} from './studio-api.ts';

const escapeText = (x: unknown) => String(x ?? 'n/a').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]!));
const fmt = (value: unknown, digits = 3) => typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : 'n/a';
const signed = (value: unknown, digits = 3) => typeof value === 'number' && Number.isFinite(value) ? `${value > 0 ? '+' : ''}${value.toFixed(digits)}` : 'n/a';

export type StudioState = {
  status: 'idle' | 'loading' | 'ready' | 'error';
  message: string;
  baseline: Baseline | null;
  source: string;
  params: string;
  validation: {valid: boolean; error?: string} | null;
  trial: Trial | null;
  robustness: {rows: TrialRow[]; gates: Gate[]; outcome: Trial['outcome']} | null;
  muse: MuseSession | null;
  versions: {label: string; fingerprint: string; outcome: string}[];
};

export const initialStudio = (): StudioState => ({status: 'idle', message: 'Load the baseline controller to begin.',
  baseline: null, source: '', params: '', validation: null, trial: null, robustness: null, muse: null, versions: []});

let state: StudioState = initialStudio();
let container: HTMLElement | null = null;

const METRICS: [keyof TrialRow['baseline'], string, number][] = [
  ['rms_cross_track_m', 'Cross-track RMS · m', 3],
  ['max_abs_cross_track_m', 'Maximum deviation · m', 3],
  ['fraction_outside_corridor', 'Outside corridor', 3],
  ['command_saturation_fraction', 'Command saturation', 3],
  ['effort_proxy_n_s', 'Effort proxy · N·s', 0],
  ['mission_success', 'Mission completed', 0],
];

export function trialMarkup(trial: Trial | null): string {
  if (!trial) return '<p class="muted">No paired trial has run yet. Baseline and candidate are simulated on identical scenarios, seeds and noise streams.</p>';
  const badge = trial.outcome.label === 'Recommended' ? 'verified' : trial.outcome.label === 'Rejected' ? 'failed' : '';
  const rows = trial.rows.map(row => METRICS.map(([key, label, digits]) => {
    const base = row.baseline[key], cand = row.candidate[key];
    const diff = typeof base === 'number' && typeof cand === 'number' ? cand - base : null;
    return `<tr><td>${escapeText(label)}</td><td>${escapeText(row.scenario_id)}</td><td>${esc(base, digits)}</td><td>${esc(cand, digits)}</td><td class="${typeof diff === 'number' && diff > 0 ? 'failed' : ''}">${signed(diff, digits)}</td></tr>`;
  }).join('')).join('');
  return `<div class="metrics" aria-label="Paired comparison summary">
    <article><small>OUTCOME</small><b class="word ${badge}">${escapeText(trial.outcome.label)}</b></article>
    <article><small>MEAN RMS CHANGE</small><b>${signed(trial.outcome.mean_rms_difference_m)} m</b></article>
    <article><small>SCENARIOS</small><b>${trial.rows.length}</b></article>
    <article><small>SPLIT</small><b class="word">${escapeText(trial.part)}</b></article></div>
  <p class="muted">${escapeText(trial.outcome.rationale)}</p>
  ${trial.outcome.failed_gates.length ? `<p class="warning">Failed gates · ${escapeText(trial.outcome.failed_gates.join(', '))}</p>` : ''}
  <div class="table-wrap"><table><thead><tr><th>METRIC</th><th>SCENARIO</th><th>BASELINE</th><th>CANDIDATE</th><th>DIFFERENCE</th></tr></thead><tbody>${rows}</tbody></table></div>
  <h4>Declared gates</h4><ul class="control-gates">${trial.gates.map(gate => `<li><span class="${gate.passed ? 'verified' : 'failed'}">${gate.passed ? 'pass' : 'fail'}</span> ${escapeText(gate.id)}${typeof gate.observed === 'number' ? ` · observed ${fmt(gate.observed)}` : ''}${typeof gate.threshold === 'number' ? ` · threshold ${fmt(gate.threshold)}` : ''}</li>`).join('')}</ul>
  <p class="muted">${escapeText(trial.methodology.note)} Fingerprint ${escapeText(trial.fingerprint.slice(0, 16))}…</p>
  ${humanReviewNote()}`;
}

const esc = (value: unknown, digits: number) => typeof value === 'boolean' ? (value ? 'yes' : 'no') : fmt(value, digits);
const humanReviewNote = () => '<p class="muted">Simulation evidence only. This is not a deployed controller change, a stability proof or a safety certificate.</p>';

function polyline(times: number[], values: number[], scale: (t: number, v: number) => [number, number]): string {
  return times.map((t, i) => { const [x, y] = scale(t, values[i] ?? 0); return `${x.toFixed(2)},${y.toFixed(2)}`; }).join(' ');
}

export function traceMarkup(traces: Record<string, Trace>, keys: readonly ('y_m' | 'port_command_n')[], unit: string, corridor: number | null): string {
  const scenarios = Object.keys(traces);
  if (!scenarios.length) return '<p class="muted">No traces returned.</p>';
  const width = 800, height = 210, left = 70, top = 24;
  return scenarios.map(id => {
    const trace = traces[id];
    const all = trace[keys[0]];
    let low = Math.min(...all, ...(corridor ? [-corridor] : [])), high = Math.max(...all, ...(corridor ? [corridor] : []));
    if (!Number.isFinite(low) || !Number.isFinite(high) || low === high) { low -= 0.5; high += 0.5; }
    const pad = (high - low) * 0.1; low -= pad; high += pad;
    const end = trace.time_s.at(-1) ?? 1;
    const scale = (t: number, v: number): [number, number] => [left + (t / (end || 1)) * (width - left - 20), top + ((high - v) / (high - low)) * (height - top - 34)];
    const grid = [0, 0.5, 1].map(f => { const value = low + f * (high - low); const y = scale(0, value)[1]; return `<line x1="${left}" x2="${width - 20}" y1="${y}" y2="${y}" class="gridline"/><text x="4" y="${y + 4}">${fmt(value, 2)}</text>`; }).join('');
    const corridorLines = corridor === null ? '' : [-corridor, corridor].map(edge => { const y = scale(0, edge)[1]; return `<line x1="${left}" x2="${width - 20}" y1="${y}" y2="${y}" class="gridline" stroke-dasharray="4 3"/>`; }).join('');
    return `<h4>${escapeText(id)} · ${escapeText(unit)}</h4><svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeText(id)} ${escapeText(unit)}">
      ${grid}${corridorLines}
      ${keys.map((key, index) => `<polyline class="trace trace${index}" points="${polyline(trace.time_s, trace[key], scale)}"/>`).join('')}
      <text x="${left}" y="${height - 8}">0 s</text><text x="${width - 90}" y="${height - 8}">${fmt(end, 1)} s</text>
      <text x="${width - 150}" y="14">${keys.map((key, index) => `<tspan class="trace${index}">${key === 'y_m' ? 'cross-track' : 'command'}</tspan>`).join(' ')}</text></svg>`;
  }).join('');
}

export function museMarkup(session: MuseSession | null): string {
  const live = '<p class="muted">Live Muse controller engineering: <strong>disabled</strong> in this deployment. No model request is made and no credits are spent; the workflow below uses a deterministic offline provider against the real simulator.</p>';
  if (!session) return `<section><h3>Muse engineering session</h3>${live}
    <button class="button secondary" data-studio="muse">Run mocked engineering session (free)</button></section>`;
  const final = session.final;
  const badge = final?.decision === 'recommend' ? 'verified' : final?.decision === 'abstain' ? '' : 'failed';
  return `<section><h3>Muse engineering session</h3>${live}
    <div class="metrics"><article><small>DECISION</small><b class="word ${badge}">${escapeText(final?.decision ?? 'stopped')}</b></article>
      <article><small>PROVIDER</small><b class="word">${escapeText(session.model)}</b></article>
      <article><small>TOOL CALLS</small><b>${session.transcript.length}</b></article>
      <article><small>PAID CALLS</small><b>${session.provider_calls}</b></article></div>
    <p>${escapeText(final?.rationale ?? session.stopped ?? 'The session stopped without a recommendation.')}</p>
    <ol class="lab-timeline">${session.transcript.map(step => `<li><b>${escapeText(step.tool)}</b> ${escapeText(summarize(step))}${step.error ? ` <span class="failed">${escapeText(step.error)}</span>` : ''}</li>`).join('')}</ol>
    ${Object.entries(session.candidates).map(([id, candidate]) => `<details><summary>${escapeText(id)} · ${escapeText(Object.entries(candidate.params).map(([k, v]) => `${k}=${v}`).join(' '))}</summary><p>${escapeText(candidate.rationale)}</p><pre>${escapeText(candidate.source)}</pre></details>`).join('')}
    <p class="muted">${escapeText(session.disclosure)} Budget: ${escapeText(JSON.stringify(session.budget))}</p></section>`;
}

function summarize(step: {tool: string; arguments: Record<string, unknown>; result?: unknown}): string {
  if (step.tool === 'execute_controller_trial') {
    const outcome = (step.result as {outcome?: {label?: string}} | undefined)?.outcome;
    return `${String(step.arguments.candidate_id)} → ${outcome?.label ?? 'no outcome'}`;
  }
  if (step.tool === 'propose_controller_revision') return `${String(step.arguments.candidate_id)} · ${String(step.arguments.rationale ?? '')}`;
  if (step.tool === 'evaluate_policy_robustness') {
    const outcome = (step.result as {outcome?: {label?: string}} | undefined)?.outcome;
    return `${String(step.arguments.candidate_id)} · held-out ${outcome?.label ?? 'n/a'}`;
  }
  return typeof step.arguments.candidate_id === 'string' ? step.arguments.candidate_id : 'read evidence';
}

export function studioMarkup(current: StudioState): string {
  const baseline = current.baseline;
  const busy = current.status === 'loading';
  return `<section class="studio" aria-label="Control policy studio">
    <div class="section-head"><h3>Controller policy</h3><span class="eyebrow">CONSTRAINED DSL · NOT PYTHON</span></div>
    <p class="muted">Expressions over public observations only. Supported functions: ${baseline ? escapeText(baseline.supported.functions.join(', ')) : 'loading…'}; references ${baseline ? escapeText(baseline.supported.references.join(', ')) : ''}. Loops, recursion, imports, attribute access and I/O are rejected before execution.</p>
    <label>Controller source<textarea id="studio-source" spellcheck="false" rows="12">${escapeText(current.source)}</textarea></label>
    <label>Parameters<textarea id="studio-params" spellcheck="false" rows="4">${escapeText(current.params)}</textarea></label>
    <div class="workbench-actions">
      <button class="button" data-studio="validate" ${busy || !baseline ? 'disabled' : ''}>Validate</button>
      <button class="button" data-studio="trial" ${busy || !baseline ? 'disabled' : ''}>Run paired trial (free)</button>
      <button class="button secondary" data-studio="robustness" ${busy || !baseline ? 'disabled' : ''}>Held-out robustness</button>
      <button class="button secondary" data-studio="revert" ${busy || !baseline ? 'disabled' : ''}>Revert to baseline</button>
      <button class="button secondary" data-studio="report" ${current.trial ? '' : 'disabled'}>Export engineering report</button>
    </div>
    <p class="lab-status" role="status">${escapeText(current.status === 'loading' ? 'Evaluating on the server…' : current.message)}</p>
    ${current.validation ? (current.validation.valid ? '<p><span class="verified">valid</span> Compiled and validated by the trusted interpreter.</p>' : `<p><span class="failed">invalid</span> ${escapeText(current.validation.error)}</p>`) : ''}
    ${current.versions.length ? `<h4>Policy versions</h4><div class="table-wrap"><table><thead><tr><th>VERSION</th><th>FINGERPRINT</th><th>OUTCOME</th></tr></thead><tbody>${current.versions.map(v => `<tr><td>${escapeText(v.label)}</td><td><code>${escapeText(v.fingerprint.slice(0, 16))}</code></td><td>${escapeText(v.outcome)}</td></tr>`).join('')}</tbody></table></div>` : ''}
    <div id="studio-comparison">${trialMarkup(current.trial)}
    ${current.trial ? traceMarkup(current.trial.traces, ['y_m', 'port_command_n'], 'cross-track · m', 1.5) : ''}
    ${current.robustness ? `<h4>Held-out robustness</h4><p class="muted">Reported as evidence only; it is never used to select a candidate.</p><ul class="control-gates">${current.robustness.rows.map(row => `<li>${escapeText(row.scenario_id)} · baseline ${fmt(row.baseline.rms_cross_track_m)} m · candidate ${fmt(row.candidate.rms_cross_track_m)} m</li>`).join('')}</ul><p>${escapeText(current.robustness.outcome.rationale)}</p>` : ''}</div>
    <div id="studio-muse">${museMarkup(current.muse)}</div>
  </section>`;
}

export function engineeringReport(current: StudioState): Record<string, unknown> {
  const trial = current.trial;
  return {
    schema: 'nautilus.policy-engineering-report.v1',
    generated_for: 'offline controller-engineering evidence; not a deployed change',
    baseline: current.baseline ? {fingerprint: current.baseline.fingerprint, params: current.baseline.policy.params, source: current.baseline.source} : null,
    candidate: trial ? {fingerprint: trial.fingerprint, params: trial.policy.params, source: trial.source} : null,
    protocol: trial?.methodology ?? null,
    outcomes: trial?.rows.map(row => ({
      scenario_id: row.scenario_id,
      baseline: row.baseline, candidate: row.candidate,
      rms_difference_m: row.candidate.rms_cross_track_m - row.baseline.rms_cross_track_m,
    })) ?? [],
    gates: trial?.gates ?? [],
    decision: trial?.outcome ?? null,
    robustness: current.robustness ? {rows: current.robustness.rows, outcome: current.robustness.outcome} : null,
    muse: current.muse ? {model: current.muse.model, mock: current.muse.mock, provider_calls: current.muse.provider_calls,
      final: current.muse.final, transcript: current.muse.transcript.map(step => ({tool: step.tool, arguments: step.arguments, error: step.error ?? null})),
      budget: current.muse.budget} : null,
    versions: current.versions,
    limitations: [
      'Controller evaluation is simulation-only; no hardware execution.',
      'The controller language is a bounded DSL, not Python.',
      'Live Muse controller engineering is disabled; the workflow shown is mocked.',
      'No formal closed-loop stability or safety guarantee is claimed.',
      'Held-out scenarios are reported as evidence and are never used to select a candidate.',
    ],
  };
}

function download(name: string, payload: unknown) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {type: 'application/json'});
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url; anchor.download = name; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

const render = () => { if (container) { container.innerHTML = studioMarkup(state); bind(); } };

function set(patch: Partial<StudioState>) { state = {...state, ...patch}; render(); }

function paramsNow(): Record<string, number> | undefined {
  const text = container?.querySelector<HTMLTextAreaElement>('#studio-params')?.value ?? state.params;
  if (!text.trim()) return undefined;
  return parseParams(text);
}

function sourceNow(): string {
  return container?.querySelector<HTMLTextAreaElement>('#studio-source')?.value ?? state.source;
}

async function run(base: string, action: 'validate' | 'trial' | 'robustness') {
  const source = sourceNow();
  let params: Record<string, number> | undefined;
  try { params = paramsNow(); } catch (error) { set({status: 'error', message: error instanceof Error ? error.message : 'Invalid parameters'}); return; }
  set({status: 'loading', message: '', source, params: container?.querySelector<HTMLTextAreaElement>('#studio-params')?.value ?? state.params});
  try {
    if (action === 'validate') {
      const result = await studioValidate(base, source, params);
      set({status: result.valid ? 'ready' : 'error', message: result.valid ? 'Controller validated.' : 'Validation failed.',
        validation: {valid: result.valid, error: result.error}});
      return;
    }
    if (action === 'trial') {
      const trial = await studioTrial(base, source, params);
      const version = `v${state.versions.length + 1}`;
      set({status: 'ready', message: 'Paired trial complete.', trial, validation: {valid: true},
        versions: [...state.versions, {label: version, fingerprint: trial.fingerprint, outcome: trial.outcome.label}]});
      return;
    }
    const robustness = await studioRobustness(base, source, params);
    set({status: 'ready', message: 'Held-out robustness evaluated.', robustness});
  } catch (error) {
    set({status: 'error', message: error instanceof Error ? error.message : 'Studio request failed.'});
  }
}

function bind() {
  if (!container) return;
  const base = container.dataset.apiBase ?? '';
  container.querySelectorAll<HTMLButtonElement>('[data-studio]').forEach(button => {
    button.onclick = () => {
      const action = button.dataset.studio;
      if (action === 'validate' || action === 'trial' || action === 'robustness') void run(base, action);
      else if (action === 'revert' && state.baseline) set({source: state.baseline.source,
        params: Object.entries(state.baseline.policy.params).map(([k, v]) => `${k} = ${v}`).join('\n'), trial: null, robustness: null, validation: null, message: 'Reverted to the baseline controller.'});
      else if (action === 'report') download('nautilus-policy-engineering-report.json', engineeringReport(state));
      else if (action === 'muse') {
        set({status: 'loading', message: 'Running the deterministic mocked engineering session…'});
        studioMuse(base).then(muse => set({status: 'ready', message: 'Mocked engineering session complete.', muse}))
          .catch(error => set({status: 'error', message: error instanceof Error ? error.message : 'Session failed.'}));
      }
    };
  });
}

export async function mountStudio(root: HTMLElement, base: string) {
  container = root;
  root.dataset.apiBase = base;
  render();
  if (state.baseline) return;
  set({status: 'loading', message: 'Loading the baseline controller…'});
  try {
    const baseline = await studioBaseline(base);
    set({status: 'ready', message: 'Baseline controller loaded. Edit the source and run a paired trial.',
      baseline, source: baseline.source,
      params: Object.entries(baseline.policy.params).map(([k, v]) => `${k} = ${v}`).join('\n')});
  } catch (error) {
    set({status: 'error', message: error instanceof Error ? error.message : 'Could not load the baseline controller.'});
  }
}

export const studioState = () => state;
export const resetStudio = () => { state = initialStudio(); container = null; };
