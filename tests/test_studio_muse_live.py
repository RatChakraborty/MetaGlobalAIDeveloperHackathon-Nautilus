import os
import unittest
from unittest import mock

from nautilus import studio_muse
from nautilus.studio_muse import Budget, run_session
from nautilus.studio_muse_live import LiveDisabled, LiveEnvelope, LiveMuse, MAX_REQUESTS
from nautilus.studio_muse_live import MAX_USD


PRICED = dict(usd_per_mtok_in=1.0, usd_per_mtok_out=2.0)


def scripted(replies):
    """Transport that returns the scripted replies in order; it counts real calls made."""
    calls = []

    def transport(**kwargs):
        calls.append(kwargs)
        return replies[len(calls) - 1]
    transport.calls = calls
    return transport


class KillSwitchTests(unittest.TestCase):
    def test_default_is_off_and_blocks_before_any_transport_call(self):
        transport = scripted([{'tool_call': {'name': 'inspect_controller', 'arguments': {}}}])
        with mock.patch.dict(os.environ, {}, clear=True):
            provider = LiveMuse(transport, LiveEnvelope(**PRICED))
            with self.assertRaises(LiveDisabled):
                provider.next_call(None, [])
        self.assertEqual(transport.calls, [])

    def test_only_exact_true_enables(self):
        for value in ('1', 'yes', 'on', ''):
            with self.subTest(value=value), mock.patch.dict(os.environ, {'NAUTILUS_MUSE_ENABLED': value}):
                self.assertFalse(studio_muse.muse_enabled())
        with mock.patch.dict(os.environ, {'NAUTILUS_MUSE_ENABLED': 'true'}):
            self.assertTrue(studio_muse.muse_enabled())

    def test_live_available_stays_false_even_when_enabled(self):
        with mock.patch.dict(os.environ, {'NAUTILUS_MUSE_ENABLED': 'true'}):
            self.assertFalse(studio_muse.live_available())

    def test_missing_price_blocks_every_request(self):
        transport = scripted([{'tool_call': {'name': 'inspect_controller', 'arguments': {}}}])
        unpriced = LiveEnvelope(usd_per_mtok_in=0.0, usd_per_mtok_out=0.0)
        with mock.patch.dict(os.environ, {'NAUTILUS_MUSE_ENABLED': 'true'}):
            with self.assertRaises(LiveDisabled):
                LiveMuse(transport, unpriced).next_call(None, [])
        self.assertEqual(transport.calls, [])

    def test_transport_is_required(self):
        with self.assertRaises(TypeError):
            LiveMuse(None)


class EnvelopeTests(unittest.TestCase):
    def test_request_ceiling_trips_before_the_request_that_exceeds_it(self):
        env = LiveEnvelope(**PRICED, requests=MAX_REQUESTS)
        with mock.patch.dict(os.environ, {'NAUTILUS_MUSE_ENABLED': 'true'}):
            with self.assertRaises(studio_muse.ToolError):
                env.reserve(10, 10)

    def test_spend_ceiling_trips_before_the_request(self):
        env = LiveEnvelope(usd_per_mtok_in=1e6, usd_per_mtok_out=1.0)
        with mock.patch.dict(os.environ, {'NAUTILUS_MUSE_ENABLED': 'true'}):
            with self.assertRaises(studio_muse.ToolError):
                env.reserve(1, 1)
        self.assertLessEqual(MAX_USD, 0.25)

    def test_spend_is_recorded_from_usage(self):
        env = LiveEnvelope(**PRICED)
        env.record(1_000_000, 500_000)
        self.assertAlmostEqual(env.usd, 1.0 + 1.0)


class LoopTests(unittest.TestCase):
    def test_scripted_muse_drives_the_trusted_loop_to_a_decision(self):
        replies = [
            {'tool_call': {'name': 'inspect_controller', 'arguments': {}}, 'usage': {'input_tokens': 100, 'output_tokens': 20}},
            {'tool_call': {'name': 'inspect_diagnosis_evidence', 'arguments': {}}, 'usage': {'input_tokens': 100, 'output_tokens': 20}},
            {'tool_call': {'name': 'finalize_controller_recommendation', 'arguments': {
                'decision': 'abstain', 'rationale': 'Scripted test: evidence is not used to recommend.'}},
             'usage': {'input_tokens': 100, 'output_tokens': 20}},
        ]
        transport = scripted(replies)
        with mock.patch.dict(os.environ, {'NAUTILUS_MUSE_ENABLED': 'true'}):
            provider = LiveMuse(transport, LiveEnvelope(**PRICED))
            result = run_session(provider=provider, budget=Budget())
        self.assertEqual(result['final']['decision'], 'abstain')
        self.assertEqual(len(transport.calls), 3)
        self.assertTrue(all('tools' in call and call['tools'] for call in transport.calls))

    def test_unsupported_tool_from_model_is_refused_not_executed(self):
        transport = scripted([{'tool_call': {'name': 'run_python', 'arguments': {'code': 'import os'}}}] * 3)
        with mock.patch.dict(os.environ, {'NAUTILUS_MUSE_ENABLED': 'true'}):
            provider = LiveMuse(transport, LiveEnvelope(**PRICED))
            result = run_session(provider=provider, budget=Budget())
        self.assertIsNone(result['final'])
        self.assertEqual(result['stopped'], 'too many invalid tool calls')
        self.assertEqual(len(transport.calls), 3)


