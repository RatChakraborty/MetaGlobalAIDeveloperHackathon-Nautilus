"""One explicitly authorized development investigation; no benchmarks or repairs."""
import argparse
import json
from pathlib import Path
from nautilus.controller_context import build_controller_context, initialize_controller_context, canonical
from nautilus.simulator import simulate, Mission, Faults
from nautilus.laboratory import Laboratory
from nautilus.lab_safety import SafeBackend
from nautilus.muse import MetaProvider
from nautilus.muse_investigator import run, Limits


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--scenario',required=True,help='Trusted private development settings outside the checkout')
    parser.add_argument('--max-output-tokens',type=int,default=2048,help='Per-request output allowance including reasoning; review cost before increasing')
    parser.add_argument('--authorize-api',action='store_true',help='Permit one bounded real investigation')
    args=parser.parse_args()
    if not args.authorize_api: parser.error('Explicit API authorization required')
    output=Path(args.output).resolve(); root=Path(__file__).resolve().parent
    if output==root or root in output.parents: parser.error('Output must be outside the repository')
    limits=Limits(model_calls=10,actions=10,output_tokens_per_call=args.max_output_tokens,output_tokens_total=16000,retries=0)
    output.mkdir(parents=True,exist_ok=False)
    # Trusted reproducible development selection; never included in model context/export.
    # This is not a frozen evaluation case and no hidden labels guide host actions.
    settings_path=Path(args.scenario).resolve()
    if settings_path==root or root in settings_path.parents: parser.error('Private development settings must remain outside the checkout')
    settings=json.loads(settings_path.read_text())
    if set(settings)!={'purpose','faults','seed'} or settings['purpose']!='development-only' or type(settings['faults']) is not dict or type(settings['seed']) is not int:
        parser.error('Trusted development-only configuration required')
    faults=Faults(**settings['faults'])
    rows=simulate(faults=faults,mission=Mission(duration_s=2.,seed=settings['seed'])).observations
    lab=Laboratory(rows,SafeBackend(faults=faults,seed=settings['seed']),
                   fit_budget=8,optimization_budget=16,experiment_budget=1,time_budget_s=16.,
                   note='Development-only investigation. Determine what the public telemetry supports; abstain when confounded.')
    initialize_controller_context(lab,build_controller_context())
    result=run(lab,MetaProvider(),limits=limits)
    for name,value in [('investigation.json',result['public_record']),('muse-provenance.json',result['provenance'])]:
        (output/name).write_text(canonical(value)+'\n')
    print('Completed bounded investigation; review public export and linked provenance outside the checkout.')


if __name__=='__main__': main()
