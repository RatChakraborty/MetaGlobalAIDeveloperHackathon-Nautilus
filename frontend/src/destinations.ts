/**
 * Destination pages for results that already exist: dashboards, the session experiment index
 * and the report export page. Markup only; the run data comes from the real session, a loaded
 * export or the last Policy Studio trial. No placeholder metrics are rendered.
 */
import type {Investigation} from './records.ts';
import type {Session} from './session.ts';
import {experimentsMarkup, trialsMarkup} from './session.ts';
import type {LabState} from './simulation-lab.ts';
import {trialMarkup} from './studio-view.ts';
import type {Trial} from './studio-api.ts';

const escapeText = (x: unknown) => String(x ?? 'n/a').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]!));
const num = (value: number | null | undefined, digits = 3) => typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : 'n/a';

/** Header metrics for Dashboards: which runs the page is describing and where they came from. */
export function dashboardsHeader(session: Session, record: Investigation | null, lab: LabState, trial: Trial | null): string {
  const diagnosis = lab.job?.result?.investigation.outcome ?? lab.simulation?.diagnosis ?? null;
  const last = session.experiments[0];
  return `<div class="metrics" aria-label="Dashboard context">
    <article><small>SESSION RUNS</small><b>${session.experiments.length}</b></article>
    <article><small>LOADED EXPORT</small><b class="hash">${record ? escapeText(record.file.run_id.slice(0, 12)) : 'none'}</b></article>
    <article><small>LAST RUN ID</small><b class="hash">${last ? escapeText(last.id) : 'n/a'}</b></article>
    <article><small>FAULT DIAGNOSIS</small><b class="word">${escapeText(diagnosis ? (diagnosis.selected ?? diagnosis.kind) : 'no investigation yet')}</b></article>
    <article><small>PAIRED TRIAL</small><b class="word">${trial ? escapeText(trial.outcome.label) : 'not run'}</b></article>
  </div>`;
}

/** Fault evidence from the server's investigation, kept separate from the charts. */
export function faultEvidence(lab: LabState): string {
  const diagnosis = lab.job?.result?.investigation.outcome ?? lab.simulation?.diagnosis ?? null;
  if (!diagnosis) {
    return `<section aria-label="Fault evidence"><div class="section-head"><h3>Fault evidence</h3><span class="eyebrow">NO INVESTIGATION YET</span></div><p class="muted">Run an investigation in Workspace to record a diagnosis, its tests and reasons. The dashboards never infer a cause from the plots alone.</p></section>`;
  }
  const investigation = lab.job?.result?.investigation;
  const reasons = diagnosis.reasons?.length ? `<ul>${diagnosis.reasons.map(reason => `<li>${escapeText(reason)}</li>`).join('')}</ul>` : '<p class="muted">No reasons recorded by the server.</p>';
  const competitive = diagnosis.competitive?.length ? `<p>Competitive hypotheses: ${escapeText(diagnosis.competitive.join(', '))}</p>` : '';
  return `<section aria-label="Fault evidence"><div class="section-head"><h3>Fault evidence</h3><span class="eyebrow">FROM THE SERVER INVESTIGATION</span></div>
    <p>Outcome <b>${escapeText(diagnosis.kind)}</b> · selected ${escapeText(diagnosis.selected ?? 'none (abstained)')}${investigation ? ` · ${escapeText(investigation.tests)} tests · ${num(investigation.time_s, 2)} s` : ''}${lab.job ? ` · job <code>${escapeText(lab.job.id.slice(0, 12))}</code>` : ''}</p>
    ${competitive}${reasons}
    <p class="muted">A selected hypothesis is the best-supported explanation under the tested models, not a proven cause. Ledger integrity verifies recorded bytes, not physical correctness.</p></section>`;
}

/** Controller comparison: the last Policy Studio paired trial, else the session's trial index. */
export function controllerComparison(session: Session, trial: Trial | null): string {
  if (trial) {
    return `<section aria-label="Controller comparison"><div class="section-head"><h3>Controller comparison</h3><span class="eyebrow">PAIRED TRIAL · SAME SCENARIOS AND SEEDS</span></div>${trialMarkup(trial)}<p class="muted">Candidate fingerprint <code>${escapeText(trial.fingerprint.slice(0, 16))}</code> · evaluated on the ${escapeText(trial.part)} split. Simulation-only comparison.</p></section>`;
  }
  if (session.trials.length) {
    return `<section aria-label="Controller comparison"><div class="section-head"><h3>Controller comparison</h3><span class="eyebrow">SESSION TRIALS</span></div>${trialsMarkup(session)}<p class="muted">Open Policy Studio to see the full paired table, gates and traces for a new candidate.</p></section>`;
  }
  return `<section aria-label="Controller comparison"><div class="section-head"><h3>Controller comparison</h3><span class="eyebrow">NO TRIAL YET</span></div><p class="muted">No candidate has been compared with the baseline in this session. Policy Studio runs free paired trials on identical scenarios, seeds and noise streams.</p><button class="button secondary" type="button" data-goto="Policy Studio">Open Policy Studio</button></section>`;
}

