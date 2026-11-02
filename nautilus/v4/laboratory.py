"""Opt-in V4 laboratory. Original laboratory/simulator modules are untouched."""
from copy import deepcopy
from dataclasses import asdict
import secrets,math
from ..controller_context import canonical,fingerprint
from ..laboratory import Laboratory
from ..lab_safety import SafeBackend,screen,guarded_trial,advisory_report
from ..simulator import Faults,PlantConfig,Controller,Experiment
from ..v2_experiments import parse_trial
from ..diagnosis import _prepare,FitConfig
from .approval import Policy,Authority,AuthorizationDenied

class Backend:
    def __init__(self,session,policy,authority=None,*,faults=Faults(),plant=PlantConfig(),controller=Controller(),seed=0):
        self.session,self.policy,self.authority=session,policy,authority
        self.faults,self.plant,self.controller,self.seed=faults,plant,controller,seed
        self.count,self.time,self.used=0,0.,set();self.private_results=[]
        if policy.mode=='simulation_operator_approved' and type(authority) is not Authority:raise ValueError('Local trusted authority required')
    def execute(self,trial,*,epoch,budget,request_id=None):
        trial=parse_trial(trial.name,trial.params());s=screen(trial)
        if type(budget) is not dict or set(budget)!={'fits','starts','experiments','simulation_s','experiment_limit','time_limit_s'} or any(type(v) not in (int,float) or not math.isfinite(v) for v in budget.values()):raise AuthorizationDenied('Malformed execution budget')
        if self.count!=budget['experiments'] or self.time!=budget['simulation_s'] or budget['experiments']>=budget['experiment_limit'] or budget['simulation_s']+trial.duration_s+self.policy.tail>budget['time_limit_s']:raise AuthorizationDenied('Independent backend budget check failed')
        if self.count>=3 or self.time+trial.duration_s+self.policy.tail>48 or trial.key in self.used:raise AuthorizationDenied('Backend execution budget exhausted')
        if not s['accepted']:
            if self.policy.mode=='simulation_enforced':raise AuthorizationDenied('Predictive rejection')
            if self.policy.mode=='simulation_operator_approved':
                self.authority.check(request_id,self.session,epoch,trial,s,self.policy,budget,consume=True)
        elif request_id is not None:raise AuthorizationDenied('Unnecessary or mismatched approval')
        self.count+=1;self.time+=trial.duration_s+self.policy.tail;self.used.add(trial.key)
        try:
            rows,meta,private=guarded_trial(trial,self.faults,self.plant,self.controller,self.seed+int(trial.key[:8],16),mode='simulation_advisory' if self.policy.mode=='simulation_advisory' else 'simulation_enforced')
            self.private_results.append(private)
            # Mode describes actual guard behavior; operating policy is separate.
            result={'accepted':True,'observations':rows,'execution':meta,'safety':s}
        except BaseException:
            if request_id is not None:self.authority.finish(request_id,False)
            raise
        if request_id is not None:self.authority.finish(request_id,True)
        return result

