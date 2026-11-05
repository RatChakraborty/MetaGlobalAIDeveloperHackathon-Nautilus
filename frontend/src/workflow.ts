/**
 * Workflow guidance: which stage a user is in and what to do next. Pure functions so the copy
 * can be unit-tested; nothing here claims a stage succeeded, only where the user can go.
 */
export type StageId = 'simulate' | 'investigate' | 'engineer' | 'evaluate' | 'report';

export interface WorkflowState {
  /** A run exists: either a loaded export or an experiment completed in this session. */
  hasRecord: boolean;
  /** The current evidence is a loaded public export, so the Studio handoff is available. */
  canHandoff?: boolean;
  /** True once the user is working in Policy Studio (the engineering stage). */
  inEngineering: boolean;
  /** True once a candidate has been run against a baseline in Policy Studio. */
  hasTrialResult: boolean;
  labAvailable: boolean;
}

export interface Stage {
  id: StageId;
  number: string;
  label: string;
  summary: string;
}

export const STAGES: readonly Stage[] = [
  {id: 'simulate', number: '01', label: 'Simulate', summary: 'Run a controlled planar experiment and inspect its recorded telemetry.'},
  {id: 'investigate', number: '02', label: 'Investigate', summary: 'Open a verified record, review evidence, fits and trajectory replay.'},
  {id: 'engineer', number: '03', label: 'Engineer', summary: 'Propose a controller change in Policy Studio.'},
  {id: 'evaluate', number: '04', label: 'Evaluate', summary: 'Compare baseline and candidate on the same paired scenarios and robustness set.'},
  {id: 'report', number: '05', label: 'Report', summary: 'Export the record, configuration and evaluation as files.'},
];

/** The next useful step for the current state, phrased as an instruction the user can follow. */
export function nextStep(state: WorkflowState): {stage: StageId; text: string} {
  if (!state.hasRecord) {
    return state.labAvailable
      ? {stage: 'simulate', text: 'Run a simulation, or open an existing investigation export to begin.'}
      : {stage: 'investigate', text: 'Open a verified investigation export from your computer to begin.'};
  }
  if (!state.inEngineering) {
    return state.canHandoff === false
      ? {stage: 'investigate', text: 'Read the run diagnosis and statistics, then open Policy Studio from the navigation to test a controller change.'}
      : {stage: 'investigate', text: 'Review the evidence, then choose “Engineer this failure” (API run) or “Open in Policy Studio” (loaded record) to test a controller change.'};
  }
  if (!state.hasTrialResult) {
    return {stage: 'evaluate', text: 'Run the baseline and a candidate revision in Policy Studio to compare them on the same scenarios.'};
  }
  return {stage: 'report', text: 'Export the evaluation report to keep the results with their configuration and run identifiers.'};
}
