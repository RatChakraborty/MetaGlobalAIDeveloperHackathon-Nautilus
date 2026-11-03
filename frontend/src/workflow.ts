/**
 * Workflow guidance: which stage a user is in and what to do next. Pure functions so the copy
 * can be unit-tested; nothing here claims a stage succeeded, only where the user can go.
 */
export type StageId = 'simulate' | 'investigate' | 'engineer';

export interface WorkflowState {
  hasRecord: boolean;
  /** True once the user is working in Policy Studio (the engineering stage). */
  inEngineering: boolean;
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
  {id: 'engineer', number: '03', label: 'Engineer', summary: 'Propose a controller change in Policy Studio and test it against the baseline.'},
];

/** The next useful step for the current state, phrased as an instruction the user can follow. */
export function nextStep(state: WorkflowState): {stage: StageId; text: string} {
  if (!state.hasRecord) {
    return state.labAvailable
      ? {stage: 'simulate', text: 'Run a simulation, or open an existing investigation export to begin.'}
      : {stage: 'investigate', text: 'Open a verified investigation export from your computer to begin.'};
  }
  if (!state.inEngineering) {
    return {stage: 'investigate', text: 'Review the evidence, then choose “Open in Policy Studio” to test a controller change.'};
  }
  return {stage: 'engineer', text: 'Run the baseline and a candidate revision in Policy Studio to compare them on the same scenarios.'};
}
