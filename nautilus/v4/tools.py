"""Four original tool names/signatures; opt-in versioned pair/finalization values."""
from copy import deepcopy
import math
from ..muse_investigator import function_tools as legacy_tools,validate_call
from ..v2_tools import parse_json
from ..v2_models import REGISTRY
from .models import PAIRS,validate_pair


def tools(joint_enabled=True):
    out=legacy_tools()
    if not joint_enabled:return out
    propose=out[0]
    for t in out:
        if t['name']=='propose_hypothesis':
            p=t['parameters']['properties'];p['template']={'type':'string','enum':list(REGISTRY)+list(PAIRS)}
            for pair in PAIRS.values():
                for key in ('knobs','bounds'):
                    properties={n:({'type':'number','minimum':s['bounds'][0],'maximum':s['bounds'][1]} if key=='knobs' else {'type':'array','items':{'type':'number'},'minItems':2,'maxItems':2}) for n,s in pair['parameters'].items()}
                    v={'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
                    if v not in p[key]['anyOf']:p[key]['anyOf'].append(v)
        elif t['name']=='finalize':
            p=t['parameters']['properties'];old=p['diagnosis'];parameters=[{'type':'object','properties':{},'required':[],'additionalProperties':False}]
            for spec in REGISTRY.values():
                if spec.parameter:
                    variant={'type':'object','properties':{spec.parameter:{'type':'number','minimum':spec.bounds[0],'maximum':spec.bounds[1]}},'required':[spec.parameter],'additionalProperties':False}
                    if variant not in parameters:parameters.append(variant)
            cause={'type':'object','properties':{'mechanism':{'type':'string','enum':list(REGISTRY)},'parameters':{'anyOf':parameters},'evidence_status':{'type':'string','enum':['supported','tentative','unresolved']}},'required':['mechanism','parameters','evidence_status'],'additionalProperties':False}
            props={'schema_version':{'type':'string','enum':['nautilus.diagnosis.v4']},'hypothesis':{'anyOf':[{'type':'string','enum':list(REGISTRY)+list(PAIRS)},{'type':'null'}]},'causes':{'type':'array','items':cause,'maxItems':2},'relationship':{'type':'string','enum':['single','joint','partial','abstain']},'unresolved_sets':{'type':'array','items':{'type':'array','items':{'type':'string','enum':list(REGISTRY)},'minItems':1,'maxItems':2},'maxItems':6},'unexplained_residual':{'type':'boolean'},'qualification':{'type':'string','maxLength':2000},'evidence_refs':{'type':'array','items':{'type':'string'},'minItems':1}}
            p['diagnosis']={'anyOf':[old,{'type':'object','properties':props,'required':list(props),'additionalProperties':False}]}
    return out


def validate(name,arguments,joint_enabled=True):
    value=parse_json(arguments)
    def finite(v):
        if type(v) is float and not math.isfinite(v):raise ValueError('Nonfinite arguments')
        if type(v) is dict:
            for x in v.values():finite(x)
        if type(v) is list:
            for x in v:finite(x)
    finite(value)
    if joint_enabled and name=='propose_hypothesis' and value.get('template') in PAIRS:
        if set(value)!= {'template','knobs','bounds','rationale'} or type(value['rationale']) is not str or len(value['rationale'])>2000:raise ValueError('Invalid joint tool arguments')
        validate_pair(value['template'],value['knobs'],value['bounds']);return {'op':name,**value}
    if joint_enabled and name=='finalize' and type(value.get('diagnosis')) is dict and value['diagnosis'].get('schema_version')=='nautilus.diagnosis.v4':
        if set(value)!= {'diagnosis','confidence','ambiguity_statement'}:raise ValueError('Invalid V4 finalize arguments')
        return {'op':name,**value} # full current-evidence rubric runs in Laboratory
    return validate_call(name,arguments)
