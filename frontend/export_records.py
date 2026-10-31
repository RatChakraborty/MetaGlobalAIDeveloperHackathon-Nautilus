import argparse,csv,hashlib,json,math
from pathlib import Path

FIELDS=('time_s','observed_y_m','observed_heading_rad','observed_yaw_rate_radps','port_command_n','starboard_command_n')
EVENTS={
'observation':{'observations','origin','execution','fit_rows','request','envelope'},
'fit':{'report','rationale','template','evidence_refs'},
'operator_note':{'text','trust'},'safety':{'request','screen'},
'finalized':{'diagnosis','confidence','stop_reason','numerical_summary','interpretation','ambiguity_statement','scope'},
'rejected':{'reason'},'fit_failure':{'template','method','reason'},'request':{'request'}}
REPORT={'hypothesis','parameters','bounds','converged','status','weighted_sse','weighted_rmse','penalized_score','physical_wrms','command_wrms','evaluations','optimization_attempts','elapsed_s','warnings','episode_lengths','sensitivity_scaled_norm','residual_diagnostics','identifiability','bound_hits','method','evidence_refs','interpretation','physical_finding','healthy_range','relative_score'}


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()


def validate_rows(rows):
    if len(rows)<2:raise ValueError('At least two observations required')
    for row in rows:
        if set(row)!=set(FIELDS) or not all(type(v) in (int,float) and math.isfinite(v) for v in row.values()):raise ValueError('Exactly six finite public channels required')
    if rows[0]['time_s']!=0 or any(b['time_s']<=a['time_s'] for a,b in zip(rows,rows[1:])):raise ValueError('Reset-aligned ordered observations required')


def reject_private(value):
    if isinstance(value,dict):
        for key,item in value.items():
            if any(token in key.lower() for token in ('private','oracle','injected','ground_truth')) or key.lower() in ('truth','faults','plant','controller','correct','injected_value','true_excursion','true_final_speed_mps'):raise ValueError('Private evaluator content in public ledger')
            reject_private(item)
    elif isinstance(value,list):
        for item in value:reject_private(item)


def public_record(source):
    if source.suffix=='.csv':
        with source.open() as f:rows=[{k:float(v) for k,v in row.items()} for row in csv.DictReader(f)]
        validate_rows(rows)
        body={'index':0,'type':'observation','observations':rows,'origin':'Recorded CSV; export-generated evidence reference','previous_hash':None}
        ledger=[{**body,'event_hash':digest(body)}];origin='recorded_simulation_csv';conclusion=None
    else:
        document=json.loads(source.read_text());record=document.get('record',document)
        state=record.get('after',record)
        ledger=state.get('history',state.get('ledger'))
        if not isinstance(ledger,list) or not ledger:raise ValueError('Recorded public history is required')
        origin='recorded_laboratory_history';conclusion=record.get('final')
    previous=None;refs=set();out=[]
    for i,event in enumerate(ledger):
        kind=event.get('type')
        if kind not in EVENTS or set(event)-EVENTS[kind]-{'index','type','previous_hash','event_hash'}:raise ValueError('Unexpected event fields; refusing lossy hash rewriting')
        reject_private(event)
        body={k:v for k,v in event.items() if k!='event_hash'}
        if event['index']!=i or event['previous_hash']!=previous or digest(body)!=event['event_hash']:raise ValueError('Invalid evidence hash chain')
        if kind=='observation':validate_rows(event['observations']);refs.add(event['event_hash'])
        if kind=='fit':
            report=event['report']
            if set(report)-REPORT:raise ValueError('Unsupported numerical report schema')
            if not set(report.get('evidence_refs',event.get('evidence_refs',[])))<=refs:raise ValueError('Unknown fit evidence reference')
        if kind=='finalized' and not set(event['diagnosis']['evidence_refs'])<=refs:raise ValueError('Unknown conclusion evidence reference')
        out.append({'hash':event['event_hash'],'body_canonical':canonical(body)})
        previous=event['event_hash']
    if not refs:raise ValueError('No observations')
    if conclusion is not None:
        reject_private(conclusion)
        if set(conclusion)-EVENTS['finalized'] or not set(conclusion.get('diagnosis',{}).get('evidence_refs',[]))<=refs:raise ValueError('Invalid recorded conclusion')
    return {'recorded_conclusion':conclusion,'schema_version':'nautilus.public-investigation.v1','run_id':hashlib.sha256(source.read_bytes()).hexdigest(),
            'source_kind':origin,'ledger':out,'disclosure':'Public evidence export. Publication requires separate dataset approval.'}


def visualization(source,observed,run_id):
    if source.parent.resolve()!=observed.parent.resolve():raise ValueError('Visualization CSV must be from the same recorded run directory')
    with source.open() as f:raw=list(csv.DictReader(f))
    samples=[{k:float(row[k]) for k in ('time_s','x_m','y_m','heading_rad')} for row in raw]
    if not samples or not all(math.isfinite(v) for row in samples for v in row.values()):raise ValueError('Finite recorded planar samples required')
    with observed.open() as f:times=[float(row['time_s']) for row in csv.DictReader(f)]
    if [r['time_s'] for r in samples]!=times:raise ValueError('Visualization/observation time alignment mismatch')
    reference=None
    metadata=source.parent/'run.json'
    if metadata.exists():
        mission=json.loads(metadata.read_text()).get('mission',{})
        length=mission.get('cable_length_m');width=mission.get('cable_half_width_m')
        if all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in (length,width)):
            reference={'cable_length_m':length,'cable_half_width_m':width,'source':'Recorded mission dimensions; simulator cable centerline convention y=0'}
    return {'reference':reference,'schema_version':'nautilus.visualization-only.v1','run_id':run_id,'label':'Simulator truth · visualization only · never observational evidence','samples':samples}


def write(path,data):
    path=path.resolve();root=Path(__file__).resolve().parent.parent
    if path==root or root in path.parents:raise ValueError('Generated data must remain outside the source repository')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:json.dump(data,f,indent=2,allow_nan=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--visualization-source',type=Path);p.add_argument('--visualization-output',type=Path);a=p.parse_args()
    if bool(a.visualization_source)!=bool(a.visualization_output):p.error('Both visualization arguments required')
    record=public_record(a.source)
    visual=visualization(a.visualization_source,a.source,record['run_id']) if a.visualization_source else None
    write(a.output,record)
    if visual:write(a.visualization_output,visual)
