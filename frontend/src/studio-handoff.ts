import type {Investigation} from './records.ts';

/**
 * Public-only evidence handed from a verified investigation to Policy Studio.
 * Built from the public ledger alone: no hidden fault truth, no private evaluator
 * results and no simulator internals. Hypotheses stay labelled as hypotheses.
 */
export type InvestigationHandoff = {
  schema_version: 'nautilus.studio-handoff.v1';
  reproducibility: {run_id: string; source_kind: string; ledger_head: string | null; events: number};
  observations: {episodes: number; evidence_refs: string[]; max_abs_observed_y_m: number | null};
  hypotheses: {
    hypothesis: string;
    converged: boolean;
    parameters: Record<string, number>;
    weighted_rmse: number | null;
    identifiability: {rank: number | null; condition: number | null; qualification: string | null};
    evidence_refs: string[];
    status: 'candidate_hypothesis';
  }[];
  conclusion: {diagnosis: string | null; confidence: string | null; ambiguity_statement: string | null;
    evidence_refs: string[]; status: 'recorded_conclusion_not_proof'} | null;
  limitations: string[];
};

const num = (x: unknown): number | null => (typeof x === 'number' && Number.isFinite(x) ? x : null);
const str = (x: unknown): string | null => (typeof x === 'string' ? x.slice(0, 200) : null);
const obj = (x: unknown): Record<string, unknown> | null =>
  typeof x === 'object' && x !== null && !Array.isArray(x) ? (x as Record<string, unknown>) : null;

export function studioHandoff(record: Investigation): InvestigationHandoff {
  const events = record.events as Array<Record<string, unknown>>;
  const observationEvents = events.filter(e => e.type === 'observation');
  const observationRefs = observationEvents.map(e => String(e.hash));
  let maxY: number | null = null;
  for (const e of observationEvents) {
    for (const row of (e.observations as Array<Record<string, unknown>>) ?? []) {
      const y = num(row.observed_y_m);
      if (y !== null) maxY = maxY === null ? Math.abs(y) : Math.max(maxY, Math.abs(y));
    }
  }
  const fitted = events.filter(e => e.type === 'fit' && obj(e.report)).map(e => {
    const report = e.report as Record<string, unknown>;
    const ident = obj(report.identifiability) ?? {};
    const parameters: Record<string, number> = {};
    for (const [k, v] of Object.entries(obj(report.parameters) ?? {})) {
      const n = num(v);
      if (n !== null) parameters[k] = n;
    }
    const refs = Array.isArray(report.evidence_refs) ? report.evidence_refs.map(String) : observationRefs;
    return {
      hypothesis: str(report.hypothesis) ?? 'unnamed hypothesis',
      converged: report.converged === true,
      parameters,
      weighted_rmse: num(report.weighted_rmse),
      identifiability: {rank: num(ident.rank), condition: num(ident.condition), qualification: str(ident.qualification)},
      evidence_refs: refs,
      status: 'candidate_hypothesis' as const,
    };
  });
  const latest = new Map(fitted.map(h=>[h.hypothesis,h]));
  const hypotheses=[...latest.values()].sort((a,b)=>(a.weighted_rmse??Infinity)-(b.weighted_rmse??Infinity)).slice(0,4);
  const finalized = [...events].reverse().find(e => e.type === 'finalized');
  const diagnosis = obj(finalized?.diagnosis);
  const conclusion = diagnosis ? {
    diagnosis: str(diagnosis.hypothesis),
    confidence: str(finalized?.confidence) ?? str(diagnosis.confidence),
    ambiguity_statement: str(finalized?.ambiguity_statement) ?? str(diagnosis.ambiguity_statement),
    evidence_refs: Array.isArray(diagnosis.evidence_refs) ? diagnosis.evidence_refs.map(String) : [],
    status: 'recorded_conclusion_not_proof' as const,
  } : null;
  const limitations = [
    'Hypotheses are candidate explanations ranked by fit, not proven causes.',
    'Identifiability limits apply: parameters may trade off against each other.',
    'Measured tracking error is evidence of a mismatch, not confirmed hardware fault.',
  ];
  if (!hypotheses.length) limitations.push('No numerical fit was recorded for this investigation.');
  return {
    schema_version: 'nautilus.studio-handoff.v1',
    reproducibility: {
      run_id: record.file.run_id,
      source_kind: record.file.source_kind,
      ledger_head: record.events.at(-1)?.hash ?? null,
      events: record.events.length,
    },
    observations: {episodes: observationRefs.length, evidence_refs: observationRefs, max_abs_observed_y_m: maxY},
    hypotheses,
    conclusion,
    limitations,
  };
}
