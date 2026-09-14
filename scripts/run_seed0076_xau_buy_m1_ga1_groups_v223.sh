#!/usr/bin/env bash
set -euo pipefail
ROOT=/mnt/data/qros_v222_ga1_groups
WORKER=/mnt/data/qros_v220/qros_seed0076_ga1_shard_worker_v222.py
SHARD=/mnt/data/qros_v220/XAUUSD_BUY_M1_SHARD.json
SPEC=/mnt/data/qros_v215/spec.json
TICKS=/mnt/data/qros_seed0076_dev/XAU_PACKED17_CENT_DEV_2018_2019.bin
BARS=/mnt/data/qros_seed0076_bars/XAUUSD
INDS=/mnt/data/qros_seed0076_indicators/XAUUSD
ROOTCFG=96d664f4c4efb431dbd475355249b51aa49c8ac656ad5fd1caaf46d7086fc1c3
mkdir -p "$ROOT"
for i in $(seq 0 23); do
  d="$ROOT/group$(printf '%02d' "$i")"
  r="$d/worker_receipt.json"
  if [[ -f "$r" ]] && python - "$r" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); raise SystemExit(0 if r.get('status')=='PASS' and r.get('processed_signal_configs')==33528 else 1)
PY
  then
    echo "SKIP_VALID group$(printf '%02d' "$i")" >> "$ROOT/progress.log"
    continue
  fi
  rm -rf "$d"; mkdir -p "$d"
  echo "START group$(printf '%02d' "$i") $(date -u +%FT%TZ)" >> "$ROOT/progress.log"
  python "$WORKER" --shard-json "$SHARD" --spec "$SPEC" --out-dir "$d" --receipt "$r" --ticks "$TICKS" --bar-root "$BARS" --ind-root "$INDS" --point 0.01 --expected-config-root "$ROOTCFG" --only-group-index "$i" >"$d/stdout.txt" 2>"$d/stderr.txt"
  python - "$r" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); assert r['status']=='PASS' and r['processed_signal_configs']==33528
PY
  echo "DONE group$(printf '%02d' "$i") $(date -u +%FT%TZ)" >> "$ROOT/progress.log"
done
echo "ALL_GROUPS_DONE $(date -u +%FT%TZ)" >> "$ROOT/progress.log"
