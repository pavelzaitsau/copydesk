#!/bin/sh
# Records the sample demo in both languages on the fake engine and mixes each to an MP4: the whole
# kit without a voice model. Needs node, ffmpeg and `npm install` in demo-video/ once.
#   e2e.sh [out-dir]
set -eu
here=$(cd "$(dirname "$0")" && pwd)
out=${1:-$(mktemp -d)}; mkdir -p "$out"; out=$(cd "$out" && pwd)
for lang in en ru; do
  o="$out/fake-$lang"; rm -rf "$o"
  (cd "$here/sample-demo" && DEMO_LANG=$lang TTS_ENGINE=fake VOICE=default node scenario.mjs "$o" > "$o.log" 2>&1)
  python3 "$here/../scripts/mix.py" "$o" "$o.mp4" > "$o.mix" 2>&1
  python3 - "$o" <<'PY'
import json, sys
run = json.load(open(f"{sys.argv[1]}/run.json"))
assert run["engine"] == "fake" and run["purpose"] == "client" and run["failedLines"] == [], run
assert len(run["clips"]) == 6, run["clips"]
PY
  echo "ok $lang: $o.mp4"
done
