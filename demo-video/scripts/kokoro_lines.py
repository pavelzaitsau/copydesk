"""Synthesises voice-over lines with Kokoro-82M in one process.

    kokoro_lines.py lines.json out-dir voice speed

lines.json maps a key to the text of one line. Writes out-dir/<key>.wav (24 kHz mono) and prints
"<key> <seconds>" per line. The voice's first letter selects the language (a: American English,
b: British English). Runs in the kokoro-tts virtual environment, see the skill's SKILL.md.
"""
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")

import espeakng_loader

# The espeakng_loader wheel points at its build machine's paths; use Homebrew's espeak-ng instead.
ESPEAK = os.environ.get("ESPEAK_PREFIX", "/opt/homebrew/opt/espeak-ng")
espeakng_loader.get_library_path = lambda: f"{ESPEAK}/lib/libespeak-ng.dylib"
espeakng_loader.get_data_path = lambda: f"{ESPEAK}/share/espeak-ng-data"

import numpy as np
import soundfile as sf
from kokoro import KPipeline

lines_path, out, voice, speed = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
with open(lines_path, encoding="utf-8") as f:
    lines = json.load(f)
pipe = KPipeline(lang_code=voice[0], repo_id="hexgrad/Kokoro-82M")
for key, text in lines.items():
    chunks = [chunk.numpy() for _, _, chunk in pipe(text, voice=voice, speed=speed)]
    # Kokoro yields nothing for an empty or unpronounceable line.
    if not chunks:
        sys.exit(f"line {key}: Kokoro produced no audio for {text!r}")
    audio = np.concatenate(chunks)
    sf.write(f"{out}/{key}.wav", audio, 24000)
    print(key, round(len(audio) / 24000, 2), flush=True)
