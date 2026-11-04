"""Run one bounded live Muse controller-engineering session and record it locally.

Requires NAUTILUS_MUSE_ENABLED=true and MODEL_API_KEY in the environment. The key is read only
inside MetaProvider.generate and is never written to the artifact. Refuses to run otherwise.
"""
import json
import sys
from pathlib import Path

from nautilus.muse import MetaProvider
from nautilus.studio_muse import Budget, live_available, run_session
from nautilus.studio_muse_live import LiveMuse, meta_transport

OUT = Path('artifacts/muse-studio-live-run.json')


def main() -> int:
    if not live_available():
        print('refused: NAUTILUS_MUSE_ENABLED must be true and MODEL_API_KEY must be set')
        return 2
    provider = LiveMuse(meta_transport(MetaProvider()))
    run = run_session(provider=provider, budget=Budget())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({'final': run['final'], 'stopped': run['stopped'], 'transcript': run['transcript'],
                               'usage': {'input_tokens': provider.envelope.input_tokens,
                                         'output_tokens': provider.envelope.output_tokens,
                                         'requests': provider.envelope.requests,
                                         'usd_estimate': round(provider.envelope.usd, 6)}},
                              indent=2, default=str, sort_keys=True))
    print(f"wrote {OUT}; final={run['final'] and run['final']['decision']}; stopped={run['stopped']}; "
          f"usd_estimate={provider.envelope.usd:.6f}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
