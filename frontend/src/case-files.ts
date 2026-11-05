/**
 * Case Files: the three verified demonstration records exposed on Overview.
 *
 * Every number quoted here is copied from a retained artifact under
 * frontend/public/evidence/ or from CONTROLLER_AWARE_REPORT.md. The module is pure:
 * it performs no request and cannot start a run. Case A's button is wired in main.ts
 * to the same free deterministic simulator used by the Simulation Lab.
 *
 * Provenance rules:
 * - recorded artifacts stay labelled recorded, even when the numbers are real;
 * - live computations are free and deterministic, never Meta Muse;
 * - no case claims physical cause, a benchmark result, or a browser pass that was
 *   not performed in this environment.
 */

const escapeText = (x: unknown) => String(x ?? 'n/a').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]!));

export type ExecutionMode = 'recorded' | 'live' | 'muse' | 'mock';

export const MODE_LEGEND: readonly {mode: ExecutionMode; label: string; meaning: string}[] = [
  {mode: 'recorded', label: 'Recorded', meaning: 'Stored evidence or a real historical Muse trace; the underlying experiment is not run again.'},
  {mode: 'live', label: 'Live deterministic', meaning: 'Fresh Python computation with supplied inputs. Fixed examples still run the numerical tools; no model call.'},
  {mode: 'muse', label: 'Live Muse', meaning: 'Paid Meta Muse requests through authenticated server-side controls; off by default. Availability is not inferred from this legend.'},
  {mode: 'mock', label: 'Offline scripted', meaning: 'Trusted tools with scripted development choices, not live Meta Muse reasoning. Test fixtures are never scientific evidence.'},
];

export function modeLegendMarkup(): string {
  return `<div class="mode-legend" aria-label="Execution mode legend">
    <strong class="simulation-label">All robot experiments are simulated.</strong>
    <details class="execution-details"><summary>About Execution Modes</summary><div class="mode-definitions">${MODE_LEGEND.map(entry => `<p data-mode="${entry.mode}"><b>${escapeText(entry.label)}</b> — ${escapeText(entry.meaning)}</p>`).join('')}</div></details>
    <span class="mode-labels" aria-hidden="true">Recorded · Live deterministic · Offline scripted · Live Muse</span>
  </div>`;
}

export interface DemoCase {
  id: 'A' | 'B' | 'C';
  title: string;
  mode: string;
  purpose: string;
  headline: string;
  detail: string;
  provenance: string;
  evidence: {file: string; sha256: string; label: string};
  resultIds: string;
  action: 'run-a' | 'studio' | 'none';
  browser: string;
}

export const CASE_A_REQUEST = {
  scenario: {current_y: -0.06, port_efficiency: 1.0, starboard_efficiency: 1.0, heading_bias_rad: 0.0},
  seed: 42,
};

export const DEMO_CASES: readonly DemoCase[] = [
  {
    id: 'A',
    title: 'Ambiguous drift: current or thruster loss?',
    mode: 'Live deterministic computation',
    purpose: 'Show what the evidence does and does not identify.',
    headline: 'No cause selected · three explanations stay competitive',
    detail: 'A small lateral current (−0.06 m/s) is injected. The passive protocol fits five explanations; the best score gap is inside its frozen ambiguity threshold, so kind=ambiguous and selected=null. A post-hoc check of simulation truth puts the maximum lateral offset at 0.31 m; the protocol never sees it.',
    provenance: 'Free simulator, seed 42, 45 s, healthy thrusters, zero heading bias. Classified by the deterministic observer-v1 protocol; no model call.',
    evidence: {file: 'evidence/case-a-passive-fits.json', sha256: 'ea2311eec3925d056bdd1b6282494f196695d1fd72783ff31791a5bfe3080085', label: 'Passive fits & protocol'},
    resultIds: 'protocol fingerprint in evidence file · fits nominal, lateral_current, starboard_degradation',
    action: 'run-a',
    browser: 'Browser workflow not yet run in this environment; run the button and verify the Simulation Lab diagnosis reads ambiguous.',
  },
  {
    id: 'B',
    title: 'Bounded integral compensation',
    mode: 'Live deterministic computation',
    purpose: 'Show a controller change that passes predeclared numerical gates.',
    headline: 'Mean RMS 0.994 → 0.410 m · 8/8 gates pass',
    detail: 'Adding integral_ki=6.0 with integral_limit=1.5 to the baseline policy removes the sustained offset on two development scenarios. Corridor excursion falls from 79.3% to 0%. Nominal RMS rises 0.002 → 0.011 m, inside the declared 0.1 m regression gate. Held-out mean improves 0.493 m and is labelled Recommended. The example is proposed by the host, not by Muse.',
    provenance: 'Studio example revision, development split, matched seeds and noise stream. Two independent requests returned the identical trial fingerprint 585bd1d5…; fixed 8-gate acceptance.',
    evidence: {file: 'evidence/case-b-studio-trial.json', sha256: '410480d8a7bce7090ed8c2026cbab3dd53f0ad883e50d3b41a4c037f9923840e', label: 'Paired trial (8 gates)'},
    resultIds: 'trial 585bd1d5 · robustness 6806f560 · scenarios nominal, current_positive; held-out heading_bias, compound_current_bias_degradation, model_mismatch',
    action: 'studio',
    browser: 'Browser workflow not yet run in this environment; load the example in Policy Studio and repeat validation, trial and robustness.',
  },
  {
    id: 'C',
    title: 'Rejected 14 m lookahead',
    mode: 'Recorded demonstration',
    purpose: 'Show a measured adverse outcome against predeclared gates.',
    headline: 'RMS 5.02 m vs 2.68 m baseline · worse, not better',
    detail: 'A predeclared aggressive candidate (14 m lookahead, versus 7 m baseline and a 3 m alternative) is evaluated on three development scenarios. RMS and outside-corridor fraction increase in every scenario; the 3 m alternative is the only one that removes breaches. The 3 m lookahead study is a separate candidate from Case B and must not be merged with it.',
    provenance: 'Recorded development measurements in CONTROLLER_AWARE_REPORT.md; approved fingerprints retained. Not selected by Muse; no parameter search or held-out data.',
    evidence: {file: 'evidence/case-c-lookahead-14m.json', sha256: '3b08b2eff5d8ee425ce29c283ca00eebc31a14cf7befcb5b3573fb1a6da60438', label: 'Recorded comparison'},
    resultIds: 'candidate 9769d71b · baseline adda0ae6 · 3 m alternative 3add7582',
    action: 'none',
    browser: 'Browser workflow: not applicable. Recorded artifact only; regeneration requires private scenario inputs.',
  },
];

