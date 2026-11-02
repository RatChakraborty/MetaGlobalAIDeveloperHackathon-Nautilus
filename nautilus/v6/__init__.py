"""V6 verified control-policy testing laboratory.

Adds a versioned control-policy contract, matched candidate/baseline evaluation,
a fixed robustness suite with a predeclared acceptance rule, bounded proposal
search, a host-owned model phase, a reviewable recommendation artifact and an
optional restricted source-patch lab. The simulator and evaluator are unchanged.
"""
from .artifact import SCHEMA as ARTIFACT_SCHEMA, build as build_artifact, configuration_diff, export_artifact, validate as validate_artifact
from .evaluation import CaseEvaluation, evaluate_case
from .host import ControlLabHost
from .patch import FEATURE_FLAG, enabled as patch_lab_enabled, review as review_patch
from .policy import TUNABLE, build_policy, candidate, differences, identity, validate_policy
from .proposal import GRID, coordinate_search, screen, validate_change
from .robustness import ACCEPTANCE, DEFAULT_SUITE, build_suite, decide, evaluate_suite, validate_robustness

__all__ = ['ARTIFACT_SCHEMA', 'ACCEPTANCE', 'CaseEvaluation', 'ControlLabHost', 'DEFAULT_SUITE', 'FEATURE_FLAG',
           'GRID', 'TUNABLE', 'build_artifact', 'build_policy', 'build_suite', 'candidate', 'configuration_diff',
           'coordinate_search', 'decide', 'differences', 'evaluate_case', 'evaluate_suite', 'export_artifact',
           'identity', 'patch_lab_enabled', 'review_patch', 'screen', 'validate_artifact', 'validate_change',
           'validate_policy', 'validate_robustness']
