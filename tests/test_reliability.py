import numpy as np
import pytest
from nautilus.reliability import fit, diagnose, residual_diagnostics
from nautilus.simulator import simulate, Mission, Experiment


def test_public_schema_and_parameter_accounting():
    rows = simulate(mission=Mission(duration_s=.3)).observations
    episode = {'observations': rows, 'experiment': Experiment()}
    result = fit([episode], 'actuator_lag', starts=1, max_nfev=5)
    assert result['parameter_count'] == 3
    assert len(result['predictions'][0]) == len(rows)
    assert result['bounds']['thrust_deadzone_n'] == (0., .5)
    rows[0]['true_x'] = 0
    with pytest.raises(ValueError): fit([episode], 'nominal')


def test_residual_and_status_rules():
    diagnostics = residual_diagnostics([np.ones((10, 3))])
    assert diagnostics[0][0]['mean'] == 1
    assert diagnostics[0][0]['lag1'] is None
    assert diagnose([])['status'] == 'OPTIMIZATION_FAILURE'
    f = {'hypothesis': 'nominal', 'converged': True, 'wrms': 1., 'score': 0.,
         'rank': 3, 'parameter_count': 3, 'bound_hits': [], 'residual_diagnostics': diagnostics}
    assert diagnose([f])['status'] == 'IDENTIFIED'
    assert diagnose([{**f, 'bound_hits': ['drag_scale']}])['status'] == 'AMBIGUOUS'
    assert diagnose([{**f, 'wrms': 3}])['status'] == 'MODEL_INADEQUATE'