class BindingTests(unittest.TestCase):
    def test_recommendation_refused_when_controller_changed_after_robustness(self):
        from nautilus.policy_ir import baseline_policy
        from nautilus.studio import policy_fingerprint
        from nautilus.studio_muse import Session, ToolError
        s = Session()
        s.inspect_diagnosis_evidence()
        s.propose_controller_revision('c1', 'bind test', params={'integral_ki': 1.0})
        policy = s.candidates['c1']['policy']
        s.results['c1'] = {'outcome': {'label': 'Recommended'}}
        s.robustness['c1'] = {'outcome': {'label': 'Recommended'}, 'part': 'held_out',
                              'fingerprint': policy_fingerprint(policy), 'protocol': 'held_out:held_out'}
        policy['params']['integral_ki'] = 2.0  # controller changed after approval
        with self.assertRaises(ToolError):
            s.finalize_controller_recommendation('recommend', 'changed after approval', 'c1')
        self.assertIsNotNone(baseline_policy())

    def test_invalid_proposal_is_returned_to_model_and_loop_recovers(self):
        class Scripted:
            name = 'scripted'
            def __init__(self):
                self.steps = [
                    {'tool': 'propose_controller_revision', 'arguments': {
                        'candidate_id': 'bad', 'rationale': 'out of range', 'params': {'integral_ki': 1e9}}},
                    {'tool': 'finalize_controller_recommendation', 'arguments': {
                        'decision': 'abstain', 'rationale': 'recovered after a structured error'}},
                ]
            def next_call(self, session, observations):
                return self.steps.pop(0)
        run = run_session(provider=Scripted(), budget=Budget())
        self.assertEqual(run['final']['decision'], 'abstain')
        errors = [step for step in run['transcript'] if 'error' in step]
        self.assertEqual(len(errors), 1)
        self.assertEqual(run['candidates'], {})
        self.assertEqual(errors[0]['tool'], 'propose_controller_revision')


class EvidenceTests(unittest.TestCase):
    def test_revision_requires_inspected_evidence_and_evidence_has_stable_id(self):
        from nautilus.studio_muse import Session, ToolError
        s = Session()
        with self.assertRaises(ToolError):
            s.propose_controller_revision('early', 'no evidence yet', params={'integral_ki': 1.0})
        ev = s.inspect_diagnosis_evidence()
        self.assertEqual(ev['evidence_id'], 'E1')
        self.assertFalse(ev['hidden_truth_exposed'])
        s.propose_controller_revision('ok', 'cites E1', params={'integral_ki': 1.0})

    def test_hypothesis_must_cite_known_evidence_and_is_logged_append_only(self):
        from nautilus.studio_muse import Session, ToolError
        s = Session()
        s.inspect_diagnosis_evidence()
        with self.assertRaises(ToolError):
            s.propose_controller_revision('bad', 'cites unknown', params={'integral_ki': 1.0},
                                          evidence_refs=['E9'])
        self.assertNotIn('bad', s.hypotheses)
        s.propose_controller_revision('good', 'bias needs integral', params={'integral_ki': 1.0},
                                      evidence_refs=['E1'])
        self.assertEqual(s.hypotheses['good']['evidence_refs'], ['E1'])
        self.assertEqual([e['seq'] for e in s.action_log], [1])
        self.assertEqual(s.action_log[0]['action'], 'propose')


class StrictSchemaTests(unittest.TestCase):
    def test_every_strict_property_is_required_and_optional_nulls_are_dropped(self):
        from nautilus.studio_muse import TOOLS
        from nautilus.studio_muse_live import _strict_schema, _drop_nulls
        for tool in TOOLS:
            schema = _strict_schema(tool['parameters'])
            self.assertEqual(set(schema.get('required', [])), set(schema.get('properties', {})), tool['name'])
        self.assertEqual(_drop_nulls({'candidate_id': 'c', 'params': None, 'source': None}),
                         {'candidate_id': 'c'})

    def test_empty_params_placeholder_beside_source_is_dropped_but_real_params_are_kept(self):
        from nautilus.studio_muse_live import _drop_nulls
        self.assertEqual(_drop_nulls({'candidate_id': 'c', 'params': {}, 'source': 'x'}),
                         {'candidate_id': 'c', 'source': 'x'})
        # Real params beside a source are still forwarded, so the trusted validator refuses them.
        self.assertEqual(_drop_nulls({'candidate_id': 'c', 'params': {'heading_kp': 1.0}, 'source': 'x'}),
                         {'candidate_id': 'c', 'params': {'heading_kp': 1.0}, 'source': 'x'})


class MalformedReplyTests(unittest.TestCase):
    def test_malformed_reply_is_recorded_and_loop_continues_until_limit(self):
        from nautilus.studio_muse import Session, ToolError, run_session, MAX_INVALID_CALLS

        class Broken:
            name = 'broken'
            def next_call(self, session, observations):
                raise ToolError('model returned no supported tool call')

        run = run_session(provider=Broken(), session=Session())
        self.assertEqual(run['stopped'], 'too many invalid tool calls')
        errors = [entry for entry in run['transcript'] if 'error' in entry]
        self.assertEqual(len(errors), MAX_INVALID_CALLS)


class MemoryTests(unittest.TestCase):
    def test_memory_ids_are_stable_and_bounded(self):
        from nautilus.studio_muse import Session
        s = Session()
        ids = [s.remember('note', f'entry {i}') for i in range(Session.MEMORY_LIMIT + 4)]
        self.assertEqual(ids[0], 'M1')
        self.assertEqual(len(s.memory), Session.MEMORY_LIMIT)
        self.assertEqual(s.memory[-1]['id'], ids[-1])
        self.assertNotIn('M1', [entry['id'] for entry in s.memory])


if __name__ == '__main__':
    unittest.main()
