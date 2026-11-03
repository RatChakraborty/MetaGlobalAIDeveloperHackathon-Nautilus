/**
 * Overview: the starting point for a first-time visitor. It names one concrete experiment,
 * shows what this browser session has produced so far, and links to every destination.
 * Everything shown is derived from the real session or a loaded export; nothing is canned.
 */
import type {Session} from './session.ts';
import {SECTIONS} from './navigation.ts';
import {caseFilesMarkup} from './case-files.ts';

const escapeText = (x: unknown) => String(x ?? 'n/a').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]!));
const num = (value: number | null | undefined, digits = 3) => typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : 'n/a';
const human = (value: unknown) => String(value ?? 'n/a').replaceAll('_', ' ');

export type OverviewOptions = {
  apiEnabled: boolean;
  /** Run identifier of a loaded public export, or null when none is loaded. */
  recordId: string | null;
  recordSource: string | null;
  /** True while the example simulation is running on the server. */
  exampleBusy?: boolean;
  /** Error text from the last example run, if it failed. */
  exampleError?: string | null;
};

function toolIndex(apiEnabled: boolean): string {
  return SECTIONS.filter(section => section.id !== 'overview').map(section => {
    const gated = !apiEnabled && (section.id === 'workspace' || section.id === 'studio');
    return `<article class="tool-card${gated ? ' unavailable' : ''}"><small>${escapeText(section.stage)}</small><h4>${escapeText(section.label)}</h4><p>${escapeText(section.description)}</p>${gated ? '<span class="tag">API disabled in this build</span>' : `<button class="button secondary" type="button" data-goto="${escapeText(section.views[0])}">Open ${escapeText(section.label)}</button>`}</article>`;
  }).join('');
}

export function overviewMarkup(session: Session, options: OverviewOptions): string {
  const experiments = session.experiments;
  const latest = experiments[0];
  const trials = session.trials;
  const ranSomething = experiments.length > 0;
  const hasTrial = trials.length > 0;
  const hasInvestigation = experiments.some(experiment => experiment.kind === 'investigation');
  const exampleDisabled = !options.apiEnabled || options.exampleBusy;
  const sessionStatus = ranSomething
    ? `<div class="session-summary"><div><small>RUNS THIS SESSION</small><b>${experiments.length}</b></div><div><small>PAIRED TRIALS</small><b>${trials.length}</b></div><div><small>LATEST RUN</small><b class="hash">${escapeText(latest.id)}</b></div><div><small>LATEST RMS</small><b>${num(latest.rmsM)} m</b></div><div><small>PEAK</small><b>${num(latest.peakM)} m</b></div><div><small>DIAGNOSIS</small><b class="word">${escapeText(human(latest.diagnosis ?? 'n/a'))}</b></div></div>`
    : '<p class="muted">No runs yet in this browser session. The example experiment below is free, deterministic and needs no operator token.</p>';
  const recordStatus = options.recordId
    ? `<p class="muted">Loaded public export <code>${escapeText(options.recordId.slice(0, 12))}</code> · ${escapeText(human(options.recordSource ?? 'source not recorded'))}. Ledger integrity is verified in the browser when it loads.</p>`
    : '<p class="muted">No public export loaded. Open one from Workspace to inspect a recorded investigation, or start with the example experiment.</p>';
  return `<section class="overview" aria-label="Overview">
    <div class="overview-hero">
      <div>
        <span class="eyebrow">START HERE</span>
        <h3>Run one experiment,<br>then follow the evidence.</h3>
        <p>The example experiment injects a lateral current into the planar simulator. The controller is a small deterministic policy; the run is computed on the server and returned as public telemetry. Nothing is pre-recorded.</p>
        <div class="overview-actions">
          <button class="button" type="button" id="start-example" ${exampleDisabled ? 'disabled' : ''}>${options.exampleBusy ? 'Running example experiment…' : 'Run the example experiment'}</button>
          ${options.apiEnabled ? '<button class="button secondary" type="button" data-goto="Simulation Lab">Adjust the scenario</button>' : ''}
        </div>
        <p class="hint" role="status" aria-live="polite">${options.exampleBusy ? 'Simulation running on the server…' : options.exampleError ? escapeText(options.exampleError) : options.apiEnabled ? 'Free · deterministic · seed 42 · no model call' : 'The simulation API is disabled in this build; only recorded exports can be inspected.'}</p>
      </div>
      <ol class="overview-steps">
        <li class="${ranSomething ? 'done' : 'next'}"><small>01</small><b>Simulate</b><span>Run the example or set your own current, thruster efficiencies and seed.</span></li>
        <li class="${hasInvestigation ? 'done' : ranSomething ? 'next' : ''}"><small>02</small><b>Investigate</b><span>Run the fault investigation and read its ledger, tests and diagnosis.</span></li>
        <li class="${hasTrial ? 'done' : hasInvestigation ? 'next' : ''}"><small>03</small><b>Engineer</b><span>Edit a controller policy in Policy Studio and validate the source.</span></li>
        <li class="${hasTrial ? 'done' : ''}"><small>04</small><b>Evaluate</b><span>Run the free paired trial and compare candidate against baseline.</span></li>
        <li class=""><small>05</small><b>Report</b><span>Download the record, comparison and engineering report with their run identifiers.</span></li>
      </ol>
    </div>
    ${caseFilesMarkup({apiEnabled: options.apiEnabled, busy: options.exampleBusy})}
    <section aria-label="Current session"><div class="section-head"><h3>Current session</h3><span class="eyebrow">MEMORY ONLY · LOST ON RELOAD</span></div>${sessionStatus}${recordStatus}</section>
    <section aria-label="Tools"><div class="section-head"><h3>Where everything is</h3><span class="eyebrow">FIVE MORE DESTINATIONS</span></div><div class="tool-grid">${toolIndex(options.apiEnabled)}</div></section>
    <p class="muted">This is a scientific simulation environment. Controller comparisons are simulation-only and are not a certified safety case. Hypotheses are candidates, never proven causes.</p>
  </section>`;
}
