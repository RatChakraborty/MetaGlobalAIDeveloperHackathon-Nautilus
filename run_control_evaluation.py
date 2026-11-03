"""Operator-triggered V6 control evaluation after a bounded investigation abstains.

Off by default. Runs the fixed V6 development suite on the candidate configuration
for named cause families. It is evaluated without a diagnosis: the investigation
abstained, so no result here is a repair that followed from a diagnosis.
"""
import argparse
import json
from pathlib import Path

from nautilus.simulator import Controller
from nautilus.v6.robustness import DEFAULT_SUITE, evaluate_suite

LABEL = 'evaluated without a diagnosis'
CAUSE_CASES = {
    'lateral_current': ('current_positive', 'current_negative'),
    'port_degradation': ('thruster_degradation',),
    'heading_bias': ('heading_bias',),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--candidate', required=True, help='JSON file of approved controller changes')
    parser.add_argument('--named-cause', action='append', default=[], choices=sorted(CAUSE_CASES))
    parser.add_argument('--run-control-evaluation', action='store_true', help='Required; off by default')
    args = parser.parse_args()
    if not args.run_control_evaluation:
        parser.error('Explicit --run-control-evaluation required; this path is off by default')
    if not args.named_cause:
        parser.error('At least one --named-cause is required')
    output = Path(args.output).resolve()
    root = Path(__file__).resolve().parent
    if output == root or root in output.parents:
        parser.error('Output must be outside the repository')
    changes = json.loads(Path(args.candidate).read_text())
    if type(changes) is not dict:
        parser.error('Candidate must be a JSON object of approved changes')

    baseline = Controller()
    full = evaluate_suite(baseline, changes, suite=DEFAULT_SUITE)
    wanted = {c for cause in args.named_cause for c in CAUSE_CASES[cause]}
    per_cause = {cause: [c for c in CAUSE_CASES[cause]] for cause in args.named_cause}
    result = {
        'label': LABEL,
        'diagnosis': None,
        'named_causes_for_scenario_selection_only': per_cause,
        'suite_scenarios_evaluated': full['suite'],
        'scenarios_of_named_causes': sorted(wanted),
        'per_scenario': full['per_scenario'],
        'regressions': [row['scenario_id'] for row in full['cases']
                        if row['candidate']['rms_cross_track_m'] > row['baseline']['rms_cross_track_m']],
        'acceptance': full['acceptance'],
        'decision': full['decision'],
        'decision_reasons': full['decision_reasons'],
        'failures': full['failures'],
        'suite_sha256': full['suite_sha256'],
        'limitations': full['limitations'] + [
            'Investigation abstained; this is not a repair that followed from a diagnosis.',
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(f'{LABEL}: decision={full["decision"]} wrote {output}')


if __name__ == '__main__':
    main()
