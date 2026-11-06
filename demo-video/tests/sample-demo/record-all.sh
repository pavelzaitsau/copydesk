#!/bin/sh
# Records the sample demo once per engine and language and mixes each to an MP4, to check the
# engines after an upgrade of mlx-audio. Every take's Whisper check is in <out>/<engine>-<lang>/voice/takes.json.
#   record-all.sh <out-dir> [engine:lang ...]
# The default list is every engine in both languages it speaks. The runs use purpose=personal, so a
# non-commercial engine records too; memory still decides which engines run on this machine.
set -u
here=$(cd "$(dirname "$0")" && pwd)
out=${1:?usage: record-all.sh <out-dir> [engine:lang ...]}; shift
mkdir -p "$out"; out=$(cd "$out" && pwd)
pairs=${*:-"kokoro:en qwen3:en qwen3:ru voxcpm2:en voxcpm2:ru chatterbox:en chatterbox:ru omnivoice:en omnivoice:ru fish-s2:en fish-s2:ru drama3:en drama3:ru higgs3:en higgs3:ru"}
cd "$here"
for pair in $pairs; do
  e=${pair%%:*}; l=${pair##*:}; o="$out/$e-$l"; rm -rf "$o"; mkdir -p "$o"
  s=$(date +%s)
  if DEMO_LANG=$l TTS_ENGINE=$e VOICE=default PURPOSE=personal node scenario.mjs "$o" > "$o/scenario.log" 2> "$o/scenario.err" \
     && python3 ../../scripts/mix.py "$o" "$out/$e-$l.mp4" > "$o/mix.log" 2>&1; then
    echo "OK $e $l $(( $(date +%s) - s ))s $(head -2 "$o/mix.log" | tr '\n' ' ')"
  else
    echo "FAIL $e $l: $(grep -iE 'error' "$o/scenario.err" "$o/mix.log" | tail -2 | cut -c1-300)"
  fi
done
