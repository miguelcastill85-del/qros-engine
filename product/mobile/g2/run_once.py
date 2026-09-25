"""CLI for deterministic TEST_ONLY G2 shard execution and process crash canaries."""
import argparse
import json
from pathlib import Path
import sys
from shard_engine import run_shards, IntegrityError


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--fixture', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--chunk', type=int, default=37)
    p.add_argument('--max-new', type=int)
    opts = p.parse_args()
    try:
        raw = json.loads(opts.fixture.read_text(encoding='utf-8'))['raw_input']
        print(json.dumps(run_shards(opts.work,raw,opts.chunk,opts.max_new),sort_keys=True))
        return 0
    except (IntegrityError, ValueError, OSError) as exc:
        print('G2_FAIL_CLOSED:'+str(exc),file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
