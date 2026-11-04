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
SOURCE_OUT = Path('artifacts/muse-studio-live-source-run.json')


def main() -> int:
    # 'parameters' (default) keeps the original run. 'source' asks Muse to write its revision as source text.
    mode = sys.argv[1] if len(sys.argv) > 1 else 'parameters'
    if mode not in ('parameters', 'source'):
        print('usage: run_muse_studio_live.py [parameters|source]')
        return 2
    if not live_available():
        print('refused: NAUTILUS_MUSE_ENABLED must be true and MODEL_API_KEY must be set')
        return 2
    provider = LiveMuse(meta_transport(MetaProvider()), source_mode=mode == 'source')
    out = SOURCE_OUT if mode == 'source' else OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        run = run_session(provider=provider, budget=Budget())
    except Exception as exc:
        # A paid call that fails is still recorded, so the spend is never silently lost.
        out.write_text(json.dumps({'final': None, 'stopped': f'provider_error: {type(exc).__name__}: {exc}',
                                   'transcript': [],
                                   'usage': {'input_tokens': provider.envelope.input_tokens,
                                             'output_tokens': provider.envelope.output_tokens,
                                             'requests': provider.envelope.requests,
                                             'usd_estimate': round(provider.envelope.usd, 6)}},
                                  indent=2, sort_keys=True))
        print(f"wrote {out}; provider error: {type(exc).__name__}; usd_estimate={provider.envelope.usd:.6f}")
        return 1
    out.write_text(json.dumps({'final': run['final'], 'stopped': run['stopped'], 'transcript': run['transcript'],
                               'usage': {'input_tokens': provider.envelope.input_tokens,
                                         'output_tokens': provider.envelope.output_tokens,
                                         'requests': provider.envelope.requests,
                                         'usd_estimate': round(provider.envelope.usd, 6)}},
                              indent=2, default=str, sort_keys=True))
    print(f"wrote {out}; final={run['final'] and run['final']['decision']}; stopped={run['stopped']}; "
          f"usd_estimate={provider.envelope.usd:.6f}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
