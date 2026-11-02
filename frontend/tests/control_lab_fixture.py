"""Emit a real V6 recommendation artifact for the frontend contract tests."""
import json

from nautilus.simulator import Controller
from nautilus.v6 import build_artifact, build_policy, build_suite, evaluate_suite

REFERENCE = 'a' * 64
suite = build_suite(duration_s=12., cable_length_m=8., specs=(('current_positive', {'current_y': .45}, {}, 9101),
                                                               ('nominal', {}, {}, 9102)))
robustness = evaluate_suite(Controller(), {'lookahead_m': 3.}, suite=suite)
change = None
if robustness['decision'] == 'accept':
    change = {'parameter': 'lookahead_m', 'value': 3.0,
              'rationale': 'Recorded cross-track excursions under lateral current support a shorter lookahead.',
              'evidence_refs': [REFERENCE], 'expected_effect': 'Lower mean cross-track RMS at the cost of slower arrivals.'}
artifact = build_artifact('fixture-investigation', [REFERENCE], build_policy(Controller()), change, robustness,
                          {'recommendation': 'accept' if change else 'reject',
                           'rationale': 'Host-measured development suite only; simulated tracking is not a physical repair.'})
print(json.dumps(artifact, sort_keys=True))
