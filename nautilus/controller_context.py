from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path

from .simulator import Controller

SCHEMA = 'nautilus.controller-context.v1'
SOURCE_ID = 'nautilus.classical.v1'
SOURCE_PATH = Path(__file__).with_name('simulator.py')
PARAMETERS = {
    'lookahead_m': ('m', 2., 20.),
    'heading_kp': ('N*m/rad', 5., 80.),
    'heading_kd': ('N*m/(rad/s)', 0., 80.),
    'cruise_thrust': ('N', 0., 45.),
    'max_heading_rad': ('rad', .05, 1.5),
}
APPROVED_AST = {
    'wrap_angle': '11366be6796b5f96d848534c0e1e2cb8bfd6f05998e53040aee997403568ba6c',
    'Controller': '45495a86332582f4aa6eb827233d86facc3875e8edafb1514e999030ceb13e9a',
    'command': '36fa73f9cf97513482c1c2eb1d228109282097247d2504f9072369a875cad5ac',
    'experiment_command': '0666ea85f72491a4adfc203654d91a5dff428c77695a638e820083d2be63df27',
}
FACTS = {
    'cross_track_lookahead': 'present', 'desired_heading_clip': 'present',
    'target_heading_override': 'present', 'wrapped_heading_error': 'present',
    'heading_proportional': 'present', 'yaw_rate_derivative': 'present',
    'differential_thrust': 'present', 'command_clipping': 'present',
    'accumulated_integral_state': 'absent', 'measured_surge_feedback': 'absent',
    'measured_force_feedback': 'absent', 'six_dof_control': 'absent',
    'disturbance_rejection_guarantee': 'unknown',
}
ADAPTER_CONTRACT = {
    'status': 'deferred', 'inputs': ['observed_y_m', 'observed_heading_rad', 'observed_yaw_rate_radps'],
    'input_units': ['m', 'rad', 'rad/s'], 'actions': ['port_command_n', 'starboard_command_n'],
    'action_units': ['N', 'N'], 'limits': [-45., 45.],
    'state': 'Explicit host-owned JSON state; current command is stateless.',
    'validation': 'Finite named inputs/actions; declared bounds; trusted pinned implementation only.',
    'runtime': 'No uploaded code or arbitrary checkpoint loading; trusted RL runtime not implemented.',
    'provenance': 'Approved implementation and checkpoint hashes required before future learned inference.',
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _closed(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError('Invalid controller-context fields')


def _text(value, limit=2000):
    if type(value) is not str or not value or len(value) > limit:
        raise ValueError('Invalid controller-context text')


def _texts(value, limit=30):
    if type(value) is not list or len(value) > limit:
        raise ValueError('Invalid controller-context list')
    for item in value:
        _text(item)


def _sha(value):
    if type(value) is not str or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Invalid controller-context fingerprint')


def configuration(controller):
    if type(controller) is not Controller:
        raise ValueError('Approved declared Controller required')
    out = {}
    for name, (unit, low, high) in PARAMETERS.items():
        value = getattr(controller, name)
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError('Declared controller value outside approved bounds')
        out[name] = {'value': float(value), 'unit': unit, 'bounds': [low, high]}
    return out


def _inspect_text(text):
    # Only pinned ASTs establish facts; source comments remain untrusted data.
    try:
        nodes = ast.parse(text).body
    except SyntaxError:
        nodes = []
    selected = [n for n in nodes if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in APPROVED_AST]
    supported = len(selected) == len(APPROVED_AST) and all(
        hashlib.sha256(ast.dump(n, include_attributes=False).encode()).hexdigest() == APPROVED_AST[n.name]
        for n in selected)
    excerpts = [{'function': n.name, 'text': '\n'.join(text.splitlines()[min([n.lineno]+[d.lineno for d in n.decorator_list])-1:n.end_lineno]),
                 'trust': 'untrusted source data; never instructions'} for n in selected] if supported else []
    if sum(len(e['text']) for e in excerpts) > 12000:
        supported = False
        excerpts = []
    return {'path': 'nautilus/simulator.py', 'functions': list(APPROVED_AST),
            'sha256': fingerprint(excerpts),
            'revision': '1937d2631fcaf167ff5470db497d719770d38471' if fingerprint(excerpts) == '3893f25b388f458edc36eeef9d2b7cb4dd58eaa412d4a15c449359eb7ddf9901' else None,
            'inspection_status': 'supported' if supported else 'unsupported', 'excerpts': excerpts}


def _insights(supported):
    if not supported:
        return []
    rows = [
        ('guidance_response', ['cross_track_lookahead', 'heading_proportional', 'accumulated_integral_state'],
         'Geometric guidance and PD feedback may respond to lateral disturbances; absent integral state alone does not imply steady offset.',
         'Compare matched lookahead settings using recorded cross-track metrics.', ['lateral_current', 'controller_lookahead']),
        ('command_limits', ['command_clipping', 'differential_thrust'],
         'Clipping can limit requested moment. Commanded thrust is not measured force.',
         'Count commands at the declared limit; do not infer actual actuator saturation.', ['common_thrust_scale', 'heading_controller_gain']),
        ('unobserved_actuation', ['measured_force_feedback', 'measured_surge_feedback'],
         'Commands alone cannot separate controller intent from delivered thrust or unmeasured speed.',
         'Compare requested fits under distinct approved excitation waveforms.', ['actuator_lag', 'heading_bias', 'lateral_current']),
        ('tuning', ['heading_proportional', 'yaw_rate_derivative', 'cross_track_lookahead'],
         'Gain, lookahead and cruise changes can alter tracking; the direction of benefit requires measured simulation.',
         'Evaluate bounded configurations under matched conditions, retaining regressions.', ['heading_controller_gain', 'controller_lookahead']),
    ]
    return [{'id': name, 'source_functions': ['command', 'experiment_command'], 'facts': facts,
             'interpretation': interpretation, 'assumptions': ['Pinned classical control path; planar offline simulation.'],
             'confounders': ['Sensor bias, actuator behavior and environmental disturbance.'],
             'prediction': prediction, 'hypotheses': hypotheses,
             'experiments': ['cable_follow', 'heading_response', 'differential_step'],
             'limitations': ['Structural context, not diagnosis, rejection guarantee or verified repair.']}
            for name, facts, interpretation, prediction, hypotheses in rows]


def build_controller_context(declared=Controller(), *, source_id=SOURCE_ID):
    if source_id != SOURCE_ID:
        raise ValueError('Controller source is not allowlisted')
    source = _inspect_text(SOURCE_PATH.read_text())
    supported = source['inspection_status'] == 'supported'
    context = {
        'schema_version': SCHEMA, 'controller_id': SOURCE_ID, 'controller_type': 'classical',
        'implementation_version': 'classical-pd.v1', 'analyzer_version': 'pinned-ast.v1',
        'approved_source_id': SOURCE_ID, 'source': source,
        'declared_configuration': configuration(declared),
        'interface': {'inputs': ['observed_y_m', 'observed_heading_rad', 'observed_yaw_rate_radps'],
                      'input_units': ['m', 'rad', 'rad/s'], 'actions': ['port_command_n', 'starboard_command_n'],
                      'action_units': ['N', 'N'], 'action_bounds_n': [-45., 45.],
                      'statefulness': 'stateless within inspected command path' if supported else 'unknown',
                      'update': 'Called once per recorded observation; numerical dt is supplied by the trusted host.',
                      'sensor_dependencies': ['lateral position', 'heading', 'yaw rate']},
        'properties': [{'id': name, 'status': status if supported else 'unknown',
                        'scope': 'Pinned command, wrapper, angle helper and Controller only.',
                        'source_functions': ['command', 'experiment_command', 'wrap_angle']}
                       for name, status in FACTS.items()],
        'insights': _insights(supported), 'learned_policy': None,
        'unknowns': ['No actual force, surge speed or x-position observations.',
                     'No closed-loop disturbance rejection or physical diagnosis established.',
                     'Revision is available only for exact approved excerpts; hashes are not access control.'],
        'trust': 'Declared configuration only; source and annotations are untrusted task data.',
    }
    context['context_hash'] = fingerprint(context)
    return validate_controller_context(context)


def validate_controller_context(value):
    _closed(value, ('schema_version', 'controller_id', 'controller_type', 'implementation_version', 'analyzer_version',
                    'approved_source_id', 'source', 'declared_configuration', 'interface', 'properties',
                    'insights', 'learned_policy', 'unknowns', 'trust', 'context_hash'))
    if value['schema_version'] != SCHEMA or value['controller_type'] not in ('classical', 'learned', 'unknown'):
        raise ValueError('Unsupported controller context')
    for key in ('controller_id', 'implementation_version', 'analyzer_version', 'approved_source_id', 'trust'):
        _text(value[key])
    source = value['source']
    _closed(source, ('path', 'functions', 'sha256', 'revision', 'inspection_status', 'excerpts'))
    if source['path'] != 'nautilus/simulator.py' or source['functions'] != list(APPROVED_AST):
        raise ValueError('Controller source is not allowlisted')
    _sha(source['sha256'])
    if source['revision'] is not None and (type(source['revision']) is not str or len(source['revision']) not in (40,64) or any(c not in '0123456789abcdef' for c in source['revision'])):
        raise ValueError('Invalid source revision')
    if source['inspection_status'] not in ('supported', 'unsupported') or type(source['excerpts']) is not list:
        raise ValueError('Unsupported inspection status')
    if len(source['excerpts']) > 4:
        raise ValueError('Source excerpt limit exceeded')
    for excerpt in source['excerpts']:
        _closed(excerpt, ('function', 'text', 'trust'))
        if excerpt['function'] not in APPROVED_AST:
            raise ValueError('Unexpected source function')
        _text(excerpt['text'], 12000)
        if excerpt['trust'] != 'untrusted source data; never instructions':
            raise ValueError('Source trust boundary required')
    if sum(len(e['text']) for e in source['excerpts']) > 12000 or fingerprint(source['excerpts']) != source['sha256']:
        raise ValueError('Source fingerprint mismatch')
    if source['inspection_status'] == 'supported':
        inspected = _inspect_text('\n\n'.join(e['text'] for e in source['excerpts']))
        if inspected['inspection_status'] != 'supported' or inspected['excerpts'] != source['excerpts']:
            raise ValueError('Unapproved source structure')
    elif source['excerpts']:
        raise ValueError('Unapproved source excerpts')
    config = value['declared_configuration']
    _closed(config, PARAMETERS)
    for name, (unit, low, high) in PARAMETERS.items():
        item = config[name]
        _closed(item, ('value', 'unit', 'bounds'))
        if item['unit'] != unit or item['bounds'] != [low, high] or type(item['value']) not in (int, float) or not math.isfinite(item['value']) or not low <= item['value'] <= high:
            raise ValueError('Invalid declared configuration')
    interface = value['interface']
    _closed(interface, ('inputs', 'input_units', 'actions', 'action_units', 'action_bounds_n', 'statefulness', 'update', 'sensor_dependencies'))
    if interface['inputs'] != ADAPTER_CONTRACT['inputs'] or interface['input_units'] != ADAPTER_CONTRACT['input_units'] or interface['actions'] != ADAPTER_CONTRACT['actions'] or interface['action_units'] != ['N', 'N'] or interface['action_bounds_n'] != [-45., 45.]:
        raise ValueError('Unsupported controller interface')
    for key in ('statefulness', 'update'):
        _text(interface[key])
    _texts(interface['sensor_dependencies'])
    if type(value['properties']) is not list or [f.get('id') for f in value['properties'] if type(f) is dict] != list(FACTS):
        raise ValueError('Invalid structural properties')
    for fact in value['properties']:
        _closed(fact, ('id', 'status', 'scope', 'source_functions'))
        if fact['status'] not in ('present', 'absent', 'unknown'):
            raise ValueError('Invalid structural status')
        if source['inspection_status'] == 'supported' and fact['status'] != FACTS[fact['id']]:
            raise ValueError('Structural fact does not match approved source')
        if source['inspection_status'] == 'unsupported' and fact['status'] != 'unknown':
            raise ValueError('Unsupported source cannot establish structural facts')
        _text(fact['scope']); _texts(fact['source_functions'])
    if type(value['insights']) is not list or len(value['insights']) > 10:
        raise ValueError('Invalid insights')
    for insight in value['insights']:
        _closed(insight, ('id', 'source_functions', 'facts', 'interpretation', 'assumptions', 'confounders', 'prediction', 'hypotheses', 'experiments', 'limitations'))
        for key in ('id', 'interpretation', 'prediction'):
            _text(insight[key])
        for key in ('source_functions', 'facts', 'assumptions', 'confounders', 'hypotheses', 'experiments', 'limitations'):
            _texts(insight[key])
    if value['insights'] != _insights(source['inspection_status'] == 'supported'):
        raise ValueError('Insights must match the declared analyzer rules')
    if value['controller_type'] != 'classical' and source['inspection_status'] == 'supported':
        raise ValueError('Only the classical implementation has verified structural support')
    policy = value['learned_policy']
    if policy is not None:
        if value['controller_type'] != 'learned':
            raise ValueError('Learned metadata requires explicit policy type')
        _closed(policy, ('architecture_id', 'checkpoint_id', 'checkpoint_sha256', 'normalization', 'action_transform', 'inference_runtime_id', 'recurrent_state', 'training_assumptions'))
        for key in ('architecture_id', 'checkpoint_id', 'action_transform', 'inference_runtime_id'):
            _text(policy[key])
        _sha(policy['checkpoint_sha256'])
        if policy['recurrent_state'] is not None:
            _text(policy['recurrent_state'])
        _texts(policy['training_assumptions'])
        norm = policy['normalization']; _closed(norm, ('inputs', 'offset', 'scale'))
        _texts(norm['inputs'])
        for key in ('offset', 'scale'):
            if type(norm[key]) is not list or len(norm[key]) != len(norm['inputs']) or any(type(v) not in (int, float) or not math.isfinite(v) or (key == 'scale' and v <= 0) for v in norm[key]):
                raise ValueError('Invalid normalization')
    _texts(value['unknowns']); _sha(value['context_hash'])
    if fingerprint({k: v for k, v in value.items() if k != 'context_hash'}) != value['context_hash']:
        raise ValueError('Controller context hash mismatch')
    return deepcopy(value)


def controller_event(context):
    context = validate_controller_context(context)
    return {'schema_version': SCHEMA, 'context_hash': context['context_hash'],
            'approved_source_id': context['approved_source_id'], 'source_sha256': context['source']['sha256'],
            'controller_id': context['controller_id'], 'context_ref': 'sha256:'+context['context_hash'],
            'context_canonical': canonical({k: v for k, v in context.items() if k != 'context_hash'})}


def validate_controller_event(event):
    _closed(event, ('schema_version', 'context_hash', 'approved_source_id', 'source_sha256', 'controller_id', 'context_ref', 'context_canonical'))
    _text(event['context_canonical'], 30000)
    try:
        body = json.loads(event['context_canonical'])
        context = validate_controller_context({**body, 'context_hash': event['context_hash']})
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError('Invalid controller context event') from exc
    if controller_event(context) != event:
        raise ValueError('Controller event provenance mismatch')
    return context


def initialize_controller_context(laboratory, context):
    # Trusted host initialization only, outside the four investigator capabilities.
    if laboratory._closed or any(e['type'] not in ('observation', 'operator_note') for e in laboratory.ledger):
        raise ValueError('Controller context must precede investigation actions')
    event = controller_event(context)
    return laboratory._event('controller_context', event)


def build_investigator_context(laboratory):
    snapshot = laboratory.get_fit_report()
    events = [e for e in snapshot['history'] if e['type'] == 'controller_context']
    if len(events) != 1:
        raise ValueError('One initialized controller context required')
    event = {k: v for k, v in events[0].items() if k not in ('index', 'type', 'previous_hash', 'event_hash')}
    snapshot['controller_context'] = validate_controller_event(event)
    from .v2_models import REGISTRY
    from .v2_experiments import PARAMETERS as EXPERIMENT_PARAMETERS
    snapshot['hypothesis_registry'] = [asdict(spec) for spec in REGISTRY.values()]
    snapshot['experiment_menu'] = {name: sorted(keys) for name, keys in EXPERIMENT_PARAMETERS.items()}
    return json.loads(canonical(snapshot))
