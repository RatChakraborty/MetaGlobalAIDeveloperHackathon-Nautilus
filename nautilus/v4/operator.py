"""Local trusted operator CLI. Not a public HTTP endpoint or model tool.

python -m nautilus.v4.operator --directory /private/path demo --mode simulation_operator_approved
python -m nautilus.v4.operator --directory /private/path decide REQUEST_ID
python -m nautilus.v4.operator --directory /private/path resume
"""
import argparse,json
from pathlib import Path
from ..controller_context import canonical,initialize_controller_context,build_controller_context
from ..simulator import simulate,Mission,Faults
from .approval import Authority,Policy
from .laboratory import V4Laboratory
from .checkpoint import save,load


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',required=True)
    sub=p.add_subparsers(dest='action',required=True)
    demo=sub.add_parser('demo');demo.add_argument('--mode',choices=('simulation_enforced','simulation_operator_approved','simulation_advisory'),default='simulation_enforced')
    decide=sub.add_parser('decide');decide.add_argument('request_id');sub.add_parser('resume');sub.add_parser('status');sub.add_parser('export')
    args=p.parse_args();authority=Authority(args.directory);path=authority.directory/'session.json'
    if args.action=='decide':
        print(canonical(authority.decide_interactive(args.request_id)));return
    if args.action=='demo':
        if path.exists():raise ValueError('Existing session: never overwrite or replay')
        faults=Faults(current_y=.4);rows=simulate(faults=faults,mission=Mission(duration_s=2.,seed=407)).observations
        lab=V4Laboratory(rows,policy=Policy(args.mode),authority=authority,settings={'faults':faults,'seed':407},experiment_budget=1,time_budget_s=16.,fit_budget=8,optimization_budget=16,starts=2)
        result=lab.call({'op':'request_experiment','name':'thrust_step','params':{'duration_s':4.,'amplitude_n':0.,'phase_s':2.}})
        save(lab,path);print(canonical(result));return
    lab,host=load(authority,path)
    if args.action=='resume':
        if host is not None:raise ValueError('Agent session requires bounded host resume adapter, not demo CLI')
        if lab.pending is None:raise ValueError('No pending experiment; never repeat execution')
        result=lab.resolve_operator(lab.pending);save(lab,path,host);print(canonical({k:v for k,v in result.items() if k!='observations'}))
    elif args.action=='export':
        from .records import export
        export(lab,authority.directory/'public-investigation.json',authority.directory/'v4-provenance.json');print('Validated local public exports written; no publication.')
    else:print(canonical({'session_id':lab.session_id,'state':lab.state,'policy':lab.policy.mode,'pending':authority.get(lab.pending) if lab.pending else None,'budget':lab.budget()}))

if __name__=='__main__':main()
