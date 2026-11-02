"""Six whitelisted pair models using the historical observer and physics kernel."""
from dataclasses import asdict,replace
import math,time
import numpy as np
from scipy.optimize import least_squares
from ..v2_models import REGISTRY,configs,validate_proposal,commanded
from ..simulator import Faults,PlantConfig,Controller,Vehicle,effective_vehicle
from ..diagnosis import _prepare,_predict,FitConfig

PAIR_COMPONENTS=(('lateral_current','port_degradation'),('lateral_current','starboard_degradation'),('lateral_current','heading_bias'),('port_degradation','heading_bias'),('starboard_degradation','heading_bias'),('lateral_current','actuator_lag'))
PAIRS={'joint__'+'__'.join(pair):{'components':list(pair),'parameters':{REGISTRY[n].parameter:{'bounds':list(REGISTRY[n].bounds),'units':REGISTRY[n].units} for n in pair},'cost':'One fit call; two parameter-start units per optimizer start','method':'joint bounded observer least_squares; original physics','limitations':'Singleton composition, correlated innovations, local rank only; not unique causal attribution.'} for pair in PAIR_COMPONENTS}


def compose(spec):
    if type(spec) is not dict or set(spec)!={'schema_version','components'} or spec['schema_version']!='nautilus.physical-composition.v4' or type(spec['components']) is not list or not 1<=len(spec['components'])<=2:raise ValueError('Invalid composable fault specification')
    names=[];values=[]
    for component in spec['components']:
        if type(component) is not dict or set(component)!={'mechanism','value'}:raise ValueError('Invalid physical component')
        name=component['mechanism']
        if name not in REGISTRY or name in names:raise ValueError('Unknown or repeated component')
        if REGISTRY[name].parameter is None and component['value'] is not None:raise ValueError('Nominal has no parameter value')
        # configs validates finite values and established physical bounds.
        configs(name,component['value']);names.append(name);values.append(component['value'])
    if len(names)==2 and not any(set(names)==set(p) for p in PAIR_COMPONENTS):raise ValueError('Unapproved physical pair')
    defaults=(Faults(),PlantConfig(),Controller());merged=[asdict(x) for x in defaults];used=[set(),set(),set()]
    for name,value in zip(names,values):
        for i,part in enumerate(configs(name,value)):
            base=asdict(defaults[i])
            for field,v in asdict(part).items():
                if v!=base[field]:
                    if field in used[i]:raise ValueError('Overlapping physical parameter composition')
                    used[i].add(field);merged[i][field]=v
    return Faults(**merged[0]),PlantConfig(**merged[1]),Controller(**merged[2])


def validate_pair(name,knobs,bounds):
    if name not in PAIRS or type(knobs) is not dict or type(bounds) is not dict:raise ValueError('Unknown joint template')
    spec=PAIRS[name]['parameters'];names=list(spec)
    if knobs and set(knobs)!=set(names) or set(bounds)-set(names):raise ValueError('Joint knobs require both parameters; unknown fields rejected')
    limits={n:list(spec[n]['bounds']) for n in names}
    for n,b in bounds.items():
        if type(b) not in (list,tuple) or len(b)!=2 or any(type(x) not in (int,float) or not math.isfinite(x) for x in b) or not limits[n][0]<=b[0]<b[1]<=limits[n][1]:raise ValueError('Joint bounds exceed registry')
        limits[n]=list(b)
    if any(type(v) not in (int,float) or not math.isfinite(v) or not limits[n][0]<=v<=limits[n][1] for n,v in knobs.items()):raise ValueError('Joint knob outside bounds')
    return names,limits


