#!/bin/sh
# Measures each engine's peak memory with Whisper, the figure ENGINES in scripts/demo-kit.mjs keeps.
#   memory.sh <out-dir> [engine ...]
# Run it with nothing else heavy open. Two takes load Whisper into the same process as the engine.
set -u
here=$(cd "$(dirname "$0")" && pwd); s="$here/../../scripts"
out=${1:?usage: memory.sh <out-dir> [engine ...]}; shift
engines=${*:-"qwen3 voxcpm2 chatterbox omnivoice fish-s2 drama3 higgs3"}
mlx=${MLX_TTS_PY:-$HOME/.local/share/demo-tts/mlx/bin/python}
mkdir -p "$out"
printf '{"m1": "Three hundred requests reached the server, and every one of them came back within a second."}' > "$out/en.json"
for e in $engines; do
  mkdir -p "$out/$e"
  "$mlx" "$s/tts_lines.py" "$out/en.json" "$out/$e" --engine "$e" --lang en --takes 2 --report-peak > /dev/null 2> "$out/$e/err"
  echo "$e $(grep peak_gb "$out/$e/err")"
done
