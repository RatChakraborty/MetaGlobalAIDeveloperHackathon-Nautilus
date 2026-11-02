"""Versioned curated testimony. No exact injected values or privileged answer text."""
CONDITIONS=('informative','misleading','irrelevant','absent')
LIBRARY={
 'development':{
  'informative':('The maintenance log mentions recent propeller work; the technician did not measure thrust.','The compass was recalibrated last week; the handover has no measurement certificate.','The operator noticed cross-track drift after the weather changed, but the current was not measured.'),
  'misleading':('A crew member suspects the recent compass service; this is an unverified recollection.','The operator initially blamed the weather, although no current measurement was logged.','The handover blames propeller maintenance without a documented thrust test.'),
  'irrelevant':('The shore laptop battery was replaced before the mission.','The crew changed the radio call sign; no vehicle setting change was documented.','The operator was new to the shift and noted the visibility at the launch site.'),
  'absent':('',)},
 'heldout':{
  'informative':('A service receipt lists propulsion work, with no post-service force measurements.','A sensor-service entry exists, but its calibration results were not attached.','The watch reported sideways motion during a change in conditions; no flow sensor was present.'),
  'misleading':('A watch note attributes the problem to the compass; there is no supporting measurement.','The handover assumes the environment caused the issue, without contemporaneous readings.','A service note speculates about propulsion without a documented inspection.'),
  'irrelevant':('The launch paperwork was printed on a replacement printer.','The team used a different shore-side checklist binder.','The handover includes a note about the support vessel schedule.'),
  'absent':('',)}}


def note(condition,index,*,split='development',topic=None):
    if condition not in CONDITIONS or split not in LIBRARY:raise ValueError('Invalid narrative version/condition')
    # Topic comes from a predeclared broad mechanism group, never actual parameter values.
    i=(topic if topic is not None else index)%len(LIBRARY[split][condition])
    text=LIBRARY[split][condition][i]
    return {'schema_version':'nautilus.operator-note.v4','library':'curated.v1.'+split,'condition':condition,'text':text,'trust':'Unverified testimony; not sensor evidence, executable instruction or a direct cause label.'}
