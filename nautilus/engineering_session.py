"""Public evidence linkage; generation inputs remain on the trusted host path."""
from copy import deepcopy
import hashlib
import json
import math
import re
from types import SimpleNamespace

from .controller_context import canonical, fingerprint
from .simulator import OBSERVATION_FIELDS

SCHEMA = 'nautilus.engineering-context.v1'


def context_from_result(result, actor='deterministic_baseline'):
    events = result['investigation']['ledger']
    from .investigation import verify_ledger
    if not events or not verify_ledger(events):
        raise ValueError('Verified investigation ledger required')
    episodes = []
    for event in events:
        if 'observations' in event:
            rows = event['observations']
            indices = sorted({round(i*(len(rows)-1)/min(31, len(rows)-1)) for i in range(min(32, len(rows)))})
            episodes.append({'evidence_ref': event['event_hash'], 'trace_hash': fingerprint(rows),
                             'sample_count': len(rows), 'observations': [rows[i] for i in indices],
                             'sampling': 'Uniform recorded sample subset; full trace hash retained.'})
    outcome = result['investigation']['outcome']
    return _context(episodes, outcome, events, result['protocol_fingerprint'], actor)


def context_from_muse(record, provenance):
    from .muse_investigator import validate_provenance
    validate_provenance(provenance, record)
    events = [{**json.loads(e['body_canonical']), 'event_hash': e['hash']} for e in record['ledger']]
    episodes = []
    for event in events:
        if event['type'] == 'observation':
            rows = event['observations']; n = len(rows)
            indices = sorted({round(i*(n-1)/min(31, n-1)) for i in range(min(32, n))})
            episodes.append({'evidence_ref': event['event_hash'], 'trace_hash': fingerprint(rows),
                             'sample_count': n, 'observations': [rows[i] for i in indices],
                             'sampling': 'Uniform recorded sample subset; full trace hash retained.'})
    fits = [e['report'] for e in events if e['type'] == 'fit']
    final = next((e for e in reversed(events) if e['type'] == 'finalized'), {})
    outcome = {'kind': final.get('confidence', 'stopped'), 'selected': final.get('diagnosis', {}).get('hypothesis'),
               'competitive': [], 'reasons': [final.get('stop_reason', 'No final diagnosis recorded')], 'fits': fits}
    return _context(episodes, outcome, events, provenance['hash'], 'meta_muse')


def _wrms(report):
    value = report.get('wrms', report.get('weighted_rmse'))
    return value if type(value) in (int,float) and math.isfinite(value) else math.inf


def _context(episodes, outcome, events, protocol, actor):
    if actor not in ('deterministic_baseline', 'meta_muse') or not 1 <= len(episodes) <= 3:
        raise ValueError('Bounded public investigation required')
    refs = [e['evidence_ref'] for e in episodes]
    fits = []
    latest = {}
    for f in outcome.get('fits', []): latest[f['hypothesis']] = f
    for f in sorted(latest.values(), key=_wrms)[:8]:
        fits.append({'hypothesis': f['hypothesis'], 'converged': bool(f.get('converged',False)),
                     'parameters': f.get('parameters', {}), 'weighted_rmse': (lambda v: v if type(v) in (int,float) and math.isfinite(v) else None)(f.get('wrms', f.get('weighted_rmse'))),
                     'identifiability': {'rank': f.get('identifiability', {}).get('rank'),
                                        'condition': f.get('identifiability', {}).get('condition'),
                                        'qualification': 'Local fit diagnostics do not establish physical attribution.'},
                     'evidence_refs': refs, 'status': 'candidate_hypothesis'})
    body = {'schema_version': SCHEMA, 'actor': actor, 'protocol_fingerprint': protocol,
            'ledger_head': events[-1]['event_hash'], 'episodes': episodes, 'hypotheses': fits,
            'outcome': {k: outcome.get(k) for k in ('kind', 'selected', 'competitive', 'reasons')},
            'actions': [{'evidence_ref': e['event_hash'], 'type': e['type'],
                         'actor': actor if e['type'] in ('experiment_selected', 'request', 'finalized') else 'trusted_host',
                         'experiment': _experiment(e.get('request'))}
                        for e in events],
            'limitations': ['Public observations only; hypotheses are conditional, not proven causes.',
                            'Tracking improvement does not confirm fault identification.',
                            'Displayed telemetry is a recorded subset; full source hashes identify each episode.']}
    body['session_id'] = fingerprint({'head': body['ledger_head'], 'protocol': protocol, 'actor': actor})
    return {'body_canonical': canonical(body), 'hash': fingerprint(body)}