def residuals(rows,times):
    out=[]
    for column in rows.T:
        mid=max(1,len(column)//2);center=column-column.mean();den=float(center@center)
        slope=float(np.polyfit(times,column,1)[0]) if len(times)>2 else None
        out.append({'mean':float(column.mean()),'std':float(column.std()),'rms':float(np.sqrt(np.mean(column**2))),'early_mean':float(column[:mid].mean()),'late_mean':float(column[mid:].mean()),'time_slope':slope,'lag1':float(center[1:]@center[:-1]/den) if den>1e-15 else None,'systematic_bias':bool(abs(column.mean())>1.)})
    return out


def fit_pair(episodes,name,*,knobs=None,bounds=None,starts=2,max_nfev=40):
    knobs={} if knobs is None else knobs;bounds={} if bounds is None else bounds
    names,limits=validate_pair(name,knobs,bounds)
    if type(starts) is not int or starts not in (1,2) or type(max_nfev) is not int or not 1<=max_nfev<=80:raise ValueError('Invalid joint optimizer budget')
    prepared=[(_prepare(e['observations'],FitConfig(method='observer'))[0],e['experiment']) for e in episodes]
    if not prepared:raise ValueError('No usable public evidence')
    lower=np.array([limits[n][0] for n in names]);upper=np.array([limits[n][1] for n in names]);began=time.perf_counter();evaluations=0
    def calculate(p,details=False):
        nonlocal evaluations
        evaluations+=1;components=PAIRS[name]['components']
        f,plant,control=compose({'schema_version':'nautilus.physical-composition.v4','components':[{'mechanism':n,'value':float(v)} for n,v in zip(components,p)]})
        physical=[];commands=[]
        for a,ex in prepared:
            prediction=_predict(a,effective_vehicle(Vehicle(),plant),f,'observer',{'actuator_tau_s':plant.actuator_tau_s,'thrust_deadzone_n':plant.thrust_deadzone_n})
            delta=prediction-a[:,1:4];delta[:,1]=np.arctan2(np.sin(delta[:,1]),np.cos(delta[:,1]));delta/=np.array([.035,.004,.003]);delta[1:]/=math.sqrt(2)
            physical.append(delta);commands.append((commanded(a,control,ex)-a[:,4:6])/.05)
        flat=np.concatenate([r.ravel() for r in physical+commands])
        return (flat,physical,commands) if details else flat
    guesses=[np.array([knobs[n] for n in names])] if knobs else [lower+t*(upper-lower) for t in ([.25,.75] if starts==2 else [.5])]
    solutions=[least_squares(calculate,g,bounds=(lower,upper),x_scale='jac',max_nfev=max_nfev) for g in guesses]
    best=min([s for s in solutions if s.success] or solutions,key=lambda s:s.cost);flat,physical,commands=calculate(best.x,True)
    scaled=best.jac*(upper-lower);_,singular,vt=np.linalg.svd(scaled,full_matrices=False);rank=int(np.sum(singular>max(float(singular[0])*1e-6,1e-8)))
    gram=scaled.T@scaled;cov=np.linalg.pinv(gram);den=np.sqrt(np.outer(np.diag(cov),np.diag(cov)));corr=np.divide(cov,den,out=np.zeros_like(cov),where=den>0)
    pw=float(np.sqrt(np.mean(np.concatenate(physical)**2)));cw=float(np.sqrt(np.mean(np.concatenate(commands)**2)));sse=float(flat@flat)
    hits=[n for n,v,lo,hi in zip(names,best.x,lower,upper) if min(v-lo,hi-v)<.001*(hi-lo)]
    diag=[residuals(r,a[:,0]) for r,(a,_) in zip(physical,prepared)]
    condition=float(singular[0]/singular[-1]) if rank==2 else None
    report={'hypothesis':name,'parameters':dict(zip(names,map(float,best.x))),'bounds':limits,'converged':bool(best.success),'status':str(best.message),'weighted_sse':sse,'weighted_rmse':max(pw,cw),'physical_wrms':pw,'command_wrms':cw,'penalized_score':sse+2*math.log(len(flat)),'evaluations':evaluations,'optimization_attempts':2*len(guesses),'warnings':['Joint correlated-innovation score is not a posterior. No speed/x observation.'],'bound_hits':hits,'method':'v4_joint','residual_diagnostics':[[{k:c[k] for k in ('mean','rms','lag1')} for c in episode] for episode in diag],'identifiability':{'scaled_norm':float(np.linalg.norm(scaled)),'rank':rank,'condition':condition,'qualification':'Local two-parameter sensitivity only, not global model identity.'},'interpretation':'Conditional joint numerical fit, not proven physical causes.'}
    detail={'schema_version':'nautilus.joint-fit.v4','hypothesis':name,'components':PAIRS[name]['components'],'parameter_order':names,'starts':len(guesses),'parameter_start_cost':2*len(guesses),'local_sensitivity_matrix':scaled.tolist(),'singular_values':singular.tolist(),'rank':rank,'condition':condition,'conditional_correlation':corr.tolist() if rank==2 else None,'coupled_directions':vt.tolist(),'residuals':diag,'bound_hits':hits,'score_rule':'SSE + k*log(5*N), k=2; support requires delta>=6 against both component singles and nominal. Correlated innovations are not calibrated likelihoods.','elapsed_s':time.perf_counter()-began}
    if not all(math.isfinite(x) for x in (sse,pw,cw,report['penalized_score'])):raise ValueError('Nonfinite joint fit')
    return report,detail


def assess(name,reports,details,refs):
    f=reports[name];pair=name in PAIRS;d=details.get(name,{})
    components=PAIRS[name]['components'] if pair else [name]
    required=['nominal']+components if pair else ['nominal']
    current=f.get('evidence_refs')==refs
    alternatives=[reports[n] for n in required if n in reports and n!=name and reports[n].get('evidence_refs')==refs and reports[n]['converged']]
    complete=all(n in reports and reports[n].get('evidence_refs')==refs and reports[n]['converged'] for n in required)
    delta=min((r['penalized_score'] for r in alternatives),default=f['penalized_score'])-f['penalized_score']
    rank=d.get('rank') if pair else f.get('identifiability',{}).get('rank')
    residual_ok=all(abs(c.get('lag1') or 0)<.8 for episode in f.get('residual_diagnostics',[]) for c in episode)
    checks={'converged':bool(f['converged']),'current_epoch':current,'finite_metrics':all(math.isfinite(f[k]) for k in ('penalized_score','physical_wrms','command_wrms')),'adequate':max(f['physical_wrms'],f['command_wrms'])<=2.,'interior_parameters':not bool(f.get('bound_hits')),'alternatives_complete':complete,'parsimony':bool(delta>=6) if pair else True,'local_rank':rank==2 and d.get('condition') is not None and d['condition']<1e6 if pair else name=='nominal' or rank==1,'tested_alternative_separation':all(r['penalized_score']-f['penalized_score']>=6 for n,r in reports.items() if n!=name and r['converged'] and r.get('evidence_refs')==refs),'residual_structure':residual_ok,'parameter_coupling':bool(d.get('conditional_correlation') is not None and abs(d['conditional_correlation'][0][1])<=.98) if pair else True}
    supported=all(checks.values());reason='supported_by_declared_rule' if supported else 'numerically_nonidentifiable' if not checks['local_rank'] else 'confounded' if complete and pair and delta<6 else 'weakly_suggested' if checks['adequate'] else 'unsupported'
    status='MODEL_INADEQUATE' if not checks['adequate'] else 'MULTI_CAUSE_SUPPORTED' if supported and pair else 'IDENTIFIED' if supported else 'PARTIAL' if pair and any(n in reports and all(assess(n,reports,details,refs)['checks'].values()) for n in components) else 'AMBIGUOUS_SET'
    return {'checks':checks,'status':status,'second_cause':reason if pair else 'not_applicable','delta_score':delta,'independent_confirmation':'unavailable; not a mandatory proof of causality','qualification':'Host numerical rubric only; not calibrated physical confidence.'}


def validate_diagnosis(d,confidence,text,lab):
    expected={'schema_version','hypothesis','causes','relationship','unresolved_sets','unexplained_residual','qualification','evidence_refs'}
    if set(d)!=expected or confidence not in ('supported','tentative','abstain') or type(text) is not str or not 1<=len(text.strip())<=4000:raise ValueError('Invalid V4 finalization envelope')
    if type(d['evidence_refs']) is not list or not d['evidence_refs'] or len(set(d['evidence_refs']))!=len(d['evidence_refs']) or any(x not in lab.evidence_refs() for x in d['evidence_refs']):raise ValueError('Unknown or repeated evidence references')
    if type(d['unexplained_residual']) is not bool or d['relationship'] not in ('single','joint','partial','abstain') or type(d['qualification']) is not str or not 1<=len(d['qualification'])<=2000 or type(d['unresolved_sets']) is not list or len(d['unresolved_sets'])>6:raise ValueError('Invalid V4 qualification')
    if type(d['causes']) is not list or len(d['causes'])>2:raise ValueError('At most two causes')
    names=[]
    for c in d['causes']:
        if type(c) is not dict or set(c)!={'mechanism','parameters','evidence_status'} or c['mechanism'] not in REGISTRY or c['mechanism'] in names or c['evidence_status'] not in ('supported','tentative','unresolved'):raise ValueError('Invalid structured cause')
        spec=REGISTRY[c['mechanism']];validate_proposal(c['mechanism'],c['parameters'])
        if set(c['parameters'])!=({spec.parameter} if spec.parameter else set()):raise ValueError('Exact fitted cause parameters required')
        names.append(c['mechanism'])
    for group in d['unresolved_sets']:
        if type(group) is not list or not 1<=len(group)<=2 or len(set(group))!=len(group) or any(x not in REGISTRY for x in group):raise ValueError('Invalid unresolved cause set')
    if confidence=='abstain':
        if names or d['hypothesis'] is not None or d['relationship']!='abstain':raise ValueError('Abstention cannot assert causes')
        return {'status':'AMBIGUOUS_SET','qualification':'Voluntary abstention; no correct-abstention claim.'}
    name=d['hypothesis']
    if name not in lab._reports or not lab._reports[name]['converged']:raise ValueError('Current converged fitted cause set required')
    components=PAIRS[name]['components'] if name in PAIRS else [name]
    if set(names)!=set(components) or len(names)!=len(components):raise ValueError('Cause list must match fitted model exactly')
    for c in d['causes']:
        for k,v in c['parameters'].items():
            if v!=lab._reports[name]['parameters'][k]:raise ValueError('Cause estimates must equal current fit')
    a=assess(name,lab._reports,lab.joint_details,lab.evidence_refs())
    if not a['checks']['current_epoch']:raise ValueError('Stale fit')
    if confidence=='supported' and d['unexplained_residual']:raise ValueError('Strong global support cannot leave unexplained residuals')
    if confidence=='supported' or any(c['evidence_status']=='supported' for c in d['causes']):
        if not all(a['checks'].values()):raise ValueError('Strong support fails mandatory host rubric')
    if len(names)==2 and d['relationship'] not in ('joint','partial') or len(names)==1 and d['relationship'] not in ('single','partial'):raise ValueError('Inconsistent cause relationship')
    return a
