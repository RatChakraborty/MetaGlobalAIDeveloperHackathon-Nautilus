"""Private, frozen-pool evaluator. No oracle outputs belong in source control.

  python evaluate_active.py pilot --output ../active-private/dev-pilot.json
  python evaluate_active.py freeze --output ../active-private/frozen.json
  python evaluate_active.py run --manifest ../active-private/frozen.json --output ../active-private/run

freeze must precede run. Generation, screening and offline correctness scoring
live here; the planner never receives injected faults, plant settings or truth.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, replace
import itertools
import json
import math
import os
from pathlib import Path
import platform
import sys
import time

import numpy as np
import scipy

from nautilus.experiments import EXPERIMENT_LIBRARY, HiddenExperimentBackend, separation
from nautilus.investigation import investigate, verify_ledger
from nautilus.protocol import (PassiveProtocol, diagnose_episodes, digest, passive,
                               source_fingerprint, summary)
from nautilus.scenarios import evaluate_scenario, Scenario
from nautilus.simulator import Controller, Faults, HIDDEN_PLANT, Mission, PlantConfig
from nautilus.simulator import OBSERVATION_FIELDS
from nautilus.diagnosis import HYPOTHESES

ROOT = Path(__file__).resolve().parent
UPSTREAM = "eb2d4df93e318a2ee50ff465f9e921e9122c9d2d"
PRIMARY_LABELS = ("nominal", "mismatch", "current", "port", "starboard", "bias",
                  "controller", "current_bias", "thruster_bias", "current")
HARD_LABELS = ("nominal", "mismatch", "current", "port", "starboard", "bias")
GENERATION = {
    "primary_count": 100, "primary_seed_start": 200000,
    "hard_count": 60, "hard_seed_start": 300000,
    "development_primary_start": 20000, "development_hard_start": 30000,
    "primary_labels": PRIMARY_LABELS, "hard_labels": HARD_LABELS,
    "mission_duration_s": 100., "dt_s": .05,
    "current_y_abs": [.30, .70], "current_x": [-.10, .10],
    "efficiency": [.25, .65], "heading_bias_abs": [.25, .55],
    "controller_kp": [-45., -20.],
    "mismatch_tau": [0., .30], "mismatch_deadzone": [0., .8],
    "mismatch_drag_scale": [.8, 1.2],
    "hard_case_reason": "First 0.5 s of recovered telemetry: short initial excitation, same faults/noise.",
}


def candidate(seed, label, case_id):
    rng = np.random.default_rng(seed)
    params, families = {}, []
    controller, plant = Controller(), HIDDEN_PLANT
    if label in ("current", "current_bias"):
        params.update(current_y=float(rng.choice([-1,1])*rng.uniform(.30,.70)),
                      current_x=float(rng.uniform(-.10,.10)))
        families.append("current")
    if label in ("port", "starboard", "thruster_bias"):
        side = label if label != "thruster_bias" else str(rng.choice(["port", "starboard"]))
        params[side+"_efficiency"] = float(rng.uniform(.25,.65))
        families.append("thruster")
    if label in ("bias", "current_bias", "thruster_bias"):
        params["heading_bias_rad"] = float(rng.choice([-1,1])*rng.uniform(.25,.55))
        families.append("sensor")
    if label == "controller":
        controller = replace(controller, heading_kp=float(rng.uniform(-45,-20)))
        families.append("controller")
    if label == "mismatch":
        plant = PlantConfig(float(rng.uniform(0,.3)), float(rng.uniform(0,.8)), float(rng.uniform(.8,1.2)))
    if label not in set(PRIMARY_LABELS+HARD_LABELS):
        raise ValueError("Unknown frozen stratum")
    return Scenario(case_id, tuple(families), seed, Faults(**params), controller), plant


def oracle_family(scenario):
    if len(scenario.families) > 1 or "controller" in scenario.families:
        return None
    f = scenario.faults
    if not scenario.families:
        return "nominal"
    if "current" in scenario.families:
        return "lateral_current"
    if "sensor" in scenario.families:
        return "heading_bias"
    return "port_degradation" if f.port_efficiency < 1 else "starboard_degradation"


def plans():
    return [{"case_id": f"{stratum}-{i:03d}", "stratum": stratum, "seed": start+i,
             "label": labels[i % len(labels)]}
            for stratum, count, start, labels in (
                ("primary", GENERATION["primary_count"], GENERATION["primary_seed_start"], PRIMARY_LABELS),
                ("hard", GENERATION["hard_count"], GENERATION["hard_seed_start"], HARD_LABELS))
            for i in range(count)]


def runtime():
    return {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
            "platform": platform.platform(),
            "threads": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")}}


def freeze():
    protocols = {"primary": asdict(PassiveProtocol()),
                 "hard": asdict(PassiveProtocol(name="short-log-v1", duration_s=.5))}
    manifest = {"upstream": UPSTREAM, "source_files": source_fingerprint(ROOT),
                "protocols": protocols, "generation": GENERATION, "plans": plans(),
                "runtime": runtime(), "scoring": "SSE of observer innovations + k*log(3*N)",
                "observation_schema": OBSERVATION_FIELDS, "parameter_bounds": HYPOTHESES,
                "outcomes": "Any candidate nonconverged => optimization_failure; adequate WRMS<=2; competitive gap<=6",
                "operational": "Existing mission_success=false; degradation separate: RMS +0.25 m, max +0.5 m, delay +5 s",
                "selection": "Every supported operational failure with public ambiguous outcome; never filter on active success",
                "unsupported": "Controller and compound families are flagged separately; passive errors still counted",
                "active": {"library": [asdict(r) for r in EXPERIMENT_LIBRARY], "budget": 2,
                           "time_budget_s": 30., "prediction_discrepancy": [.1,.03,.02],
                           "predicted_separation_threshold": 2., "strategies": ["fixed","random","greedy"]},
                "random_policy_seed_start": 700000,
                "threshold_justification": "Gap 6 retained from development reliability as a heuristic. Not a calibrated noise floor.",
                "noise": "Existing independent Gaussian sensors; deterministic fitter; per-request independent trial seeds",
                "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    manifest["fingerprint"] = digest(manifest)
    return manifest


def validate_manifest(manifest):
    body = {k:v for k,v in manifest.items() if k != "fingerprint"}
    if digest(body) != manifest.get("fingerprint"):
        raise ValueError("Frozen manifest was modified")
    if manifest["source_files"] != source_fingerprint(ROOT):
        raise ValueError("Source differs from frozen algorithm: do not silently rerun held-out results")
    if manifest["runtime"] != runtime():
        raise ValueError("Numerical runtime differs from freeze")
    return True


def protocol_from(values):
    return PassiveProtocol(**{**values, "scales": tuple(values["scales"]),
                              "hypotheses": tuple(values["hypotheses"])})


def wilson(successes, count):
    if not count:
        return None
    z=1.959963984540054
    p=successes/count; den=1+z*z/count
    mid=(p+z*z/(2*count))/den
    half=z*math.sqrt(p*(1-p)/count+z*z/(4*count*count))/den
    return [max(0.,mid-half), min(1.,mid+half)]


def private_write(path, value):
    path=Path(path).resolve()
    if ROOT == path or ROOT in path.parents:
        raise ValueError("Private outputs must be outside the source repository")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')


def assess(initial, outcome, protocol, backend_factory, true_family, seed):

    cache = {}
    def refit(episodes, p):
        key = (p.fingerprint, tuple(sorted(digest(e) for e in episodes)))
        if key not in cache:
            cache[key] = diagnose_episodes(episodes, p)
        return cache[key]
    backend = backend_factory()
    tests = [(r, backend.execute(r)) for r in EXPERIMENT_LIBRARY]
    assessments = []
    all_outcomes = []
    for size in (1,2):
        for group in itertools.combinations(tests, size):
            updated = refit([initial]+[rows for _,rows in group], protocol)
            all_outcomes.append(updated)
            assessments.append({"requests": [asdict(r) for r,_ in group],
                                "outcome": summary(updated),
                                "empirically_correct": updated.kind == "identified" and updated.selected == true_family})
    if any(a['empirically_correct'] for a in assessments):
        category = "resolvable"
    elif any(u.kind in ("optimization_failure", "model_inadequate") for u in all_outcomes):
        category = "undetermined"
    elif any(u.kind == "ambiguous" and set(u.competitive) < set(outcome.competitive)
             and true_family in u.competitive for u in all_outcomes):
        category = "partially_resolvable"
    else:
        category = "not_resolved_by_library"
    policies = {}
    for strategy in ("fixed", "random", "greedy"):
        execution = backend_factory()
        result = investigate(initial, protocol, execution.execute, strategy=strategy,
                             seed=seed, initial_outcome=outcome, refit=refit)
        result['correct'] = result['decision'] == true_family
        result['confidently_wrong'] = result['decision'] is not None and not result['correct']
        result['appropriate_abstention'] = result['decision'] is None and result['error'] is None
        result['ledger_valid'] = verify_ledger(result['ledger'])
        result['parameter_error'] = None
        policies[strategy] = result
    return {"classification": category, "assessments": assessments, "policies": policies,
            "cached_evidence_sets": len(cache),
            "initial_predicted_separation": {
                r.key: separation([f for f in outcome.fits if f.hypothesis in outcome.competitive],
                                  r, scales=protocol.scales,dt_s=protocol.dt_s)
                for r in EXPERIMENT_LIBRARY},
            "noise_matching": "Same request seed across policies; different requests independent"}


def accounting(records):
    qualifying=[r for r in records if r['operational']=='mission_failure']
    counts=Counter(r['passive']['kind'] for r in qualifying)
    supported=[r for r in qualifying if r['supported']]
    eligible=[r for r in records if r['eligible_ambiguity']]
    identified=[r for r in qualifying if r['passive']['kind']=='identified']
    active_summary={}
    for strategy in ('fixed','random','greedy'):
        trials=[r['active']['policies'][strategy] for r in eligible]
        active_summary[strategy]={
            'cases':len(trials),'correct':sum(t['correct'] for t in trials),
            'confidently_wrong':sum(t['confidently_wrong'] for t in trials),
            'abstained':sum(t['decision'] is None for t in trials),
            'errors':sum(t['error'] is not None for t in trials),
            'experiments':sum(t['tests'] for t in trials),'experimental_time_s':sum(t['time_s'] for t in trials),
            'constraint_violations':sum(t['tests']>2 or t['time_s']>30+1e-9 for t in trials),
            'resolution_interval_95_wilson':wilson(sum(t['correct'] for t in trials),len(trials)),
            'by_category':{cat:{'cases':len(sub),
                               'correct':sum(t['correct'] for t in sub),
                               'wrong':sum(t['confidently_wrong'] for t in sub),
                               'abstained':sum(t['decision'] is None for t in sub)}
                           for cat in ('resolvable','partially_resolvable','not_resolved_by_library','undetermined')
                           for sub in [[r['active']['policies'][strategy] for r in eligible
                                        if r['active']['classification']==cat]]}}
    return {"generated":len(records), "operational_failures":len(qualifying),
            "degradations":sum(r['operational']=='performance_degradation' for r in records),
            "unqualified":sum(r['operational']=='unqualified' for r in records),
            "supported_operational_failures":len(supported),
            "unsupported_operational_failures":len(qualifying)-len(supported),
            "identified_correctly":sum(r['correct_identification'] for r in identified),
            "confidently_wrong":sum(not r['correct_identification'] for r in identified),
            "ambiguous_public_all_families":counts['ambiguous'],
            "model_inadequate":counts['model_inadequate'],
            "optimization_failure":counts['optimization_failure'],
            "eligible_ambiguous_failures":len(eligible),
            "unsupported_ambiguous_failures":sum(not r['supported'] and r['passive']['kind']=='ambiguous' for r in qualifying),
            "ambiguity_rate_supported_failures":len(eligible)/len(supported) if supported else None,
            "ambiguity_rate_95_wilson":wilson(len(eligible),len(supported)),
            "resolvability":dict(Counter(r['active']['classification'] for r in eligible)),
            "active_strategies":active_summary,
            "all_pool_identified_correctly":sum(r['passive']['kind']=='identified' and r['correct_identification'] for r in records),
            "all_pool_confidently_wrong":sum(r['passive']['kind']=='identified' and not r['correct_identification'] for r in records),
            "all_pool_passive_outcomes":dict(Counter(r['passive']['kind'] for r in records))}


def run(manifest, destination):
    validate_manifest(manifest)
    destination = Path(destination)
    if destination.exists():
        raise ValueError("Refusing to overwrite an existing benchmark run")
    if ROOT == destination.resolve() or ROOT in destination.resolve().parents:
        raise ValueError("Benchmark outputs must be outside source")
    destination.mkdir(parents=True)
    private_write(destination/'manifest.json', manifest)
    records=[];started=time.perf_counter()
    for index,plan in enumerate(manifest['plans']):
        protocol=protocol_from(manifest['protocols'][plan['stratum']])
        scenario, plant=candidate(plan['seed'],plan['label'],plan['case_id'])
        case=evaluate_scenario(scenario,mission=Mission(duration_s=100),hidden_plant=plant)
        initial=[dict(r) for r in case.result.observations if r['time_s']<=protocol.duration_s+1e-9]
        outcome=passive(initial,protocol)
        true_family=oracle_family(scenario)
        supported=true_family is not None
        eligible=case.outcome=='mission_failure' and supported and outcome.kind=='ambiguous'
        record={**plan,'injected':asdict(scenario),'plant':asdict(plant),
                'operational':case.outcome,'qualification_reason':case.qualification_reason,
                'metrics':case.faulty_metrics,'matched_nominal_metrics':case.nominal_metrics,
                'supported':supported,'oracle_family':true_family,
                'correct_identification':outcome.kind=='identified' and outcome.selected==true_family,
                'passive':summary(outcome),'eligible_ambiguity':eligible,'active':None}
        true_fit=next((f for f in outcome.fits if f.hypothesis==true_family),None)
        record['passive_parameter_error']=({k:abs(v-getattr(scenario.faults,k))
                                            for k,v in true_fit.parameters.items()} if true_fit else None)
        if eligible:
            factory=lambda:HiddenExperimentBackend(faults=scenario.faults,controller=scenario.controller,
                                                   plant=plant,seed=plan['seed'],dt_s=protocol.dt_s)
            record['active']=assess(initial,outcome,protocol,factory,true_family,
                                    manifest['random_policy_seed_start']+index)
            for p in record['active']['policies'].values():
                truefit=next((f for f in p['outcome']['fits'] if f['hypothesis']==true_family),None)
                if truefit:
                    p['parameter_error']={k:abs(v-getattr(scenario.faults,k))
                                          for k,v in truefit['parameters'].items()}
        private_write(destination/(plan['case_id']+'.json'),record)
        records.append(record)
        print(plan['case_id'],case.outcome,outcome.kind,
              record['active']['classification'] if eligible else '-',flush=True)
    result={'manifest_fingerprint':manifest['fingerprint'], 'source_files':manifest['source_files'],
            'summary':accounting(records),'strata':{
                s:accounting([r for r in records if r['stratum']==s]) for s in ('primary','hard')},
            'elapsed_s':time.perf_counter()-started,
            'eligible_case_ids':[r['case_id'] for r in records if r['eligible_ambiguity']]}
    private_write(destination/'screening.json',result)
    return result


def pilot():
    records=[]
    for duration,start in ((30.,20000),(.5,30000)):
        p=PassiveProtocol(duration_s=duration)
        for i,label in enumerate(HARD_LABELS):
            scenario,plant=candidate(start+i,label,f'dev-{start+i}')
            case=evaluate_scenario(scenario,hidden_plant=plant)
            outcome=passive(case.result.observations,p)
            records.append({'case':scenario.case_id,'label':label,'duration':duration,
                            'operational':case.outcome,'passive':summary(outcome)})
            print(records[-1]['case'],label,duration,case.outcome,outcome.kind,outcome.competitive,flush=True)
    return {'split':'development_only','records':records,
            'decision':'No thresholds/noise changed; short recovered-log stratum declared before held-out screening.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('pilot','freeze','run'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--manifest',type=Path)
    args=parser.parse_args()
    if args.action=='run':
        if not args.manifest:parser.error('run requires a pre-existing frozen manifest')
        print(json.dumps(run(json.loads(args.manifest.read_text()),args.output),indent=2))
    else:
        if args.output.exists():parser.error('Refusing to overwrite existing output')
        if ROOT==args.output.resolve() or ROOT in args.output.resolve().parents:
            parser.error('Private outputs must be outside the source repository')
        private_write(args.output,pilot() if args.action=='pilot' else freeze())
