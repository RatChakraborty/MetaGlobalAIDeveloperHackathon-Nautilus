"""Validate the public investigation evidence handed to Policy Studio.

The browser builds this payload from a verified public ledger. The server re-checks its exact
shape, bounds every number and string, and rejects any unexpected key, so hidden fault truth,
private evaluator results or simulator internals cannot enter the controller-engineering loop
through the handoff.
"""
import math

SCHEMA = 'nautilus.studio-handoff.v1'
MAX_HYPOTHESES = 4
MAX_REFS = 16
MAX_PARAMS = 8
MAX_TEXT = 200

_TOP = {'schema_version', 'reproducibility', 'observations', 'hypotheses', 'conclusion', 'limitations'}
_REPRO = {'run_id', 'source_kind', 'ledger_head', 'events'}
_OBS = {'episodes', 'evidence_refs', 'max_abs_observed_y_m'}
_HYP = {'hypothesis', 'converged', 'parameters', 'weighted_rmse', 'identifiability', 'evidence_refs', 'status'}
_IDENT = {'rank', 'condition', 'qualification'}
_CONC = {'diagnosis', 'confidence', 'ambiguity_statement', 'evidence_refs', 'status'}


class HandoffError(ValueError):
    pass


def _keys(obj, allowed, where):
    if type(obj) is not dict:
        raise HandoffError(f'{where} must be an object')
    extra = set(obj) - allowed
    if extra:
        raise HandoffError(f'{where} has unexpected fields: {sorted(extra)}')


def _num(value, where, optional=True):
    if value is None and optional:
        return None
    if type(value) not in (int, float) or not math.isfinite(value):
        raise HandoffError(f'{where} must be a finite number')
    return float(value)


def _text(value, where, optional=True):
    if value is None and optional:
        return None
    if type(value) is not str or len(value) > MAX_TEXT:
        raise HandoffError(f'{where} must be text of at most {MAX_TEXT} characters')
    return value


def _refs(value, where):
    if type(value) is not list or len(value) > MAX_REFS or not all(type(r) is str and len(r) <= 128 for r in value):
        raise HandoffError(f'{where} must be a list of evidence references')
    return list(value)


def validate_handoff(payload):
    """Return a sanitised copy of the handoff, or raise HandoffError."""
    _keys(payload, _TOP, 'handoff')
    if payload.get('schema_version') != SCHEMA:
        raise HandoffError('unsupported handoff schema')
    repro = payload.get('reproducibility')
    _keys(repro, _REPRO, 'reproducibility')
    obs = payload.get('observations')
    _keys(obs, _OBS, 'observations')
    hypotheses = payload.get('hypotheses')
    if type(hypotheses) is not list or len(hypotheses) > MAX_HYPOTHESES:
        raise HandoffError('hypotheses must be a list of at most %d entries' % MAX_HYPOTHESES)
    clean_hyp = []
    for index, item in enumerate(hypotheses):
        where = f'hypotheses[{index}]'
        _keys(item, _HYP, where)
        if item.get('status') != 'candidate_hypothesis':
            raise HandoffError(f'{where} must be labelled as a candidate hypothesis')
        params = item.get('parameters')
        if type(params) is not dict or len(params) > MAX_PARAMS:
            raise HandoffError(f'{where}.parameters must be an object of at most {MAX_PARAMS} entries')
        ident = item.get('identifiability')
        _keys(ident, _IDENT, f'{where}.identifiability')
        if type(item.get('converged')) is not bool:
            raise HandoffError(f'{where}.converged must be a boolean')
        clean_hyp.append({
            'hypothesis': _text(item.get('hypothesis'), f'{where}.hypothesis', optional=False),
            'converged': item['converged'],
            'parameters': {_text(k, f'{where}.parameter name', optional=False): _num(v, f'{where}.parameters', False)
                           for k, v in params.items()},
            'weighted_rmse': _num(item.get('weighted_rmse'), f'{where}.weighted_rmse'),
            'identifiability': {
                'rank': _num(ident.get('rank'), f'{where}.rank'),
                'condition': _num(ident.get('condition'), f'{where}.condition'),
                'qualification': _text(ident.get('qualification'), f'{where}.qualification'),
            },
            'evidence_refs': _refs(item.get('evidence_refs'), f'{where}.evidence_refs'),
            'status': 'candidate_hypothesis',
        })
    conclusion = payload.get('conclusion')
    clean_conclusion = None
    if conclusion is not None:
        _keys(conclusion, _CONC, 'conclusion')
        if conclusion.get('status') != 'recorded_conclusion_not_proof':
            raise HandoffError('conclusion must be labelled as a recorded conclusion, not proof')
        clean_conclusion = {
            'diagnosis': _text(conclusion.get('diagnosis'), 'conclusion.diagnosis'),
            'confidence': _text(conclusion.get('confidence'), 'conclusion.confidence'),
            'ambiguity_statement': _text(conclusion.get('ambiguity_statement'), 'conclusion.ambiguity_statement'),
            'evidence_refs': _refs(conclusion.get('evidence_refs'), 'conclusion.evidence_refs'),
            'status': 'recorded_conclusion_not_proof',
        }
    limitations = payload.get('limitations')
    if type(limitations) is not list or len(limitations) > 12:
        raise HandoffError('limitations must be a list of at most 12 entries')
    return {
        'schema_version': SCHEMA,
        'reproducibility': {
            'run_id': _text(repro.get('run_id'), 'run_id', optional=False),
            'source_kind': _text(repro.get('source_kind'), 'source_kind', optional=False),
            'ledger_head': _text(repro.get('ledger_head'), 'ledger_head'),
            'events': int(_num(repro.get('events'), 'events', optional=False)),
        },
        'observations': {
            'episodes': int(_num(obs.get('episodes'), 'episodes', optional=False)),
            'evidence_refs': _refs(obs.get('evidence_refs'), 'observations.evidence_refs'),
            'max_abs_observed_y_m': _num(obs.get('max_abs_observed_y_m'), 'max_abs_observed_y_m'),
        },
        'hypotheses': clean_hyp,
        'conclusion': clean_conclusion,
        'limitations': [_text(t, 'limitation', optional=False) for t in limitations],
    }
