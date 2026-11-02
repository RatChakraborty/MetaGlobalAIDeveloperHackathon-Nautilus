"""Equal-capability bounded policies. No evaluator truth or narrative parser."""
import random
from ..v2_models import REGISTRY
from ..active_planner import candidates
from ..lab_safety import screen
from .models import PAIRS,assess

STRATEGIES=('passive','exhaustive','sequential_residual','fixed','random','greedy','zero_test')


def summary(reports,details,refs):
    fits=[r for r in reports.values() if r['converged'] and r.get('evidence_refs')==refs]
    adequate=[r for r in fits if max(r['physical_wrms'],r['command_wrms'])<=2.]
    if not adequate:return {'kind':'MODEL_INADEQUATE','selected':None,'competitive':[]}
    best=min(r['penalized_score'] for r in adequate)
    competitive=sorted([r for r in adequate if r['penalized_score']<=best+6],key=lambda r:(len(r['parameters']),r['penalized_score'],r['hypothesis']))
    chosen=competitive[0]['hypothesis'];a=assess(chosen,reports,details,refs)
    return {'kind':a['status'],'selected':chosen,'competitive':[r['hypothesis'] for r in competitive],'qualification':'Simplest adequate fit within score gap6; strong classifications require separate mandatory rubric. No calibrated posterior.'}


def diagnosis(lab,name=None):
    report=lab.get_fit_report()
    if name is None:name=report['numerical_summary'].get('selected')
    if name is None:return {'schema_version':'nautilus.diagnosis.v4','hypothesis':None,'causes':[],'relationship':'abstain','unresolved_sets':[],'unexplained_residual':True,'qualification':'Available models/evidence inadequate or absent.','evidence_refs':lab.evidence_refs()}
    fit=lab._reports[name];components=PAIRS[name]['components'] if name in PAIRS else [name]
    return {'schema_version':'nautilus.diagnosis.v4','hypothesis':name,'causes':[{'mechanism':n,'parameters':{REGISTRY[n].parameter:fit['parameters'][REGISTRY[n].parameter]} if REGISTRY[n].parameter else {},'evidence_status':'tentative'} for n in components],'relationship':'joint' if name in PAIRS else 'single','unresolved_sets':[PAIRS[n]['components'] if n in PAIRS else [n] for n in report['numerical_summary'].get('competitive',[]) if n!=name][:6],'unexplained_residual':not all(report['v4']['assessments'][name]['checks'].values()),'qualification':'Conditional numerical choice; physical alternatives and untested models remain.','evidence_refs':lab.evidence_refs()}

class Policy:
    def __init__(self,strategy='sequential_residual',seed=0):
        if strategy not in STRATEGIES:raise ValueError('Unknown V4 policy')
        self.strategy=strategy;self.rng=random.Random(seed);self.attempted=set();self.fit_attempts=set();self.actions=0
    def choose(self,lab):
        self.actions+=1;r=lab.get_fit_report();remaining=r['remaining'];refs=tuple(r['evidence_refs'])
        if self.strategy in ('fixed','random','greedy') and remaining['experiments'] and not self.attempted:
            # One bounded 36-candidate screen; rejected menu means passive, not repeated experiments.
            from .planning import ranking
            ranked=ranking(lab);feasible=[row for row in ranked['rows'] if row['accepted'] and row['within_budget']]
            if feasible:
                chosen=self.rng.choice(feasible) if self.strategy=='random' else max(feasible,key=lambda x:x['minimum_separation'] or 0) if self.strategy=='greedy' else feasible[0]
                self.attempted.add(chosen['candidate_id']);return {'op':'request_experiment','name':chosen['name'],'params':chosen['params']}
            self.attempted.add('empty_safe_menu')
        singles=['nominal','lateral_current','port_degradation','starboard_degradation','heading_bias','actuator_lag']
        pairs=list(PAIRS)
        if self.strategy=='zero_test':order=singles+list(REGISTRY)[6:]+pairs
        elif self.strategy=='exhaustive':order=[x for pair in zip(singles,pairs) for x in pair]+[n for n in REGISTRY if n not in singles]
        elif self.strategy=='sequential_residual':
            # Fit original four physical fault singles + nominal before a residual-driven second cause.
            order=singles[:5]
            existing=[f for n,f in lab._reports.items() if n in singles[:5] and n!='nominal' and f['converged']]
            if existing:
                strongest=min(existing,key=lambda f:f['penalized_score'])['hypothesis']
                relevant=[n for n in pairs if strongest in PAIRS[n]['components']]
                # Bias/residual trend is used only as a deterministic ordering heuristic, not oracle cause evidence.
                mean=sum(abs(c['mean']) for ep in lab._reports[strongest]['residual_diagnostics'] for c in ep)
                if mean>1:relevant=sorted(relevant,key=lambda n:('heading_bias' not in PAIRS[n]['components'],n))
                order+=relevant+[n for n in pairs if n not in relevant]
        else:order=singles[:4]+pairs+singles[4:]
        for name in order:
            if (refs,name) in self.fit_attempts:continue
            cost=(2 if name in PAIRS else 1 if REGISTRY[name].parameter else 0)*lab._starts
            if remaining['fit_calls']<=0 or remaining['optimization_attempts']<cost:continue
            self.fit_attempts.add((refs,name));return {'op':'propose_hypothesis','template':name,'knobs':{},'bounds':{},'rationale':'Bounded deterministic '+self.strategy+' comparison; free text deliberately ignored.'}
        d=diagnosis(lab)
        return {'op':'finalize','diagnosis':d,'confidence':'abstain' if not d['causes'] else 'tentative','ambiguity_statement':'Deterministic text-blind policy; conditional current numerical evidence, not certified cause identity.'}
