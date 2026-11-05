/**
 * Application navigation: six persistent destinations over the five-stage workflow.
 * Pure data and markup so the active section, stage label and keyboard order are testable
 * without a browser. Nothing here performs a request or claims a stage has succeeded.
 */
export type SectionId = 'overview' | 'workspace' | 'dashboards' | 'studio' | 'experiments' | 'reports';

export type ViewName =
  | 'Overview'
  | 'Simulation Lab'
  | 'Investigator'
  | 'Trajectory'
  | 'Dashboards'
  | 'Policy Studio'
  | 'Experiments'
  | 'Reports';

export interface NavSection {
  id: SectionId;
  label: string;
  /** Stage label shown above the page title; the five-stage workflow, plus the start page. */
  stage: string;
  views: readonly ViewName[];
  /** What the destination is for, shown in the Overview tool index. */
  description: string;
}

export const SECTIONS: readonly NavSection[] = [
  {id: 'overview', label: 'Overview', stage: 'Start', views: ['Overview'], description: 'Starting point, example experiment and session status.'},
  {id: 'workspace', label: 'Run and Investigate', stage: '01–02 · Run · Investigate', views: ['Simulation Lab', 'Investigator', 'Trajectory'], description: 'Run a simulation, open a verified record, replay recorded telemetry.'},
  {id: 'dashboards', label: 'Evidence', stage: '02 · Investigate', views: ['Dashboards'], description: 'Measured channels, fit evidence, fault diagnosis and controller comparisons.'},
  {id: 'studio', label: 'Engineer', stage: '03–04 · Engineer · Verify', views: ['Policy Studio'], description: 'Edit a controller policy, validate it and run free paired trials.'},
  {id: 'experiments', label: 'History', stage: 'Session history', views: ['Experiments'], description: 'Runs and paired trials produced in this session, plus any loaded export.'},
  {id: 'reports', label: 'Reports', stage: '05 · Report', views: ['Reports'], description: 'Download the record, configuration diff, comparison and engineering report.'},
];

/** Views shown as sub-tabs inside the Workspace destination. */
export const WORKSPACE_VIEWS: readonly ViewName[] = ['Simulation Lab', 'Investigator', 'Trajectory'];

export function sectionOf(view: string): NavSection {
  return SECTIONS.find(section => (section.views as readonly string[]).includes(view)) ?? SECTIONS[0];
}

export function defaultView(section: SectionId): ViewName {
  return (SECTIONS.find(entry => entry.id === section) ?? SECTIONS[0]).views[0];
}

export function stageOf(view: string): string {
  return ({'Simulation Lab':'01 · Run',Investigator:'02 · Investigate',Trajectory:'Recorded visualization',Experiments:'Session history'} as Record<string,string>)[view] ?? sectionOf(view).stage;
}

export function isWorkspaceView(view: string): boolean {
  return (WORKSPACE_VIEWS as readonly string[]).includes(view);
}

export function navMarkup(view: string): string {
  const active = sectionOf(view).id;
  const items = SECTIONS.map(section => {
    const current = section.id === active;
    return `<button type="button" data-section="${section.id}" class="${current ? 'active' : ''}"${current ? ' aria-current="page"' : ''}><small>${section.stage}</small>${section.label}</button>`;
  }).join('');
  return `<nav class="app-nav" aria-label="Main navigation"><div class="app-nav-inner">${items}</div></nav>`;
}

export function subnavMarkup(view: string): string {
  if (!isWorkspaceView(view)) return '';
  const items = WORKSPACE_VIEWS.map(name => {
    const selected = name === view;
    return `<button type="button" role="tab" data-tab="${name}" aria-selected="${selected}" class="${selected ? 'active' : ''}">${name}</button>`;
  }).join('');
  return `<nav class="subnav" role="tablist" aria-label="Workspace views">${items}</nav>`;
}

// Route IDs are independent of visitor-facing labels.
export function viewHash(view: string): string {
  const routes: Record<string, string> = {'Overview':'overview','Simulation Lab':'workspace','Investigator':'investigator','Trajectory':'trajectory','Dashboards':'dashboards','Policy Studio':'studio','Experiments':'experiments','Reports':'reports'};
  return '#/' + (routes[view] ?? 'overview');
}
export function viewFromHash(hash: string): ViewName | null {
  const key = hash.replace(/^#\/?/, '').toLowerCase();
  const aliases: Record<string, ViewName> = {'':'Overview',overview:'Overview',workspace:'Simulation Lab','simulation-lab':'Simulation Lab',investigator:'Investigator',trajectory:'Trajectory',dashboards:'Dashboards',evidence:'Dashboards',studio:'Policy Studio','policy-studio':'Policy Studio',engineer:'Policy Studio',experiments:'Experiments',history:'Experiments',reports:'Reports'};
  return Object.hasOwn(aliases,key) ? aliases[key] : null;
}
export function activeStage(view: string): string | null {
  return ({'Simulation Lab':'simulate',Investigator:'investigate',Dashboards:'investigate','Policy Studio':'engineer',Reports:'report'} as Record<string,string>)[view] ?? null;
}