export function caseFilesMarkup(options: {apiEnabled: boolean; busy?: boolean}): string {
  const outcomes = {A:'Several causes remain plausible.', B:'A bounded controller revision improves tracking.', C:'A controller change makes tracking worse.'};
  const descriptions = {A:'Passive numerical ambiguity: the evidence does not select a cause. This is not Muse abstention.', B:'Host-proposed integral compensation passes eight development gates, with a separate held-out check.', C:'Recorded rejection of a 14 m lookahead candidate. Private study inputs prevent full public reproduction.'};
  return `<section id="verified-cases" class="case-files" aria-label="Verified case files">
    <div class="section-head"><h3>Verified Cases</h3><span class="eyebrow">THREE SEPARATE STUDIES</span></div>
    <p class="case-intro">Read the retained evidence, or run the supported deterministic examples. Each study keeps its own provenance.</p>
    <div class="case-grid">
      ${DEMO_CASES.map(item => `<article class="case-card case-${item.id}" aria-label="Case ${item.id}: ${escapeText(item.title)}">
        <div class="case-top"><span class="case-id">CASE ${item.id}</span><span class="case-mode">Recorded evidence${item.action !== 'none' ? ' · live deterministic example available' : ''}</span></div>
        <h4>${escapeText(item.title)}</h4><b class="case-headline">${outcomes[item.id]}</b><p>${descriptions[item.id]}</p>
        <div class="case-actions">
          ${item.action === 'run-a' ? `<button class="button" type="button" id="case-a-run" ${options.apiEnabled && !options.busy ? '' : 'disabled'}>${options.busy ? 'Case A running…' : 'Run case A now'}</button>` : ''}
          ${item.action === 'studio' ? `<button class="button" type="button" data-goto="Policy Studio" ${options.apiEnabled ? '' : 'disabled'}>Open Policy Studio</button>` : ''}
          ${item.action === 'none' ? `<a class="button" href="${item.evidence.file}" target="_blank" rel="noopener">Read recorded rejection</a>` : ''}
        </div>
        ${item.action !== 'none' && !options.apiEnabled ? '<p class="hint">Live example unavailable in this build; recorded evidence remains available below.</p>' : ''}
        <details class="case-details"><summary>Technical Details and evidence</summary>
          <p><b>${escapeText(item.headline)}</b></p><p>${escapeText(item.detail)}</p>
          <dl class="case-meta"><dt>Provenance</dt><dd>${escapeText(item.provenance)}</dd><dt>Result IDs</dt><dd>${escapeText(item.resultIds)}</dd></dl>
          <a href="${escapeText(item.evidence.file)}" target="_blank" rel="noopener">${escapeText(item.evidence.label)}</a>
          ${item.id === 'B' ? '<p><a href="evidence/case-b-studio-robustness.json" target="_blank" rel="noopener">Separate held-out robustness evidence</a></p>' : ''}
          <p class="case-hash">SHA-256 ${escapeText(item.evidence.sha256)}</p>
        </details>
      </article>`).join('')}
    </div>
    <details><summary>Scientific limitations</summary><p class="case-limit">Scores are heuristic, not probabilities; hidden plant truth never reaches the protocol or lab UI, and Case A labels its post-hoc truth check. Case A is passive ambiguity, not an agent or Muse abstention. Case B covers two development scenarios plus three held-out scenarios, not a benchmark. Case C cannot be regenerated from the public tree. Its 3 m alternative is a separate study from Case B.</p></details>
  </section>`;
}
