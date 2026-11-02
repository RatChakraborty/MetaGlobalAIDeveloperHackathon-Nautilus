"""Explicit V4 wrapper; shortened complete telemetry supported, channel gaps deferred."""
from ..simulator import OBSERVATION_FIELDS
from ..diagnosis import _prepare,FitConfig


def wrap(rows):
    return {'schema_version':'nautilus.observations.v4','channels':list(OBSERVATION_FIELDS),'rows':rows,'missingness_mask':[[False]*6 for _ in rows],'scope':'Complete six-channel samples, possibly shortened time window.'}


def legacy(value):
    if type(value) is not dict or set(value)!={'schema_version','channels','rows','missingness_mask','scope'} or value['schema_version']!='nautilus.observations.v4' or value['channels']!=list(OBSERVATION_FIELDS):raise ValueError('Invalid V4 observation envelope')
    if len(value['missingness_mask'])!=len(value['rows']) or any(type(mask) is not list or len(mask)!=6 or any(type(v) is not bool for v in mask) for mask in value['missingness_mask']):raise ValueError('Invalid missingness mask')
    if any(any(mask) for mask in value['missingness_mask']):raise ValueError('Missing-channel/gap fitting is disabled; never replace missing measurements with zero')
    _prepare(value['rows'],FitConfig(method='observer'));return value['rows']
