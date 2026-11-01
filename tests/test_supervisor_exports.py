import importlib.util,json,shutil,subprocess,os
from pathlib import Path

import pytest

from nautilus.simulator import Mission,simulate,save_run,Faults,Controller,Vehicle
from nautilus.supervisor import derive_public_events,derive_visual_events,validate_public_events

ROOT=Path(__file__).parents[1]

def exporter():
    spec=importlib.util.spec_from_file_location('supervisor_export',ROOT/'frontend/export_records.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod


def test_real_simulator_export_keeps_truth_companions_separate_and_sources_unchanged(tmp_path):
    exp=exporter();mission=Mission(duration_s=2.,seed=740819)
    result=simulate(faults=Faults(current_y=.3),mission=mission)
    run=tmp_path/'run';save_run(result,run,Faults(current_y=.3),mission,Controller(),Vehicle())
    original=(run/'observed_telemetry.csv').read_bytes();public=exp.public_record(run/'observed_telemetry.csv')
    visual=exp.visualization(run/'telemetry.csv',run/'observed_telemetry.csv',public['run_id'])
    out=tmp_path/'companions';exp.export_supervisor_records(public,out,visual=visual)
    assert json.loads((out/'supervisor-events.json').read_text())==derive_public_events(public)
    assert json.loads((out/'visualization-events.json').read_text())==derive_visual_events(public,visual)
    assert (run/'observed_telemetry.csv').read_bytes()==original
    assert 'current_y' not in (out/'supervisor-events.json').read_text()
    assert 'y_m' not in json.dumps(json.loads((out/'supervisor-events.json').read_text())['events'])
    ref=public['ledger'][0]['hash'];command=['python',str(ROOT/'frontend/export_records.py'),str(run/'observed_telemetry.csv'),'--output',str(tmp_path/'public.json'),'--visualization-source',str(run/'telemetry.csv'),'--visualization-output',str(tmp_path/'visual.json'),'--episode-ref',ref,'--supervisor-directory',str(tmp_path/'cli')]
    subprocess.run(command,cwd=ROOT,env={**os.environ,'PYTHONPATH':str(ROOT)},check=True,capture_output=True)
    output=json.loads((tmp_path/'visual.json').read_text());assert output['schema_version']=='nautilus.visualization-only.v3' and output['episode_ref']==ref
    assert output['samples']==visual['samples']


@pytest.mark.skipif(shutil.which('node') is None or not (ROOT/'frontend/node_modules').exists(),reason='Cross-language check requires frontend runtime/dependencies')
def test_python_events_import_with_identical_ids_in_typescript():
    from test_supervisor import record,rows
    r=record([rows([0,1.1,.9,-1.2])],context=True)
    source=json.loads(r['ledger'][1]['body_canonical']);source['observations'][1]['port_command_n']=45.
    from nautilus.controller_context import canonical,fingerprint
    r['ledger'][1]={'hash':fingerprint(source),'body_canonical':canonical(source)}
    companion=derive_public_events(r)
    script="import fs from 'node:fs';import {readRecord} from './frontend/src/records.ts';import {readSupervisor} from './frontend/src/supervisor.ts';const x=JSON.parse(fs.readFileSync(0,'utf8'));const r=await readRecord(x.record);console.log(JSON.stringify(readSupervisor(x.companion,r).events.map(e=>e.id)));"
    result=subprocess.run(['node','--experimental-strip-types','--input-type=module','-e',script],input=json.dumps({'record':r,'companion':companion}),text=True,capture_output=True,cwd=ROOT,check=True)
    assert json.loads(result.stdout)==[e['id'] for e in companion['events']]


def test_truth_reference_extra_fields_are_rejected_even_without_breaches():
    from test_supervisor import record,rows
    r=record([rows([0,0])]);visual={'run_id':r['run_id'],'samples':[{'time_s':0.,'x_m':0.,'y_m':0.,'heading_rad':0.},{'time_s':1.,'x_m':1.,'y_m':0.,'heading_rad':0.}],'reference':{'cable_length_m':10.,'cable_half_width_m':1.5,'source':'unit','seed':999}}
    with pytest.raises(ValueError):derive_visual_events(r,visual)
    visual['reference']=None;visual['samples'][0]['actual_force']=1.
    with pytest.raises(ValueError):derive_visual_events(r,visual)