class V4Laboratory(Laboratory):
    def __init__(self,observations,*,policy=Policy(),authority=None,session_id=None,settings=None,joint_enabled=False,**limits):
        self.policy=policy;self.authority=authority;self.session_id=session_id or secrets.token_hex(16)
        settings=dict(settings or {});self.joint_enabled=joint_enabled
        super().__init__(observations,SafeBackend(**settings,mode='simulation_advisory' if policy.mode=='simulation_advisory' else 'simulation_enforced'),**limits)
        self.execution_backend=Backend(self.session_id,policy,authority,**settings)
        self.pending=None;self.state='RUNNING';self.v4_events=[];self.joint_details={}
        from ..controller_context import initialize_controller_context,build_controller_context
        initialize_controller_context(self,build_controller_context())
    @property
    def epoch(self):return fingerprint(self.evidence_refs())
    def record(self,kind,data):
        body={'index':len(self.v4_events),'kind':kind,'ledger_anchor':self.ledger[-1]['event_hash'],'previous_hash':self.v4_events[-1]['hash'] if self.v4_events else None,'data':deepcopy(data)}
        self.v4_events.append({'body_canonical':canonical(body),'hash':fingerprint(body)})
    def _open(self):
        if self._closed or self.state!='RUNNING':raise ValueError('Laboratory is closed or suspended')
    def request_experiment(self,name,params):
        self._open();trial=parse_trial(name,params);self._experiment_budget(trial)
        s=screen(trial);display=advisory_report(s,'simulation_advisory' if self.policy.mode=='simulation_advisory' else 'simulation_enforced')
        self._event('safety',{'request':asdict(trial),'screen':display})
        self.record('safety_policy',{'policy':self.policy.mode,'policy_id':self.policy.identity,'trial':{'name':trial.name,'params':trial.params()},'predictive_margin_m':s['limit_m']-s['ensemble_max_y_m']-s['noise_allowance_m'],'screen':s})
        if not s['accepted'] and self.policy.mode=='simulation_enforced':return {'accepted':False,'constraint':'predictive_envelope','safety':s}
        if not s['accepted'] and self.policy.mode=='simulation_operator_approved':
            row=self.authority.create(self.session_id,self.epoch,trial,s,self.policy,self.budget())
            self.pending=row['binding']['request_id'];self.state='AWAITING_OPERATOR'
            self.record('approval_request',row)
            return {'status':'AWAITING_OPERATOR','accepted':False,'executed':False,'request_id':self.pending,'safety':s}
        return self._execute_v4(trial)
    def _experiment_budget(self,trial):
        if self._allowed is not None and trial.key not in self._allowed:raise ValueError('Outside experiment menu')
        if self.tests>=self._experiment_limit or self.test_time_s+trial.duration_s+self.policy.tail>self._time_limit or trial.key in self._seen:raise ValueError('Experiment budget exhausted or repeated action')
    def budget(self):return {'fits':self.fit_calls,'starts':self.optimization_attempts,'experiments':self.tests,'simulation_s':self.test_time_s,'experiment_limit':self._experiment_limit,'time_limit_s':self._time_limit}
    def resolve_operator(self,request_id):
        if self.state!='AWAITING_OPERATOR' or request_id!=self.pending:raise AuthorizationDenied('No matching pending request')
        row=self.authority.get(request_id);state=row['state']
        if state=='AWAITING_OPERATOR':return {'status':state,'executed':False,'request_id':request_id}
        if state in ('DENIED','CANCELLED','EXPIRED'):
            self.record('approval_decision',row);self.pending=None;self.state='RUNNING'
            return {'status':state,'accepted':False,'executed':False,'request_id':request_id}
        if state=='EXECUTING':
            # Interrupted execution is uncertain: never replay it.
            self.authority.finish(request_id,False);self.state='FAILED';self.record('approval_decision',self.authority.get(request_id));raise AuthorizationDenied('Interrupted execution; no automatic replay')
        if state!='APPROVED':
            self.state='FAILED';self.record('approval_decision',row)
            raise AuthorizationDenied('Terminal execution recovery is uncertain; no automatic replay or invented observations')
        b=row['binding'];trial=parse_trial(b['experiment']['name'],b['experiment']['params']);self._experiment_budget(trial);s=screen(trial)
        self.authority.check(request_id,self.session_id,self.epoch,trial,s,self.policy,self.budget()) # lab independent check
        self.record('approval_decision',row)
        result=self._execute_v4(trial,request_id=request_id)
        self.pending=None;self.state='RUNNING';return result
    def _execute_v4(self,trial,request_id=None):
        before=self.budget();self.tests+=1;self.test_time_s+=trial.duration_s+self.policy.tail;self._seen.add(trial.key)
        try:result=self.execution_backend.execute(trial,epoch=self.epoch,budget=before,request_id=request_id)
        except AuthorizationDenied:
            self.tests-=1;self.test_time_s-=trial.duration_s+self.policy.tail;self._seen.remove(trial.key);raise
        except BaseException:self.state='FAILED';raise
        self._reports.clear();self._fits.clear();self.joint_details.clear()
        rows=result['observations'];_prepare(rows,FitConfig(method='observer'))
        prefix=[r for r in rows if r['time_s']<result['execution']['fit_end_exclusive_s']-1e-9]
        if len(prefix)>=3:self.episodes.append({'observations':prefix,'experiment':trial.experiment()})
        ref=self._event('observation',{'observations':rows,'execution':result['execution'],'fit_rows':len(prefix),'request':asdict(trial)})
        self.record('execution',{'policy':self.policy.mode,'approval_request_id':request_id,'observation_ref':ref,'execution':result['execution'],'containment':'unverified'})
        return {**result,'evidence_ref':ref,'fit_reports_stale':True}
    def propose_hypothesis(self,template,knobs,bounds,rationale):
        self._open()
        from .models import PAIRS,fit_pair
        if template not in PAIRS:return super().propose_hypothesis(template,knobs,bounds,rationale)
        if not self.joint_enabled:raise ValueError('Joint research feature disabled')
        if type(rationale) is not str or len(rationale)>2000:raise ValueError('Invalid rationale')
        starts=1 if knobs else self._starts;cost=2*starts
        if self.fit_calls>=self._fit_limit or self.optimization_attempts+cost>self._optimization_limit:raise ValueError('Joint numerical budget exhausted')
        # Validate before charging; a pair start costs two parameter-start units.
        from .models import validate_pair
        validate_pair(template,knobs,bounds)
        self.fit_calls+=1;self.optimization_attempts+=cost
        try:report,detail=fit_pair(self.episodes,template,knobs=knobs,bounds=bounds,starts=starts)
        except (ValueError,FloatingPointError,OverflowError):
            self._event('fit_failure',{'template':template,'method':'v4_joint','reason':'Joint numerical fit failed'});self._reports.pop(template,None);self.joint_details.pop(template,None);return {'status':'OPTIMIZATION_FAILURE'}
        report['evidence_refs']=self.evidence_refs();self._reports[template]=report;detail['evidence_refs']=self.evidence_refs();self.joint_details[template]=detail
        self._event('fit',{'report':report,'rationale':rationale});self.record('joint_fit',detail);return {**report,'v4_diagnostics':detail}
    def get_fit_report(self):
        result=super().get_fit_report()
        if hasattr(self,'v4_events'):
            from .models import PAIRS,assess
            if self.joint_enabled:
                from .policies import summary
                result['numerical_summary']=summary(self._reports,self.joint_details,self.evidence_refs())
            result['v4']={'policy':self.policy.mode,'policy_id':self.policy.identity,'state':self.state,'joint_enabled':self.joint_enabled,'joint_registry':PAIRS if self.joint_enabled else {},'joint_details':deepcopy(self.joint_details),'assessments':{name:assess(name,self._reports,self.joint_details,self.evidence_refs()) for name in self._reports}}
        return result
    def validate_finalization(self,diagnosis,confidence,ambiguity_statement):
        self._open()
        if type(diagnosis) is not dict:raise ValueError('Structured diagnosis required')
        if diagnosis.get('schema_version')!='nautilus.diagnosis.v4':return super().validate_finalization(diagnosis,confidence,ambiguity_statement)
        from .models import validate_diagnosis
        return validate_diagnosis(diagnosis,confidence,ambiguity_statement,self)
    def finalize(self,diagnosis,confidence,ambiguity_statement):
        try:assessment=self.validate_finalization(diagnosis,confidence,ambiguity_statement)
        except ValueError as error:
            self.record('rejected_conclusion',{'proposal':{'diagnosis':diagnosis,'confidence':confidence,'ambiguity_statement':ambiguity_statement},'reason':str(error)});raise
        result={'diagnosis':deepcopy(diagnosis),'confidence':confidence,'stop_reason':ambiguity_statement,'numerical_summary':self.get_fit_report()['numerical_summary'],'interpretation':'Conditional numerical evidence, not certified physical causality.'}
        self.record('host_assessment',{'proposal':deepcopy(result),'assessment':assessment})
        self._event('finalized',result);self._closed=True;self.state='COMPLETED';return deepcopy(result)
