from typing import Protocol
import random
from .v2_models import REGISTRY
from .v2_experiments import LIBRARY
from .v2_tools import predicted_separation
from types import SimpleNamespace


class Investigator(Protocol):
    def choose(self, state: dict) -> dict: ...


def investigate(laboratory, investigator, *, max_actions=64):
    if type(max_actions) is not int or not 1 <= max_actions <= 128:
        raise ValueError('Bounded action count required')
    for _ in range(max_actions):
        state = laboratory.get_fit_report()
        action = investigator.choose(state)
        try:
            result = laboratory.call(action)
        except ValueError:
            continue
        if laboratory._closed: return result
    return laboratory.finalize({'hypothesis': None, 'evidence_refs': laboratory.evidence_refs()},
                               'abstain', 'Investigator action limit reached')


class DeterministicInvestigator:
    def __init__(self, strategy='fixed', seed=0):
        if strategy not in ('passive', 'exhaustive', 'fixed', 'random', 'greedy'):
            raise ValueError('Unknown strategy')
        self.strategy = strategy
        self.rng = random.Random(seed)
        self.attempted = set()
        self.fit_attempts = set()

    def choose(self, state):
        refs = tuple(state['evidence_refs'])
        for name in REGISTRY:
            key = (refs, name)
            if key not in self.fit_attempts and state['remaining']['fit_calls']:
                self.fit_attempts.add(key)
                return {'op': 'propose_hypothesis', 'template': name, 'knobs': {}, 'bounds': {}, 'rationale': 'Deterministic exhaustive comparison'}
        options = [t for t in LIBRARY if t.key not in self.attempted and t.duration_s+state['safety_constraints']['tail_reserve_s'] <= state['remaining']['time_s']]
        if self.strategy not in ('passive', 'exhaustive') and options and state['remaining']['experiments']:
            if self.strategy == 'random': trial = self.rng.choice(options)
            elif self.strategy == 'greedy' and state['method'] == 'singleton':
                fits = [SimpleNamespace(**f) for f in state['fits'] if f['converged']]
                trial = max(options, key=lambda t: predicted_separation(fits, t))
            else: trial = options[0]
            self.attempted.add(trial.key)
            return {'op': 'request_experiment', 'name': trial.name, 'params': trial.params()}
        summary = state['numerical_summary']
        selected = summary.get('selected')
        return {'op': 'finalize', 'diagnosis': {'hypothesis': selected, 'evidence_refs': list(refs)},
                'confidence': 'supported' if selected else 'abstain',
                'ambiguity_statement': 'Policy completed; numerical ranking is conditional, and rejected tests supplied no new evidence.'}
