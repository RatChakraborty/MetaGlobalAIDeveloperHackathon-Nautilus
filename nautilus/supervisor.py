from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math

from .controller_context import canonical, fingerprint, validate_controller_event
from .host_evaluation import fields
from .simulator import OBSERVATION_FIELDS

RULES = {'version':'nautilus.analysis-thresholds.v1','warning_m':1.,'rearm_m':.9,
         'saturation_tolerance_n':1e-6,'saturation_rearm_n':.001}
DESCRIPTIONS = {
    'observed_cross_track_warning':'Observed lateral analysis warning; not a verified physical corridor breach.',
    'command_saturation':'Requested command reached the declared limit; not measured actuator saturation.',
    'guard_stop':'Recorded enforced guard intervention; physical vehicle stopping is not established.',
    'corridor_breach':'Recorded simulator-truth corridor entry; visualization only, never investigator evidence.',
}


def validate_rules(rules):
    fields(rules,RULES)
    if rules['version']!=RULES['version'] or any(type(rules[k]) not in (int,float) or not math.isfinite(rules[k]) for k in RULES if k!='version') or not 0 <= rules['rearm_m'] < rules['warning_m'] <= 10 or not 0 <= rules['saturation_tolerance_n'] < rules['saturation_rearm_n'] <= 1:
        raise ValueError('Invalid analysis thresholds')
    return deepcopy(rules)


def public_source(record):
    allowed={'schema_version','run_id','source_kind','disclosure','recorded_conclusion','ledger'}
    if type(record) is not dict or set(record)-allowed or not {'schema_version','run_id','source_kind','disclosure','ledger'} <= set(record) or record['schema_version'] not in ('nautilus.public-investigation.v1','nautilus.public-investigation.v2') or type(record['run_id']) is not str or not record['run_id'] or type(record['ledger']) is not list:
        raise ValueError('Validated public investigation required')
    episodes=[];previous=None;limit=None;limit_ref=None;contexts=0;past_initialization=False
    for index,item in enumerate(record['ledger']):
        fields(item,('hash','body_canonical'))
        if type(item['body_canonical']) is not str or hashlib.sha256(item['body_canonical'].encode()).hexdigest()!=item['hash']:
            raise ValueError('Invalid public source hash')
        event=json.loads(item['body_canonical'])
        if event.get('type') not in ('controller_context','observation','fit','operator_note','safety','finalized','rejected','fit_failure','request'):
            raise ValueError('Unknown public source event')
        if event['index']!=index or event['previous_hash']!=previous:
            raise ValueError('Invalid public source chain')
        if event['type']=='controller_context':
            contexts+=1
            if contexts>1 or past_initialization or record['schema_version']!='nautilus.public-investigation.v2':raise ValueError('Invalid controller provenance')
            context=validate_controller_event({k:v for k,v in event.items() if k not in ('index','type','previous_hash')})
            low,high=context['interface']['action_bounds_n'];limit=high if high==-low else None;limit_ref=item['hash']
        if event['type']=='observation':
            rows=event['observations']
            if type(rows) is not list or len(rows)<2:raise ValueError('Observation episode required')
            last=-1.
            for row in rows:
                fields(row,OBSERVATION_FIELDS)
                if any(type(v) not in (int,float) or not math.isfinite(v) for v in row.values()) or row['time_s']<=last:raise ValueError('Invalid observation clock or channels')
                last=row['time_s']
            if rows[0]['time_s']!=0:raise ValueError('Episode reset missing')
            episodes.append({'episode_ref':item['hash'],'episode_index':len(episodes),'investigation_index':index,
                             'rows':rows,'execution':event.get('execution')})
        previous=item['hash']
        if event['type'] not in ('observation','operator_note'):past_initialization=True
    if not episodes:raise ValueError('Public observations required')
    return episodes,previous,limit,limit_ref


def _event(record,episode,kind,time,field,rule,threshold,value,units,rule_ref):
    body={'type':kind,'disclosure':'visualization-only' if kind=='corridor_breach' else 'public-derived',
          'run_id':record['run_id'],**{k:episode[k] for k in ('episode_ref','episode_index','investigation_index')},
          'time_s':time,'source_field':field,'rule':rule,'derivation_version':'nautilus.supervisor.v1',
          'threshold':threshold,'supporting_value':value,'units':units,'rule_source_ref':rule_ref,
          'description':DESCRIPTIONS[kind]}
    return {'id':fingerprint(body),'body_canonical':canonical(body)}


