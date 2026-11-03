import test from 'node:test';
import assert from 'node:assert/strict';
import {SECTIONS, WORKSPACE_VIEWS, defaultView, isWorkspaceView, navMarkup, sectionOf, stageOf, subnavMarkup} from '../src/navigation.ts';

test('the six destinations appear once each, in workflow order', () => {
  assert.deepEqual(SECTIONS.map(s => s.label), ['Overview', 'Workspace', 'Dashboards', 'Policy Studio', 'Experiments', 'Reports']);
  assert.deepEqual(SECTIONS.map(s => s.id), ['overview', 'workspace', 'dashboards', 'studio', 'experiments', 'reports']);
});

test('each destination belongs to exactly one section, and unknown views fall back to Overview', () => {
  for (const section of SECTIONS) for (const view of section.views) assert.equal(sectionOf(view).id, section.id);
  assert.equal(sectionOf('not a view').id, 'overview');
  assert.equal(sectionOf('Simulation Lab').id, 'workspace');
  assert.equal(sectionOf('Experiments').id, 'experiments');
});

test('the five workflow stages are labelled in the navigation, in order', () => {
  const stages = SECTIONS.map(s => s.stage).join(' | ');
  assert.equal(stages, 'Start | 01–02 · Simulate · Investigate | 02 · Investigate | 03–04 · Engineer · Evaluate | 04 · Evaluate | 05 · Report');
  const order = ['Simulate', 'Investigate', 'Engineer', 'Evaluate', 'Report'].map(stage => stages.indexOf(stage));
  assert.deepEqual(order, [...order].sort((a, b) => a - b));
});

test('nav markup marks the active destination and offers all six buttons', () => {
  const markup = navMarkup('Policy Studio');
  assert.equal((markup.match(/data-section=/g) ?? []).length, 6);
  assert.match(markup, /data-section="studio" class="active" aria-current="page"/);
  assert.doesNotMatch(markup, /data-section="dashboards" class="active"/);
  assert.match(markup, /aria-label="Main navigation"/);
});

test('the workspace sub-navigation lists its three views and nothing elsewhere', () => {
  assert.deepEqual([...WORKSPACE_VIEWS], ['Simulation Lab', 'Investigator', 'Trajectory']);
  assert.ok(isWorkspaceView('Investigator'));
  assert.ok(!isWorkspaceView('Reports'));
  assert.equal((subnavMarkup('Trajectory').match(/data-tab=/g) ?? []).length, 3);
  assert.match(subnavMarkup('Trajectory'), /data-tab="Trajectory" aria-selected="true"/);
  assert.equal(subnavMarkup('Dashboards'), '');
});

test('a section opens on its default view and reports its stage', () => {
  assert.equal(defaultView('overview'), 'Overview');
  assert.equal(defaultView('workspace'), 'Simulation Lab');
  assert.equal(defaultView('reports'), 'Reports');
  assert.equal(stageOf('Investigator'), '01–02 · Simulate · Investigate');
  assert.equal(stageOf('Policy Studio'), '03–04 · Engineer · Evaluate');
});
