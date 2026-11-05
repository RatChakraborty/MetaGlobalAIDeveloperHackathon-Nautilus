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
  /** True while the deterministic example investigation runs on the server. */
  exampleBusy?: boolean;
  /** Error text from the last example run, if it failed. */
  exampleError?: string | null;
  /** Pre-rendered recorded Muse engineering trace, or empty when it could not be loaded. */
  recordedMuseMarkup?: string;
  demoAvailable?: boolean;
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
    ? `<div class="session-summary"><div><small>RUNS THIS SESSION</small><b>${experiments.length}</b></div><div><small>PAIRED TRIALS</small><b>${trials.length}</b></div><div><small>LATEST RMS</small><b>${num(latest.rmsM)} m</b></div><div><small>PEAK</small><b>${num(latest.peakM)} m</b></div><div><small>DIAGNOSIS</small><b class="word">${escapeText(human(latest.diagnosis ?? 'n/a'))}</b></div></div>`
    : '<p class="muted">No runs yet in this browser session. The example investigation is free, deterministic and needs no operator token.</p>';
  const recordStatus = options.recordId
    ? `<p class="muted">Loaded public export <code>${escapeText(options.recordId.slice(0, 12))}</code> · ${escapeText(human(options.recordSource ?? 'source not recorded'))}. Ledger integrity is verified in the browser when it loads.</p>`
    : '<p class="muted">No public export loaded. Open one from Run and Investigate to inspect a recorded investigation, or start with the example experiment.</p>';
  return `<section class="overview" aria-label="Overview">
    <div class="overview-hero">
      <div>
        <span class="eyebrow">START HERE</span>
        <h3>Investigate a failure.<br>Test a better controller.</h3>
        <p>Nautilus investigates simulated underwater-robot failures, compares possible causes using numerical evidence, and evaluates controller changes before recommending them.</p>
        <div class="overview-actions">
          <button class="button" type="button" id="start-example" ${exampleDisabled ? 'disabled' : ''}>${options.exampleBusy ? 'Starting investigation…' : 'Start an Investigation'}</button>
        </div>
        <p class="hint" role="status" aria-live="polite">${options.exampleBusy ? 'Deterministic investigation running on the server…' : options.exampleError ? escapeText(options.exampleError) : options.apiEnabled ? 'Live deterministic · seed 42 · no model call' : 'The simulation API is disabled in this build; only recorded exports can be inspected.'}</p>
      </div>
      <ol class="overview-steps">
        <li class="${ranSomething ? 'done' : 'next'}"><small>01</small><b>Run</b><span>Run the example or set your own current, thruster efficiencies and seed.</span></li>
        <li class="${hasInvestigation ? 'done' : ranSomething ? 'next' : ''}"><small>02</small><b>Investigate</b><span>Run the fault investigation and read its ledger, tests and diagnosis.</span></li>
        <li class="${hasInvestigation && !hasTrial ? 'next' : ''}"><small>03</small><b>Engineer</b><span>Edit a controller policy in Policy Studio and validate the source.</span></li>
        <li class="${hasTrial ? 'next' : ''}"><small>04</small><b>Verify</b><span>Run the free paired trial and compare candidate against baseline.</span></li>
        <li class=""><small>05</small><b>Report</b><span>Download the record, comparison and engineering report with their run identifiers.</span></li>
      </ol>
    </div>
    <div class="overview-shortcuts" aria-label="Explore demonstrations"><a class="button secondary" href="#verified-cases">Verified Cases</a><a class="button secondary" href="#recorded-muse">Recorded Meta Muse Engineering</a><button class="button secondary" type="button" ${options.demoAvailable ? 'id="overview-3d-demo"' : 'data-goto="Trajectory"'}>View 3D AUV Demonstration</button></div>${options.demoAvailable ? '' : '<p class="hint">The existing 3D viewer needs an authorized matching recording; this build includes no bundled 3D example.</p>'}
    <section class="how-it-works" aria-label="How Nautilus Works"><h3>How Nautilus Works</h3><dl><div><dt>Simulator</dt><dd>Computes supported underwater-vehicle dynamics.</dd></div><div><dt>Investigator</dt><dd>Tests competing explanations using public telemetry.</dd></div><div><dt>Controller Evaluator</dt><dd>Measures controller changes against a baseline.</dd></div><div><dt>Three.js Viewer</dt><dd>Replays compatible recorded robot motion.</dd></div><div><dt>Meta Muse</dt><dd>Proposes bounded actions that trusted host tools validate and evaluate.</dd></div></dl></section>
    ${caseFilesMarkup({apiEnabled: options.apiEnabled, busy: options.exampleBusy})}
    ${options.recordedMuseMarkup || '<section id="recorded-muse"><h3>Recorded Real Muse — Parameter Engineering</h3><p role="status">The recording has not loaded. Live Muse is not invoked. Reload to retry.</p></section>'}
    <section aria-label="Current session"><div class="section-head"><h3>Current session</h3><span class="eyebrow">MEMORY ONLY · LOST ON RELOAD</span></div>${sessionStatus}<p>Session data stays in memory and may disappear after refreshing. Export a report to keep your results.</p><button class="button secondary" type="button" data-goto="${hasTrial ? 'Reports' : ranSomething ? 'Dashboards' : options.recordId || !options.apiEnabled ? 'Investigator' : 'Simulation Lab'}">${hasTrial ? 'Export the latest report' : ranSomething ? 'Inspect the latest evidence' : options.recordId || !options.apiEnabled ? 'Review a recorded investigation' : 'Configure a run'}</button><details><summary>Technical session details</summary>${recordStatus}${latest ? `<p>Latest run <code>${escapeText(latest.id)}</code></p>` : ''}</details></section>
    <section aria-label="Tools"><div class="section-head"><h3>Where everything is</h3><span class="eyebrow">FIVE MORE DESTINATIONS</span></div><div class="tool-grid">${toolIndex(options.apiEnabled)}</div></section>
    <p class="muted">This is a scientific simulation environment. Controller comparisons are simulation-only and are not a certified safety case. Hypotheses are candidates, never proven causes.</p>
  </section>`;
}