def derive_public_events(record, rules=RULES):
    rules=validate_rules(rules);episodes,head,limit,limit_ref=public_source(record);events=[]
    for ep in episodes:
        warning=False;saturated={k:False for k in ('port_command_n','starboard_command_n')}
        for row in ep['rows']:
            value=abs(row['observed_y_m'])
            if not warning and value>=rules['warning_m']:
                events.append(_event(record,ep,'observed_cross_track_warning',row['time_s'],'observed_y_m','observed-warning.v1',rules['warning_m'],row['observed_y_m'],'m',rules['version']));warning=True
            elif warning and value<=rules['rearm_m']:warning=False
            if limit is not None:
                for field in saturated:
                    if not saturated[field] and abs(row[field])>=limit-rules['saturation_tolerance_n']:
                        events.append(_event(record,ep,'command_saturation',row['time_s'],field,'command-limit.v1',limit,row[field],'N',limit_ref));saturated[field]=True
                    elif saturated[field] and abs(row[field])<limit-rules['saturation_rearm_n']:saturated[field]=False
        execution=ep['execution']
        if type(execution) is dict and execution.get('mode')=='simulation_enforced' and execution.get('guard_intervened') is True and execution.get('stop_reason')=='observed_guard':
            t=execution.get('guard_time_s')
            if type(t) not in (int,float) or not math.isfinite(t) or t not in [r['time_s'] for r in ep['rows']]:
                raise ValueError('Recorded guard time is not a discrete observation time')
            events.append(_event(record,ep,'guard_stop',t,'execution.guard_time_s','recorded-guard.v1',None,t,'s',ep['episode_ref']))
    events.sort(key=lambda e:(json.loads(e['body_canonical'])['investigation_index'],json.loads(e['body_canonical'])['time_s'],json.loads(e['body_canonical'])['source_field']))
    return {'schema_version':'nautilus.supervisor-events.v1','run_id':record['run_id'],'source_head':head,
            'rules':rules,'declared_command_limit_n':limit,'events':events}


def validate_public_events(companion,record):
    if companion!=derive_public_events(record,companion.get('rules',{})):
        raise ValueError('Derived events do not match recorded public evidence')
    return deepcopy(companion)


def match_episode(record,visual,episode_ref=None):
    episodes,_,_,_=public_source(record)
    if visual['run_id']!=record['run_id']:raise ValueError('Visualization run mismatch')
    ref=episode_ref or visual.get('episode_ref')
    if ref is None and len(episodes)==1:ref=episodes[0]['episode_ref']
    chosen=next((ep for ep in episodes if ep['episode_ref']==ref),None)
    if chosen is None or [r['time_s'] for r in chosen['rows']]!=[r['time_s'] for r in visual['samples']]:
        raise ValueError('Explicit matching episode required for visualization')
    return chosen


def derive_visual_events(record,visual,episode_ref=None):
    ep=match_episode(record,visual,episode_ref);events=[];outside=False
    for row in visual['samples']:
        fields(row,('time_s','x_m','y_m','heading_rad'))
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in row.values()):raise ValueError('Invalid recorded pose')
    if visual.get('reference') is not None:
        fields(visual['reference'],('cable_length_m','cable_half_width_m','source'))
        width=visual['reference']['cable_half_width_m']
        if type(width) not in (int,float) or not math.isfinite(width) or width<=0:raise ValueError('Recorded corridor required')
        for row in visual['samples']:
            fields(row,('time_s','x_m','y_m','heading_rad'))
            if any(type(v) not in (int,float) or not math.isfinite(v) for v in row.values()):raise ValueError('Invalid recorded pose')
            breach=abs(row['y_m'])>width
            if breach and not outside:events.append(_event(record,ep,'corridor_breach',row['time_s'],'y_m','truth-corridor-entry.v1',width,row['y_m'],'m','recorded-corridor'))
            outside=breach
    source={'samples':visual['samples'],'reference':visual.get('reference')}
    return {'schema_version':'nautilus.visualization-events.v1','run_id':record['run_id'],
            'episode_ref':ep['episode_ref'],'visual_canonical':canonical(source),'events':events}


def validate_visual_events(companion,record,visual):
    if companion!=derive_visual_events(record,visual,companion.get('episode_ref')):
        raise ValueError('Visualization events do not match recorded poses')
    return deepcopy(companion)


def public_event_summary(companion,record):
    validate_public_events(companion,record)
    return {'scope':'Derived interpretations of existing observations, not independent evidence.',
            'rules':deepcopy(companion['rules']),
            'events':[{'id':e['id'],**json.loads(e['body_canonical'])} for e in companion['events']]}
