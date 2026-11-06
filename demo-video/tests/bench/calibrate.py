#!/usr/bin/env python3
"""Calibrates the take check without listening: the WER threshold and SLOW_CPS.

    calibrate.py <out-dir> [--engines qwen3,voxcpm2] [--takes 3]

Synthesises the 20 lines per language in lines.json beside this file, each as written and each
distorted (every fifth word replaced by another word of the same language, never a number or a
Latin word), with --takes takes per line on each engine. Whisper scores every take against the line
as written. Prints, per language:

- the 95th percentile WER of the takes of written lines, the threshold candidate;
- how many distorted takes that threshold catches; below 9 in 10 the threshold stays at 12%;
- the median characters per second of each engine, and its SLOW_CPS: that median divided by 1.5,
  so a take 1.5 times longer than the engine's usual counts as drawled.

Runs tts_lines.py in the MLX environment (MLX_TTS_PY overrides it). Takes about half an hour.
Copy the printed values into tts_lines.py with the date.
"""
import argparse
import json
import os
import pathlib
import random
import statistics
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
from wer import NUMBER_WORDS, line_wer  # noqa: E402

PY = os.environ.get("MLX_TTS_PY", str(pathlib.Path.home() / ".local/share/demo-tts/mlx/bin/python"))


def distort(line, pool, lang, rng):
    words = line.split()
    for i in range(4, len(words), 5):
        core = words[i].strip(".,!?")
        choices = [w for w in pool if w != core.lower() and w not in NUMBER_WORDS[lang]]
        words[i] = words[i].replace(core, rng.choice(choices))
    return " ".join(words)


def run(lines, out, engine, lang, takes):
    out.mkdir(parents=True, exist_ok=True)
    (out / "lines.json").write_text(json.dumps(lines, ensure_ascii=False), encoding="utf-8")
    subprocess.run([PY, str(SCRIPTS / "tts_lines.py"), str(out / "lines.json"), str(out),
                    "--engine", engine, "--lang", lang, "--takes", str(takes)],
                   check=True, stdout=subprocess.DEVNULL)
    return json.loads((out / "takes.json").read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--engines", default="qwen3,voxcpm2")
    ap.add_argument("--takes", type=int, default=3)
    a = ap.parse_args()
    data = json.loads((HERE / "lines.json").read_text(encoding="utf-8"))
    rng = random.Random(7)
    for lang, texts in data.items():
        pool = sorted({w.strip(".,!?").lower() for t in texts for w in t.split()
                       if w.strip(".,!?").isalpha() and (lang != "ru" or not w.isascii())})
        good, bad, cps = [], [], {}
        for engine in a.engines.split(","):
            written = {f"g{i:02d}": t for i, t in enumerate(texts)}
            twisted = {f"d{i:02d}": distort(t, pool, lang, rng) for i, t in enumerate(texts)}
            base = pathlib.Path(a.out) / lang / engine
            g = run(written, base / "good", engine, lang, a.takes)
            d = run(twisted, base / "bad", engine, lang, a.takes)
            rates = []
            for key, rec in g.items():
                for t in rec["takes"]:
                    good.append(line_wer([written[key]], t["heard"], lang))
                    rates.append(len(written[key]) / max(t["sec"], 0.1))
            for key, rec in d.items():
                orig = texts[int(key[1:])]
                for t in rec["takes"]:
                    bad.append(line_wer([orig], t["heard"], lang))
            cps[engine] = statistics.median(rates)
        good.sort()
        threshold = good[min(len(good) - 1, int(0.95 * len(good)))]
        caught = sum(1 for w in bad if w > threshold) / len(bad)
        print(json.dumps({"lang": lang, "p95_good": round(threshold, 3), "caught": round(caught, 3),
                          "threshold": round(threshold, 3) if caught >= 0.9 else 0.12,
                          "median_cps": {e: round(v, 1) for e, v in cps.items()},
                          "slow_cps": {e: round(v / 1.5, 1) for e, v in cps.items()},
                          "good_takes": len(good), "bad_takes": len(bad)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
