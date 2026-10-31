from pathlib import Path
from dataclasses import replace, asdict
import argparse
import json
from nautilus.simulator import simulate, Mission, Faults, PlantConfig, Experiment
from nautilus.v2_models import REGISTRY, fit_model
from nautilus.reliability import fit, diagnose

PLANS = [('nominal', {}), ('actuator_lag', {'actuator_tau_s': .6}),
         ('thrust_deadzone', {'thrust_deadzone_n': 2.}),
         ('heading_bias', {'heading_bias_rad': .3}),
         ('heading_bias', {'heading_bias_rad': -.3}),
         ('unknown_longitudinal_current', {'current_x': .4})]


def run(output):
    output = Path(output).resolve()
    root = Path(__file__).resolve().parent
    if output == root or root in output.parents:
        raise ValueError('Private output must be outside source')
    output.mkdir(parents=True, exist_ok=True)
    plan = {'seeds': list(range(1100000, 1100006)), 'plans': PLANS,
            'duration_s': 4, 'methods': ['singleton', 'nuisance', 'discrepancy'],
            'starts': 2, 'max_nfev': 20,
            'scope': 'Exploratory development; not independent calibration or held-out evidence'}
    path = output/'plan.json'
    if not path.exists(): path.write_text(json.dumps(plan, indent=2))
    elif json.loads(path.read_text()) != json.loads(json.dumps(plan)): raise ValueError('Plan changed')
    for i, (truth, values) in enumerate(PLANS):
        faults = Faults(**{k: v for k, v in values.items() if k in Faults.__dataclass_fields__})
        plant = replace(PlantConfig(), actuator_tau_s=.12, thrust_deadzone_n=.25, drag_scale=1.02,
                        **{})
        plant = replace(plant, **{k: v for k, v in values.items() if k in PlantConfig.__dataclass_fields__})
        experiment = Experiment()
        observations = simulate(faults=faults, plant=plant, mission=Mission(duration_s=4, seed=1100000+i)).observations
        episodes = [{'observations': observations, 'experiment': experiment}]
        for method in plan['methods']:
            path = output/f'{i}-{method}.json'
            if path.exists(): continue
            fits = []
            for name in REGISTRY:
                if method == 'singleton':
                    f = asdict(fit_model(episodes, name, starts=2, max_nfev=20))
                else: f = fit(episodes, name, method=method, starts=2, max_nfev=20)
                fits.append(f)
            result = {'true_family_private': truth, 'injection_private': values,
                      'seed': 1100000+i, 'method': method, 'observations': observations, 'fits': fits}
            if method != 'singleton': result['decision'] = diagnose(fits)
            serialized = json.dumps(result, indent=2, allow_nan=False)
            with path.open('x') as stream: stream.write(serialized)
            print(i, method, result.get('decision', {}).get('status', 'legacy'), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    run(parser.parse_args().output)
