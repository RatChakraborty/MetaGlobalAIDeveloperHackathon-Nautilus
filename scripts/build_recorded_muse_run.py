"""Build the public, sanitized replay of the recorded real Muse engineering run.

Input is the operator artifact produced by `scripts/run_muse_studio_live.py`. Output is a
public-safe JSON the frontend loads without any API key. Only the tool sequence, arguments,
trusted results and usage counters are copied. Nothing else from the artifact is published.

Usage: python scripts/build_recorded_muse_run.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'artifacts' / 'muse-studio-live-run.recommend.json'
OUTPUT = ROOT / 'frontend' / 'public' / 'recorded' / 'muse-engineering-run.json'

ALLOWED_USAGE = ('input_tokens', 'output_tokens', 'requests', 'usd_estimate')


def build(raw: bytes) -> dict:
    data = json.loads(raw)
    final = data.get('final') or {}
    if final.get('decision') != 'recommend':
        raise ValueError('the recorded run does not end in a recommendation')
    events = []
    for index, entry in enumerate(data['transcript'], start=1):
        events.append({
            'index': index,
            'tool': entry['tool'],
            'arguments': entry.get('arguments', {}),
            'result': entry.get('result'),
        })
    usage = {key: data['usage'][key] for key in ALLOWED_USAGE if key in data['usage']}
    return {
        'label': 'Recorded Real Muse',
        'disclosure': ('This is a recorded run of the Meta Muse provider. It is not a live model call. '
                       'Muse proposed a parameter revision; the trusted host compiled, simulated and '
                       'decided. Candidate C1 is a tested hypothesis, not a proven cause.'),
        'origin': {
            'source_sha256': hashlib.sha256(raw).hexdigest(),
            'source_file': 'artifacts/muse-studio-live-run.recommend.json',
            'candidate_origin': 'muse-proposed-parameter',
            'structural_source': False,
        },
        'final': final,
        'usage': usage,
        'events': events,
    }


def main() -> int:
    raw = SOURCE.read_bytes()
    record = build(raw)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(f'wrote {OUTPUT.relative_to(ROOT)} with {len(record["events"])} events')
    return 0


if __name__ == '__main__':
    sys.exit(main())
