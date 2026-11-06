#!/bin/sh
# Writes one sample per voice and language into <out-dir>/wav/<engine>-<voice>-<lang>.wav, then
# page.py builds the scoring sheet <out-dir>/index.html. The samples feed the first round of a vote.
#   make.sh <out-dir>
set -u
here=$(cd "$(dirname "$0")" && pwd); s="$here/../../scripts"
out=${1:?usage: make.sh <out-dir>}
mlx=${MLX_TTS_PY:-$HOME/.local/share/demo-tts/mlx/bin/python}
kok=${KOKORO_PY:-$HOME/.local/share/kokoro-tts/.venv/bin/python}
mkdir -p "$out/wav" "$out/tmp"
one() { # engine voice lang
  t="$out/tmp/$1-$2-$3"; mkdir -p "$t"
  if [ "$1" = kokoro ]; then "$kok" "$s/kokoro_lines.py" "$here/en.json" "$t" "$2" 1.0 > "$t/log" 2> "$t/err"
  elif [ "$2" = ref ]; then "$mlx" "$s/tts_lines.py" "$here/$3.json" "$t" --engine "$1" --lang "$3" > "$t/log" 2> "$t/err"
  else "$mlx" "$s/tts_lines.py" "$here/$3.json" "$t" --engine "$1" --lang "$3" --voice "$2" > "$t/log" 2> "$t/err"; fi
  if [ -f "$t/sample.wav" ]; then cp "$t/sample.wav" "$out/wav/$1-$2-$3.wav"; echo "OK $1 $2 $3 $(cat "$t/log")"
  else echo "FAIL $1 $2 $3 $(grep -i error "$t/err" | tail -1)"; fi
}
for v in af_alloy af_aoede af_bella af_heart af_jessica af_kore af_nicole af_nova af_river af_sarah af_sky am_adam am_echo am_eric am_fenrir am_liam am_michael am_onyx am_puck am_santa bf_alice bf_emma bf_isabella bf_lily bm_daniel bm_fable bm_george bm_lewis; do one kokoro $v en; done
for l in en ru; do for v in serena vivian uncle_fu ryan aiden ono_anna sohee eric dylan; do one qwen3 $v $l; done; done
for e in fish-s2 higgs3 drama3 voxcpm2 chatterbox omnivoice; do for l in en ru; do one $e ref $l; done; done
python3 "$here/page.py" "$out"
