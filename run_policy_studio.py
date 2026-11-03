"""Reproduce the Control Policy Studio acceptance scenarios A-E offline.

Every number in the output is produced by the real simulator through nautilus.studio; the Muse
provider is the deterministic offline mock. No model request is made, no credential is read and
no controller is deployed. Scenario F (website) needs the frontend and is not covered here.
"""
import argparse
import json
import time
from pathlib import Path

from nautilus.policy_ir import PolicyError, baseline_policy
from nautilus.policy_source import from_source, to_source
from nautilus.studio import paired_trial, policy_fingerprint, robustness
from nautilus.studio_muse import Budget, MockMuse, live_available, run_session

CANDIDATES = {
    'A': {'integral_ki': 6.0, 'integral_limit': 1.5},
    'B': {'integral_ki': 12.0, 'integral_limit': 2.5},
    'C': {'integral_ki': 0.02, 'integral_limit': 0.5},
}
HOSTILE = {
    'imports': 'import os\ndesired = 0.0',
    'attribute_access': 'desired = vehicle.x_true',
    'function_calls': 'desired = open("/etc/passwd")',
    'loops': 'while True:\n    desired = 0.0',
    'hidden_truth': 'desired = x_true',
    'state_mutation': 'desired = 0.0\nintegral_y = 99.0',
}


def candidate(overrides):
    """Baseline law with named parameter overrides; every other gain is preserved."""
    policy = baseline_policy()
    policy['params'] = {**policy['params'], **overrides}
    return policy


def trial(policy):
    development = paired_trial(policy)
    held_out = robustness(policy)
    return {
        'fingerprint': policy_fingerprint(policy),
        'params': policy['params'],
        'source': to_source(policy),
        'development': {
            'outcome': development['outcome'],
            'rows': [{k: row[k] for k in ('scenario_id', 'baseline', 'candidate')} for row in development['rows']],
            'gates': development['decision']['gates'],
            'acceptance': development['acceptance'],
        },
        'held_out': {'outcome': held_out['outcome'],
                     'rows': [{k: row[k] for k in ('scenario_id', 'baseline', 'candidate')} for row in held_out['rows']]},
        'structural_change': to_source(policy).splitlines() != to_source(baseline_policy()).splitlines(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    root = Path(__file__).resolve().parent
    if output == root or root in output.parents:
        parser.error('Output must be outside the repository')

    started = time.monotonic()
    report = {'branch_scope': 'feature/autonomous-control-policy-studio', 'operator_cli': True,
              'baseline_source': to_source(baseline_policy()),
              'baseline_fingerprint': policy_fingerprint(baseline_policy())}

    report['A_successful_improvement'] = trial(candidate(CANDIDATES['A']))
    report['B_rejected_modification'] = trial(candidate(CANDIDATES['B']))
    report['C_inconclusive'] = trial(candidate(CANDIDATES['C']))

    hostile = {}
    for name, source in HOSTILE.items():
        try:
            from_source(source)
        except PolicyError as error:
            hostile[name] = {'rejected': True, 'reason': str(error)}
        else:
            hostile[name] = {'rejected': False, 'reason': 'ACCEPTED - policy language is not safe'}
    report['D_hostile_policies'] = hostile

    session = run_session(provider=MockMuse(), budget=Budget())
    report['E_mock_iteration'] = {
        'model': session['model'], 'mock': session['mock'], 'provider_calls': session['provider_calls'],
        'live_available': live_available(), 'stopped': session['stopped'], 'final': session['final'],
        'budget': session['budget'], 'transcript': [{k: step[k] for k in step if k != 'result'} for step in session['transcript']],
        'outcomes': {cid: result['outcome']['label'] for cid, result in session['results'].items()},
    }
    report['elapsed_s'] = round(time.monotonic() - started, 2)
    report['F_website'] = {'status': 'not covered by this CLI', 'action': 'open the Policy Studio tab in the built frontend'}
    output.write_text(json.dumps(report, indent=2, default=str))
    for key in ('A_successful_improvement', 'B_rejected_modification', 'C_inconclusive'):
        outcome = report[key]['development']['outcome']
        print(f"{key}: {outcome['label']} · mean RMS difference {outcome['mean_rms_difference_m']:+.4f} m · failed {outcome['failed_gates']}")
    print('D_hostile_policies:', {k: v['rejected'] for k, v in hostile.items()})
    print('E_mock_iteration:', report['E_mock_iteration']['final'], report['E_mock_iteration']['outcomes'])
    print('wrote', output, f"in {report['elapsed_s']} s")


if __name__ == '__main__':
    main()
