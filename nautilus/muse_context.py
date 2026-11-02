"""Reversible public tool-result presentation; no summarization or measurement loss."""
from copy import deepcopy
import math
from .controller_context import canonical, fingerprint
from .simulator import OBSERVATION_FIELDS

SCHEMA = 'nautilus.muse-observation-array.v1'


def _encode(value):
    if type(value) is list:
        if value and all(type(row) is dict and set(row)==set(OBSERVATION_FIELDS) for row in value):
            if any(type(v) not in (int,float) or not math.isfinite(v) for row in value for v in row.values()):
                raise ValueError('Finite public observation channels required')
            return {'schema_version':SCHEMA,'channels':list(OBSERVATION_FIELDS),
                    'samples':[[row[k] for k in OBSERVATION_FIELDS] for row in value],
                    'sha256':fingerprint(value)}
        return [_encode(item) for item in value]
    if type(value) is dict:
        return {key:_encode(item) for key,item in value.items()}
    return deepcopy(value)


def restore_result(value):
    """Independent decoder verifies channel order, values and original row hash."""
    if type(value) is dict:
        if value.get('schema_version')==SCHEMA:
            if set(value)!={'schema_version','channels','samples','sha256'} or value['channels']!=list(OBSERVATION_FIELDS) or type(value['samples']) is not list:
                raise ValueError('Invalid observation-array encoding')
            rows=[]
            for sample in value['samples']:
                if type(sample) is not list or len(sample)!=len(OBSERVATION_FIELDS) or any(type(v) not in (int,float) or not math.isfinite(v) for v in sample):
                    raise ValueError('Invalid observation-array sample')
                rows.append(dict(zip(OBSERVATION_FIELDS,sample)))
            if fingerprint(rows)!=value['sha256']: raise ValueError('Observation-array hash mismatch')
            return rows
        return {key:restore_result(item) for key,item in value.items()}
    if type(value) is list: return [restore_result(item) for item in value]
    return deepcopy(value)


def project_result(value):
    """Only repeated row keys are factored. All other fields remain unchanged.

    Fits, units in the retained initial registry, residuals, warnings and safety
    metadata are not summarized or filtered. No provider conversation is reset.
    """
    projected=_encode(value)
    original_bytes=len(canonical(value).encode())
    projected_bytes=len(canonical(projected).encode())
    if projected_bytes>=original_bytes:
        projected=deepcopy(value);projected_bytes=original_bytes
    if canonical(restore_result(projected))!=canonical(value):
        raise ValueError('Tool-result presentation was not lossless')
    return projected, {'schema_version':'nautilus.muse-result-presentation.v1',
        'encoding':'identity' if projected==value else 'lossless_row_arrays',
        'original_bytes':original_bytes,'projected_bytes':projected_bytes,
        'original_sha256':fingerprint(value),'projected_sha256':fingerprint(projected)}
