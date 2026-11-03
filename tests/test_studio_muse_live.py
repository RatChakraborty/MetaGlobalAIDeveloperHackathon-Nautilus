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
        with mock.patch.dict(os.environ, {'NAUTILUS_MUSE_ENABLED': 'true'}):
            with self.assertRaises(LiveDisabled):
                LiveMuse(transport, LiveEnvelope()).next_call(None, [])
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
        transport = scripted([{'tool_call': {'name': 'run_python', 'arguments': {'code': 'import os'}}}])
        with mock.patch.dict(os.environ, {'NAUTILUS_MUSE_ENABLED': 'true'}):
            provider = LiveMuse(transport, LiveEnvelope(**PRICED))
            result = run_session(provider=provider, budget=Budget())
        self.assertIsNone(result['final'])
        self.assertIn('no supported tool call', result['stopped'] or '')


if __name__ == '__main__':
    unittest.main()
