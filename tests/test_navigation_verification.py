import importlib.util
from pathlib import Path

import pytest

spec=importlib.util.spec_from_file_location('field_verify',Path(__file__).parents[1]/'scripts/verify_navigation.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_measured_rows_preview_and_missing_conventions_are_explicit():
    result=module.verify(b'lat,lon,time,yaw\n34,108,0,0\n34.0001,108.0001,0.1,0.2\n')
    assert result['valid_rows']==2
    assert result['transformation']['preview'][0]['east_m_assumed']==0
    assert result['transformation']['preview'][1]['east_m_assumed']>0
    assert result['compatibility']['bridge_executed'] is False
    assert result['checks']['heading_convention']=='Not verified'
    assert not result['matches_reviewed_source']
    assert result['checks']['source_license']=='Not verified'
    assert result['license']['name']=='unverified'


def test_bad_and_nonmonotonic_rows_do_not_become_verified_evidence():
    result=module.verify(b'lat,lon,time\n34,108,1\n34,108,0\nnan,108,2\n')
    assert result['excluded_rows']==[2]
    assert result['checks']['timestamp_monotonicity']=='Failed'
    with pytest.raises(ValueError):module.verify(b'lat,lon,time\nnan,108,0\n')