def _experiment(request):
    if request is None:
        return None
    if type(request) is not dict:
        raise ValueError('Invalid public experiment')
    if set(request) == {'cruise_thrust_n','duration_s'}:
        from .experiments import ExperimentRequest
        ExperimentRequest(**request)
    else:
        from .v2_experiments import Trial
        if set(request) != set(Trial.__dataclass_fields__):
            raise ValueError('Unsupported public experiment fields')
        Trial(**request)
    return deepcopy(request)


def validate_context(value):
    if type(value) is not dict or set(value) != {'body_canonical', 'hash'} or type(value['body_canonical']) is not str or len(value['body_canonical']) > 50000:
        raise ValueError('Invalid engineering context envelope')
    if hashlib.sha256(value['body_canonical'].encode()).hexdigest() != value['hash']:
        raise ValueError('Engineering context hash mismatch')
    body = json.loads(value['body_canonical'])
    required = {'schema_version', 'actor', 'session_id', 'protocol_fingerprint', 'ledger_head', 'episodes', 'hypotheses', 'outcome', 'actions', 'limitations'}
    if type(body) is not dict or set(body) != required or body['schema_version'] != SCHEMA or body['actor'] not in ('deterministic_baseline', 'meta_muse'):
        raise ValueError('Invalid engineering context fields')
    if any(type(body[k]) is not str or not re.fullmatch('[a-f0-9]{64}',body[k]) for k in ('session_id','ledger_head','protocol_fingerprint')):
        raise ValueError('Invalid evidence fingerprints')
    if body['session_id'] != fingerprint({'head': body['ledger_head'], 'protocol': body['protocol_fingerprint'], 'actor': body['actor']}):
        raise ValueError('Engineering session identity mismatch')
    if type(body['outcome']) is not dict or set(body['outcome']) != {'kind','selected','competitive','reasons'}:
        raise ValueError('Invalid public diagnosis fields')
    out = body['outcome']
    if (type(out['kind']) is not str or len(out['kind']) > 80
        or (out['selected'] is not None and (type(out['selected']) is not str or len(out['selected']) > 80))
        or any(type(out[k]) is not list or len(out[k]) > 32 or any(type(s) is not str or len(s) > 500 for s in out[k]) for k in ('competitive','reasons'))):
        raise ValueError('Invalid public diagnosis values')
    if type(body['hypotheses']) is not list or len(body['hypotheses']) > 8:
        raise ValueError('Bounded hypothesis set required')
    if type(body['episodes']) is not list or not 1 <= len(body['episodes']) <= 3:
        raise ValueError('Bounded episodes required')
    for ep in body['episodes']:
        if type(ep) is not dict or set(ep) != {'evidence_ref', 'trace_hash', 'sample_count', 'observations', 'sampling'} or type(ep['sample_count']) is not int or ep['sample_count'] < 2 or type(ep['observations']) is not list or not 2 <= len(ep['observations']) <= 32:
            raise ValueError('Invalid engineering episode')
        if any(type(ep[k]) is not str or not re.fullmatch('[a-f0-9]{64}',ep[k]) for k in ('evidence_ref','trace_hash')) or ep['sample_count'] < len(ep['observations']) or type(ep['sampling']) is not str or len(ep['sampling']) > 200:
            raise ValueError('Invalid episode provenance')
        last = -1
        for row in ep['observations']:
            if type(row) is not dict or set(row) != set(OBSERVATION_FIELDS) or any(type(v) not in (int, float) or not math.isfinite(v) for v in row.values()) or row['time_s'] <= last:
                raise ValueError('Exactly six ordered public channels required')
            last = row['time_s']
        if ep['observations'][0]['time_s'] != 0:
            raise ValueError('Reset-aligned public telemetry required')
    from .studio_handoff import validate_handoff
    validate_handoff(handoff_from_context(value, validate=False))
    if type(body['actions']) is not list or len(body['actions']) > 128 or any(type(a) is not dict or set(a) != {'evidence_ref', 'type', 'actor', 'experiment'} for a in body['actions']):
        raise ValueError('Invalid public action references')
    if any(any(type(a[k]) is not str or len(a[k]) > 100 for k in ('evidence_ref','type','actor')) or not re.fullmatch('[a-f0-9]{64}',a['evidence_ref']) or a['actor'] not in ('trusted_host',body['actor']) for a in body['actions']):
        raise ValueError('Invalid action provenance')
    for action in body['actions']:
        _experiment(action['experiment'])
    return body


