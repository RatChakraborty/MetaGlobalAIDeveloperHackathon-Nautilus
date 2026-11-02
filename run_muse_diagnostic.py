"""Explicitly authorized development-only two-request laboratory dispatch test."""
import argparse
from pathlib import Path
from nautilus.controller_context import canonical
from nautilus.lab_safety import SafeBackend
from nautilus.laboratory import Laboratory
from nautilus.muse import MetaProvider, DEFAULT_MODEL
from nautilus.muse_diagnostic import run_diagnostic
from nautilus.simulator import simulate, Mission


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorize-api',action='store_true')
    parser.add_argument('--output',required=True)
    parser.add_argument('--reasoning-effort',choices=['low'],help='Only use after account/model support has been verified')
    args=parser.parse_args()
    if not args.authorize_api: parser.error('Explicit two-request authorization required')
    output=Path(args.output).resolve();root=Path(__file__).resolve().parent
    if output==root or root in output.parents: parser.error('Generated diagnostic data must remain outside the repository')
    provider=MetaProvider(model=DEFAULT_MODEL,reasoning_effort=args.reasoning_effort or '')
    output.mkdir(parents=True,exist_ok=False)
    lab=Laboratory(simulate(mission=Mission(duration_s=.3)).observations,SafeBackend(),
        fit_budget=1,optimization_budget=0,experiment_budget=0,time_budget_s=0.,note='Development-only read-only interface diagnostic; no scientific diagnosis.')
    result=run_diagnostic(lab,provider)
    for name,key in [('investigation.json','public_record'),('muse-provenance.json','provenance'),('tool-result.json','tool_result')]:
        if result[key] is not None: (output/name).write_text(canonical(result[key])+'\n')
    print('Development-only dispatch diagnostic recorded outside checkout; inspect acceptance evidence.')


if __name__=='__main__': main()
