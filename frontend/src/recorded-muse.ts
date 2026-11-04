/**
 * Recorded Real Muse engineering run. Renders a sanitized replay of an authentic Muse
 * session: each tool event, the candidate Muse proposed, the trusted results and the host decision.
 * Everything comes from the public record file; no paid model call is made and nothing is live.
 */
export type RecordedEvent = {index: number; tool: string; arguments: Record<string, unknown>; result: unknown};
export type RecordedRun = {
  label: string;
  disclosure: string;
  origin: {source_sha256: string; source_file: string; candidate_origin: string; structural_source: boolean};
  final: {candidate_id?: string; decision?: string; rationale?: string};
  usage: {input_tokens?: number; output_tokens?: number; requests?: number; usd_estimate?: number};
  events: RecordedEvent[];
};

const escapeText = (x: unknown) => String(x ?? 'n/a').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]!));
const num = (value: unknown, digits = 3) => typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : 'n/a';

/** One-line description of a tool event, built from its trusted result. */
export function eventSummary(event: RecordedEvent): string {
  const r = (event.result ?? {}) as Record<string, any>;
  switch (event.tool) {
    case 'inspect_controller': return `Baseline controller inspected (fingerprint ${escapeText(String(r.fingerprint ?? 'n/a').slice(0, 12))}).`;
    case 'inspect_diagnosis_evidence': return `Evidence ${escapeText(r.evidence_id)}: baseline RMS ${num(r.baseline_rms_cross_track_m, 2)} m, ${num((r.baseline_fraction_outside_corridor ?? 0) * 100, 1)}% outside corridor.`;
    case 'propose_controller_revision': return `Muse proposed ${escapeText(event.arguments.candidate_id)} from ${escapeText((event.arguments.evidence_refs as string[] | undefined)?.join(', '))}.`;
    case 'validate_controller': return `Trusted validator: ${r.valid ? 'accepted' : 'rejected'} ${escapeText(r.candidate_id)}.`;
    case 'execute_controller_trial': {
      const rms = r.aggregate?.mean_rms_cross_track_m;
      return `Paired trial: mean RMS ${num(rms?.baseline, 3)} m → ${num(rms?.candidate, 3)} m (difference ${num(rms?.difference, 3)} m).`;
    }
    case 'compare_candidate_policies': return `Comparison: ${escapeText(r.better ?? 'no winner recorded')} preferred on the recorded metric.`;
    case 'evaluate_policy_robustness': return `Held-out robustness recorded for ${escapeText(r.candidate_id)} (evidence only, not a proof).`;
    case 'finalize_controller_recommendation': return `Host decision: ${escapeText(r.decision)} for ${escapeText(r.candidate_id)}.`;
    default: return `Tool ${escapeText(event.tool)} executed.`;
  }
}

export function recordedRunMarkup(run: RecordedRun): string {
  const decision = run.final.decision ?? 'unknown';
  const steps = run.events.map(event => `<li class="trace-event" tabindex="0" data-event="${event.index}">
      <small>${String(event.index).padStart(2, '0')}</small>
      <b>${escapeText(event.tool)}</b>
      <span>${eventSummary(event)}</span>
      <details><summary>Arguments and trusted result</summary><pre>${escapeText(JSON.stringify({arguments: event.arguments, result: event.result}, null, 2))}</pre></details>
    </li>`).join('');
  return `<section class="recorded-muse" aria-label="Recorded Real Muse engineering run">
    <div class="section-head"><h3>Muse Engineering — Proposal to Verified Decision</h3><span class="eyebrow">RECORDED REAL MUSE</span></div>
    <p class="muted">${escapeText(run.disclosure)}</p>
    <dl class="trace-facts">
      <div><dt>Candidate</dt><dd>${escapeText(run.final.candidate_id)}</dd></div>
      <div><dt>Origin</dt><dd>Muse-proposed parameter revision</dd></div>
      <div><dt>Structural source</dt><dd>${run.origin.structural_source ? 'yes' : 'not used in this run'}</dd></div>
      <div><dt>Host decision</dt><dd>${escapeText(decision)}</dd></div>
      <div><dt>Model requests</dt><dd>${escapeText(run.usage.requests)}</dd></div>
      <div><dt>Estimated cost</dt><dd>$${num(run.usage.usd_estimate, 2)} (estimate, not billing)</dd></div>
      <div><dt>Record hash</dt><dd class="hash">${escapeText(run.origin.source_sha256.slice(0, 16))}</dd></div>
    </dl>
    <ol class="trace-events" aria-label="Engineering events">${steps}</ol>
    <p class="muted">${escapeText(run.final.rationale)}</p>
  </section>`;
}

export const RECORDED_RUN_URL = '/recorded/muse-engineering-run.json';

export async function loadRecordedRun(fetcher: typeof fetch = fetch): Promise<RecordedRun> {
  const response = await fetcher(RECORDED_RUN_URL);
  if (!response.ok) throw new Error(`recorded run unavailable (${response.status})`);
  const run = await response.json() as RecordedRun;
  if (run.label !== 'Recorded Real Muse') throw new Error('unexpected recorded-run label');
  return run;
}