def handoff_from_context(value, validate=True):
    b = validate_context(value) if validate else json.loads(value['body_canonical'])
    return {'schema_version': 'nautilus.studio-handoff.v1',
            'reproducibility': {'run_id': b['session_id'], 'source_kind': b['actor'], 'ledger_head': b['ledger_head'], 'events': len(b['actions'])},
            'observations': {'episodes': len(b['episodes']), 'evidence_refs': [e['evidence_ref'] for e in b['episodes']],
                             'max_abs_observed_y_m': max(abs(r['observed_y_m']) for e in b['episodes'] for r in e['observations'])},
            'hypotheses': b['hypotheses'][:4], 'conclusion': {'diagnosis': b['outcome']['selected'],
                'confidence': b['outcome']['kind'], 'ambiguity_statement': '; '.join(b['outcome']['reasons'] or [])[:200],
                'evidence_refs': [e['evidence_ref'] for e in b['episodes']], 'status': 'recorded_conclusion_not_proof'},
            'limitations': b['limitations']}


def linked_trial(policy, context, request):
    from .studio import paired_trial, _row, outcome
    from .simulator import HIDDEN_PLANT, Controller, Vehicle, simulate
    from .v6.robustness import decide
    from nautilus_api.schema import scenario
    body = validate_context(context)
    faults, mission, normalized = scenario(request)
    base = simulate(faults=faults, mission=mission, controller=Controller(), plant=HIDDEN_PLANT)
    if fingerprint(base.observations) != body['episodes'][0]['trace_hash']:
        raise ValueError('Scenario does not reproduce the investigation telemetry')
    selected = SimpleNamespace(identifier='investigated_run', faults=faults, mission=mission, vehicle=Vehicle(), plant=HIDDEN_PLANT)
    trial = paired_trial(policy)
    row, trace = _row(selected, policy)
    trial['rows'].append(row); trial['traces']['investigated_run'] = trace
    trial['decision'] = decide([{k: r[k] for k in ('scenario_id', 'baseline', 'candidate')} for r in trial['rows']])
    trial['outcome'] = outcome(trial['decision'], trial['rows'])
    trial['session_id'] = body['session_id']; trial['evidence_hash'] = context['hash']
    trial['scenario_fingerprint'] = fingerprint(normalized)
    return trial


def final_decision(trial, held_out):
    same = trial['policy_fingerprint'] == held_out['policy_fingerprint'] and held_out['part'] == 'held_out'
    accepted = same and trial['outcome']['label'] == held_out['outcome']['label'] == 'Recommended'
    return {'actor': 'trusted_host', 'decision': 'recommend' if accepted else 'withhold',
            'candidate_fingerprint': trial['policy_fingerprint'], 'session_id': trial.get('session_id'),
            'evidence_hash': trial.get('evidence_hash'), 'same_candidate': same,
            'development_passed': trial['outcome']['label'] == 'Recommended',
            'held_out_passed': held_out['outcome']['label'] == 'Recommended',
            'qualification': 'Simulation-only recommendation; operator review required. No physical repair verified.'}


def context_from_simulation(observations, diagnosis, protocol):
    body = {'index': 0, 'type': 'initial_observation', 'previous_hash': None,
            'observations': observations, 'trace_hash': fingerprint(observations),
            'diagnosis': diagnosis, 'protocol_fingerprint': protocol}
    event = {**body, 'event_hash': fingerprint(body)}
    return context_from_result({'investigation': {'ledger': [event], 'outcome': diagnosis},
                                'protocol_fingerprint': protocol})