export function experimentsView(session: Session, record: Investigation | null): string {
  const persisted = record
    ? `<div class="run-info persisted"><span class="eyebrow">LOADED PUBLIC EXPORT</span><strong>${escapeText(record.file.run_id.slice(0, 12))}</strong><span>${escapeText(String(record.file.source_kind).replaceAll('_', ' '))} · ${record.events.length} verified ledger events</span><b class="verified">SHA-256 chain verified on load</b><p class="muted">This export is a file on your device, not a server archive. Re-import it to reopen the investigation.</p></div>`
    : '<p class="muted">No public export is loaded in this browser. Nothing from this session is stored on a server, so there is no other history to show.</p>';
  return `<div class="destinations">
    <section aria-label="Persisted history"><div class="section-head"><h3>Loaded history</h3><span class="eyebrow">PERSISTED ONLY IF YOU KEEP THE FILE</span></div>${persisted}</section>
    <section aria-label="Session experiments"><div class="section-head"><h3>Experiments this session</h3><span class="eyebrow">SESSION ONLY</span></div>${experimentsMarkup(session)}</section>
    <section aria-label="Session trials"><div class="section-head"><h3>Paired trials this session</h3><span class="eyebrow">SESSION ONLY</span></div>${trialsMarkup(session)}</section>
  </div>`;
}

export type ReportOptions = {
  recordLoaded: boolean;
  /** True once Policy Studio has a completed paired trial to report. */
  hasEngineeringReport: boolean;
  /** The last completed paired trial, used to link each report claim to its evidence. */
  trial?: Trial | null;
};

/**
 * Claim-to-evidence table for the last paired trial. Each row states a claim the trial supports
 * and the exact fingerprint, split and gate result it rests on. Claims are shown only when the
 * trial records them; nothing is inferred beyond the recorded outcome.
 */
function claimsMarkup(trial: Trial | null | undefined): string {
  if (!trial) {
    return '<p class="muted">No paired trial has been run in this session. Claims appear here after a Policy Studio trial completes.</p>';
  }
  const failed = trial.outcome.failed_gates;
  const passedAll = failed.length === 0;
  const rows = [
    ['Controller comparison outcome', `${trial.outcome.label} · mean RMS change ${trial.outcome.mean_rms_difference_m.toFixed(3)} m`, `Fingerprint ${escapeText(trial.fingerprint.slice(0, 16))}… · ${escapeText(trial.part)} split`],
    ['Predeclared acceptance gates', passedAll ? `All ${trial.gates.length} gates passed` : `Failed: ${failed.map(escapeText).join(', ')}`, `${trial.gates.length} gates recorded in the trial`],
    ['Scenario outcomes', `${trial.rows.length} scenario(s) compared on identical seeds and noise`, 'Per-scenario metrics are in the engineering report'],
  ];
  return `<table class="claims"><thead><tr><th>Claim</th><th>Result</th><th>Evidence it rests on</th></tr></thead><tbody>${rows.map(([claim, result, evidence]) => `<tr><td>${claim}</td><td>${result}</td><td>${evidence}</td></tr>`).join('')}</tbody></table><p class="muted">Simulation-only evidence. Not hardware validation and not a safety certificate.</p>`;
}

export function reportsView(session: Session, options: ReportOptions): string {
  const sessionRuns = session.experiments.length + session.trials.length;
  return `<div class="destinations">
    <section aria-label="Claims and evidence"><div class="section-head"><h3>Claims and their evidence</h3><span class="eyebrow">FROM THE LAST PAIRED TRIAL</span></div>${claimsMarkup(options.trial)}</section>
    <section aria-label="Report exports"><div class="section-head"><h3>Download</h3><span class="eyebrow">FILES STAY ON THIS DEVICE</span></div>
      <p class="muted">Each file is generated from data already in this browser. The investigation exports require a loaded public record; the engineering report requires a completed Policy Studio trial.</p>
      <div class="report-list">
        <article><h4>Investigation report</h4><p>Recorded ledger, conclusion and provenance as exported.</p><button class="button" type="button" id="report-download-report" ${options.recordLoaded ? '' : 'disabled'}>Download report</button></article>
        <article><h4>Configuration diff</h4><p>Approved controller configuration differences, when the export records them.</p><button class="button secondary" type="button" id="report-download-config" ${options.recordLoaded ? '' : 'disabled'}>Download configuration JSON</button></article>
        <article><h4>Numerical comparison</h4><p>Baseline and candidate metrics with run identifiers, when a host evaluation is loaded.</p><button class="button secondary" type="button" id="report-download-comparison" ${options.recordLoaded ? '' : 'disabled'}>Download comparison JSON</button></article>
        <article><h4>Policy engineering report</h4><p>Candidate source, protocol, per-scenario outcomes, gates and robustness evidence.</p><button class="button secondary" type="button" id="report-download-engineering" ${options.hasEngineeringReport ? '' : 'disabled'}>Download engineering report</button></article>
        <article><h4>Session summary</h4><p>Every experiment and paired trial from this browser session, with run identifiers and the session-only disclaimer.</p><button class="button secondary" type="button" id="report-download-session" ${sessionRuns ? '' : 'disabled'}>Download session JSON</button></article>
      </div>
      <p class="muted">Session summary: ${session.experiments.length} experiment(s) and ${session.trials.length} paired trial(s).</p>
    </section>
    <section aria-label="Report contents"><div class="section-head"><h3>What a report contains</h3><span class="eyebrow">AND WHAT IT DOES NOT</span></div>
      <ul class="report-notes">
        <li>Run identifiers, controller fingerprints, scenario parameters and seeds travel with the numbers.</li>
        <li>Controller comparisons are simulation-only; no hardware execution is recorded.</li>
        <li>Held-out robustness is reported as evidence and never used to select a candidate.</li>
        <li>Hypotheses are candidates; no cause is proven and no formal stability or safety guarantee is claimed.</li>
      </ul>
    </section>
  </div>`;
}
