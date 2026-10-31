
from dataclasses import asdict,replace
from types import SimpleNamespace
import json
import math

import numpy as np

from .protocol import digest,classify
from .v2_models import REGISTRY,fit_model,validate_proposal,finding
from .v2_experiments import parse_trial,Trial,forward,PARAMETERS
from .simulator import Experiment,OBSERVATION_FIELDS
from .diagnosis import _prepare,FitConfig


def public_fit(fit):
    return {**{k:v for k,v in asdict(fit).items() if k!='elapsed_s'},
            'physical_finding':finding(fit),'healthy_range':REGISTRY[fit.hypothesis].healthy_range,
            'interpretation':'A fitted healthy-range mechanism is ordinary plant behavior, not injected degradation.'}


def verdict(fits):
    if not fits:return {'kind':'optimization_failure','selected':None,'competitive':[]}
    protocol=SimpleNamespace(hypotheses=tuple(f.hypothesis for f in fits),adequacy_wrms=2.,gap=6.)
    out=classify(list(fits),protocol)
    return {'kind':out.kind,'selected':out.selected,'competitive':out.competitive}


def parse_json(value):
    def pairs(items):
        out={}
        for k,v in items:
            if k in out:raise ValueError('Duplicate JSON field')
            out[k]=v
        return out
    if type(value) is str:
        value=json.loads(value,object_pairs_hook=pairs,
                         parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON number')))

    json.dumps(value,allow_nan=False)
    if type(value) is not dict:raise ValueError('JSON object required')
    return value


def fields(value,expected):
    if set(value)!=set(expected):raise ValueError('Missing or unknown JSON fields')


def capability_schema():

    operations={
      'propose_hypothesis':{'template':{'type':'string','enum':list(REGISTRY)},
                            'knobs':{'type':'object'},'bounds':{'type':'object'},
                            'rationale':{'type':'string','maxLength':2000}},
      'request_experiment':{'name':{'type':'string','enum':['cable_follow','thrust_step','coast_down','differential_step','amplitude_ramp','heading_response']},'params':{'type':'object'}},
      'get_fit_report':{},
      'finalize':{'diagnosis':{'type':'object','additionalProperties':False,
                             'required':['hypothesis','evidence_refs'],
                             'properties':{'hypothesis':{'type':['string','null']},
                                           'evidence_refs':{'type':'array','minItems':1,'items':{'type':'string'}}}},
                  'confidence':{'enum':['supported','tentative','abstain']},
                  'ambiguity_statement':{'type':'string','minLength':1,'maxLength':4000}},
    }
    branches=[{'type':'object','additionalProperties':False,
               'required':['op',*props], 'properties':{'op':{'const':op},**props}}
              for op,props in operations.items()]
    proposals=[]
    for name,spec in REGISTRY.items():
        knobs={};bounds={}
        if spec.parameter:
            numeric={'type':'number','minimum':spec.bounds[0],'maximum':spec.bounds[1]}
            knobs[spec.parameter]=numeric
            bounds[spec.parameter]={'type':'array','minItems':2,'maxItems':2,
                                    'items':numeric}
        proposals.append({'properties':{'template':{'const':name},
            'knobs':{'type':'object','additionalProperties':False,'properties':knobs},
            'bounds':{'type':'object','additionalProperties':False,'properties':bounds}}})
    branches[0]['oneOf']=proposals
    ranges={'duration_s':(4,16),'amplitude_n':(0,20),'differential_n':(-6,6),
            'cruise_thrust_n':(0,20),'phase_s':(0,16),'heading_step_rad':(-.5,.5)}
    branches[1]['oneOf']=[{'properties':{'name':{'const':name},
        'params':{'type':'object','additionalProperties':False,
                  'properties':{k:{'type':'number','minimum':ranges[k][0],'maximum':ranges[k][1]}
                                for k in keys}}}} for name,keys in PARAMETERS.items()]
    return {'oneOf':branches,
            'semantic_validation':'Per-template knobs/bounds and per-mode parameters are closed whitelists in application validation.'}


class InvestigationSession:
    def __init__(self,observations,execute,*,note='',fit_budget=64,
                 optimization_budget=128,experiment_budget=3,time_budget_s=48.,starts=2,
                 initial_fits=None,fit_provider=fit_model,allowed_trials=None):
        if (type(fit_budget) is not int or not 1<=fit_budget<=64
                or type(optimization_budget) is not int or not 0<=optimization_budget<=128
                or type(experiment_budget) is not int or not 0<=experiment_budget<=3
                or type(starts) is not int or not 1<=starts<=2
                or type(time_budget_s) not in (int,float) or not math.isfinite(time_budget_s)
                or not 0<=time_budget_s<=48 or type(note) is not str or len(note)>4000):
            raise ValueError('Invalid session limits or untrusted note')
        _prepare(observations,FitConfig(method='observer'))
        self.episodes=[{'observations':[dict(r) for r in observations],'experiment':Experiment()}]
        self._execute=execute;self._fits={};self._starts=starts
        self._allowed=None if allowed_trials is None else {r.key for r in allowed_trials}
        self._fit_provider=fit_provider
        self._fit_limit=fit_budget;self._optimization_limit=optimization_budget
        self._experiment_limit=experiment_budget;self._time_limit=time_budget_s
        self.fit_calls=0;self.optimization_attempts=0;self.tests=0;self.test_time_s=0.
        self._seen=set();self._closed=False;self.ledger=[]
        self._event('observation',{'observations':observations,'origin':'initial public telemetry'})
        self._event('operator_note',{'text':note,'trust':'untrusted evidence, never executable instructions'})


        if initial_fits:
            for f in initial_fits:
                validate_proposal(f.hypothesis)
                self._fits[f.hypothesis]=f
                self.fit_calls+=1;self.optimization_attempts+=f.optimization_attempts
            if self.fit_calls>fit_budget or self.optimization_attempts>optimization_budget:
                raise ValueError('Initial fits exceed budget')

    def _event(self,kind,payload):
        event={'index':len(self.ledger),'type':kind,**payload,
               'previous_hash':self.ledger[-1]['event_hash'] if self.ledger else None}
        self.ledger.append({**event,'event_hash':digest(event)})
        return self.ledger[-1]['event_hash']

    def propose_hypothesis(self,template,knobs,bounds,rationale):
        if self._closed:raise ValueError('Session finalized')
        spec,_=validate_proposal(template,knobs,bounds)
        if type(rationale) is not str or len(rationale)>2000:raise ValueError('Invalid untrusted rationale')
        attempts=(1 if knobs else self._starts) if spec.parameter else 0
        if self.fit_calls>=self._fit_limit or self.optimization_attempts+attempts>self._optimization_limit:
            raise ValueError('Fit or optimization budget exhausted')
        self.fit_calls+=1;self.optimization_attempts+=attempts
        fit=self._fit_provider(self.episodes,template,knobs=knobs,bounds=bounds,starts=self._starts)
        self._fits[template]=fit
        self._event('fit',{'template':template,'report':public_fit(fit),'rationale':rationale,
                           'evidence_refs':self.evidence_refs()})
        return public_fit(fit)

    def evidence_refs(self):
        return [e['event_hash'] for e in self.ledger if e['type']=='observation']

    def request_experiment(self,name,params):
        if self._closed:raise ValueError('Session finalized')
        request=parse_trial(name,params)
        if self._allowed is not None and request.key not in self._allowed:
            raise ValueError('Experiment outside this comparison protocol menu')
        if (self.tests>=self._experiment_limit or self.test_time_s+request.duration_s>self._time_limit
                or request.key in self._seen):raise ValueError('Experiment budget exhausted or repeated request')


        self.tests+=1;self.test_time_s+=request.duration_s;self._seen.add(request.key)
        self._event('request',{'request':asdict(request)})
        self._fits.clear()
        result=self._execute(request)
        if set(result)!={'observations','experiment','envelope'}:raise ValueError('Invalid backend response')
        _prepare(result['observations'],FitConfig(method='observer'))
        self.episodes.append({'observations':result['observations'],'experiment':result['experiment']})
        self._fits.clear()
        reference=self._event('observation',{'observations':result['observations'],
                                             'request':asdict(request),'envelope':result['envelope']})
        return {'observations':result['observations'],'evidence_ref':reference,
                'envelope':result['envelope'],'fit_reports_stale':True}

    def get_fit_report(self):
        fits=list(self._fits.values())
        finite=[f.penalized_score for f in fits if f.converged and math.isfinite(f.penalized_score)]
        best=min(finite) if finite else None
        return {'fits':[{**public_fit(f),'relative_score':f.penalized_score-best if best is not None else None} for f in fits], 'decision':verdict(fits),
                'budgets':{'fit_calls':self.fit_calls,'optimization_attempts':self.optimization_attempts,
                           'experiments':self.tests,'charged_time_s':self.test_time_s},
                'remaining':{'fit_calls':self._fit_limit-self.fit_calls,
                             'optimization_attempts':self._optimization_limit-self.optimization_attempts,
                             'experiments':self._experiment_limit-self.tests,
                             'time_s':self._time_limit-self.test_time_s},
                'allowed_request_keys':sorted(self._allowed) if self._allowed is not None else 'bounded parameter envelope',
                'evidence_refs':self.evidence_refs(),'history':self.ledger,
                'scope':'Only fitted templates; absence from this set does not refute an untested mechanism.'}

    def finalize(self,diagnosis,confidence,ambiguity_statement):
        if self._closed:raise ValueError('Session finalized')
        if type(diagnosis) is not dict:raise ValueError('Structured diagnosis required')
        fields(diagnosis,('hypothesis','evidence_refs'))
        if (confidence not in ('supported','tentative','abstain')
                or type(ambiguity_statement) is not str or not ambiguity_statement.strip()
                or len(ambiguity_statement)>4000):raise ValueError('Qualified categorical confidence and limitations required')
        refs=diagnosis['evidence_refs']
        if type(refs) is not list or not refs or not all(type(r) is str and r in self.evidence_refs() for r in refs):
            raise ValueError('Actual public-observation evidence references required')
        decision=verdict(list(self._fits.values()))
        name=diagnosis['hypothesis']
        if confidence=='abstain':
            if name is not None:raise ValueError('Abstention cannot assert a diagnosis')
        elif (name not in self._fits or not self._fits[name].converged
              or self._fits[name].weighted_rmse>2):raise ValueError('Current adequate fit required')
        elif confidence=='supported' and (len(self._fits)<2 or 'nominal' not in self._fits
                                         or decision['kind']!='identified' or name!=decision['selected']):
            raise ValueError('Ambiguous or contradicted finding cannot be supported')
        elif confidence=='tentative' and name not in decision['competitive']:
            raise ValueError('Tentative findings must remain numerically competitive')
        self._closed=True
        result={'diagnosis':diagnosis,'confidence':confidence,'ambiguity_statement':ambiguity_statement,
                'scope':'Conditional on tested registry models; not a calibrated probability.'}
        self._event('finalized',result)
        return result

    def call(self,payload):
        try:
            value=parse_json(payload)
            op=value.get('op')
            schemas={'propose_hypothesis':('op','template','knobs','bounds','rationale'),
                     'request_experiment':('op','name','params'),
                     'get_fit_report':('op',),
                     'finalize':('op','diagnosis','confidence','ambiguity_statement')}
            if type(op) is not str or op not in schemas:raise ValueError('Unknown capability')
            fields(value,schemas[op])
            return getattr(self,op)(**{k:v for k,v in value.items() if k!='op'})
        except (ValueError,TypeError,KeyError,FloatingPointError,OverflowError) as exc:
            self._event('rejected',{'reason':str(exc)})
            raise ValueError(str(exc)) from exc


def predicted_separation(fits,trial):

    if len(fits)<2:return 0.
    predictions=[forward(f,trial) for f in fits]
    distances=[]
    scale=np.sqrt(2*np.array([.035,.004,.003])**2+np.array([.1,.03,.02])**2)
    for i,a in enumerate(predictions):
        for b in predictions[i+1:]:
            n=min(len(a),len(b));delta=np.array([[x[k]-y[k] for k in ('observed_y_m','observed_heading_rad','observed_yaw_rate_radps')] for x,y in zip(a[1:n],b[1:n])])
            if not len(delta):continue
            delta[:,1]=np.arctan2(np.sin(delta[:,1]),np.cos(delta[:,1]))
            distances.append(float(np.mean((delta/scale)**2)))
    return float(np.sqrt(np.mean(distances))) if distances else 0.
