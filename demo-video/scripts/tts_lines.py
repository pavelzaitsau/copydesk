"""Synthesises voice-over lines with an MLX text-to-speech engine in one process.

    tts_lines.py lines.json out-dir --engine NAME --lang en|ru [--voice VOICE] [--speed 1.0] [--takes 1]
    tts_lines.py lines.json out-dir --check-existing --lang en|ru

lines.json maps a key to the text of one line, or to {"say": what the voice reads, "text": what
the viewer reads}. Writes out-dir/<key>.wav and prints "<key> <seconds>" per line, the same
contract as kokoro_lines.py. --check-existing synthesises nothing: it checks the WAV files another
engine (Kokoro) left in out-dir. Runs in the mlx-audio virtual
environment on Apple Silicon, see the skill's SKILL.md.

An engine either has preset voices (qwen3) or clones a reference clip (the rest). A cloning engine
takes --voice as a path to a WAV file with its transcript in a .txt file of the same name. Without
--voice it clones the default reference: qwen3's preset voice speaking REF_TEXT in the target
language, synthesised once and cached. Every engine then speaks with the same voice, so a
comparison between engines compares the engine, not the speaker.

Whisper checks every take, also with --takes 1; references/engines.md, "Takes", says how the
best take is chosen. out-dir/takes.json holds every take's WER, its speed and what Whisper heard,
and marks a line with no passing take as failed for the caller to handle.
"""
import argparse
import json
import os
import pathlib
import sys
import warnings

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import soundfile as sf

QWEN3 = "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-bf16"
# name -> Hugging Face repository and how the engine takes a voice.
ENGINES = {
    "qwen3": {"repo": QWEN3, "voice": "preset"},
    "voxcpm2": {"repo": "mlx-community/VoxCPM2-bf16", "voice": "clone"},
    "chatterbox": {"repo": "mlx-community/chatterbox-multilingual-v3", "voice": "clone"},
    "omnivoice": {"repo": "mlx-community/OmniVoice-bfloat16", "voice": "clone"},
    "fish-s2": {"repo": "mlx-community/fish-audio-s2-pro", "voice": "clone"},
    "drama3": {"repo": "mlx-community/fish-audio-drama-3-4bit", "voice": "clone"},
    # Renamed upstream to bosonai/higgs-tts-3-4b; the old name redirects and keeps an existing cache valid.
    "higgs3": {"repo": "bosonai/higgs-audio-v3-tts-4b", "voice": "clone"},
}
LANGS = {"en": "english", "ru": "russian"}
QWEN3_VOICE = "ryan"
# What the default reference clip says. The Russian sentence is speech data, not prose.
REF_TEXT = {
    "en": "Hi there. Let me show you how this works, step by step, so you can try it yourself today.",
    "ru": "Привет. Сейчас я покажу, как это работает, шаг за шагом, чтобы вы смогли попробовать сами уже сегодня.",
}
ASR = "mlx-community/whisper-large-v3-turbo"
# WER above which a take counts as failed. tests/bench/calibrate.py, 2026-11-05: the 95th
# percentile of correct takes was 0.111 in English and 0.167 in Russian, but those thresholds caught
# only 68% and 20% of the distorted takes, under the 90% the calibration asks for, so the starting
# 12% stays. At 12% one wrong word passes in a line of nine words or more, and two pass from 17.
WER_FAIL = 0.12
# Characters per second below which a take counts as drawled: the engine's own median speed divided
# by 1.5, so a take half as long again as usual. tests/bench/calibrate.py, 2026-11-05, 60 takes per
# engine and language: median speed Qwen3 14.5 and VoxCPM2 16.5 in English, 13.0 and 17.9 in Russian.
SLOW_CPS = {("qwen3", "en"): 9.7, ("qwen3", "ru"): 8.7, ("voxcpm2", "en"): 11.0, ("voxcpm2", "ru"): 11.9}
# An engine not yet calibrated gets the lowest calibrated value, so it is penalised only when clearly slow.
SLOW_CPS_FALLBACK = {"en": 9.7, "ru": 8.7}
CACHE = pathlib.Path(os.environ.get("DEMO_TTS_CACHE", pathlib.Path.home() / ".cache" / "demo-video"))


def load(repo):
    from mlx_audio.tts.utils import load_model
    return load_model(repo)


def synth(model, engine, text, lang, voice, ref, speed):
    kw = {}
    if engine == "qwen3":
        kw = {"voice": voice, "lang_code": LANGS[lang], "speed": speed}
    elif engine == "chatterbox":
        kw = {"ref_audio": ref[0], "lang_code": lang}
    elif engine == "omnivoice":
        kw = {"ref_audio": ref[0], "ref_text": ref[1], "language": lang, "lang_code": lang}
    else:
        kw = {"ref_audio": ref[0], "ref_text": ref[1]}
    parts, rate = [], None
    for r in model.generate(text=text, verbose=False, **kw):
        parts.append(np.asarray(r.audio, dtype=np.float32).reshape(-1))
        rate = getattr(r, "sample_rate", None) or model.sample_rate
    if not parts:
        return None, rate
    return np.concatenate(parts), rate


def check(wav, refs, lang, engine):
    """Whisper's reading of a take, its WER against the line and whether it drawls."""
    import mlx_whisper
    from wer import line_wer

    result = mlx_whisper.transcribe(wav, path_or_hf_repo=ASR, language=lang, word_timestamps=True)
    heard = result["text"].strip()
    # Word timings let a slide change on a word: slides.mjs places an anchor by them.
    words = [{"w": w["word"].strip(), "t": round(w["start"], 2), "e": round(w["end"], 2)}
             for seg in result.get("segments", []) for w in seg.get("words", [])]
    sec = sf.info(wav).duration
    slow = len(refs[0]) / max(sec, 0.1) < SLOW_CPS.get((engine, lang), SLOW_CPS_FALLBACK[lang])
    return {"sec": round(sec, 2), "miss": round(line_wer(refs, heard, lang), 3), "slow": slow, "heard": heard,
            "words": words}


def record(takes, best):
    return {"best": best, "failed": takes[best]["miss"] > WER_FAIL,
            "takes": [{k: v for k, v in t.items() if k != "wav"} for t in takes]}


def reference(lang, voice):
    """Returns (wav path, transcript) of the clip a cloning engine copies."""
    if voice:
        wav = pathlib.Path(voice)
        txt = wav.with_suffix(".txt")
        if not wav.is_file() or not txt.is_file():
            sys.exit(f"--voice {voice}: needs the WAV file and its transcript in {txt.name}")
        return str(wav), txt.read_text(encoding="utf-8").strip()
    wav = CACHE / f"ref-qwen3-{QWEN3_VOICE}-{lang}.wav"
    if not wav.is_file():
        CACHE.mkdir(parents=True, exist_ok=True)
        qwen3 = load(QWEN3)
        audio, rate = synth(qwen3, "qwen3", REF_TEXT[lang], lang, QWEN3_VOICE, None, 1.0)
        sf.write(wav, audio, rate)
        # Free the 4.5 GB before the cloning engine loads.
        del qwen3
        import mlx.core as mx
        mx.clear_cache()
    return str(wav), REF_TEXT[lang]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lines")
    ap.add_argument("out")
    ap.add_argument("--engine", choices=sorted(ENGINES))
    ap.add_argument("--check-existing", action="store_true", help="only check the WAV files already in out-dir")
    ap.add_argument("--lang", default="en", choices=sorted(LANGS))
    ap.add_argument("--voice", default="")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--takes", type=int, default=1, help="takes per line; the best by Whisper wins")
    ap.add_argument("--retries", type=int, default=2, help="extra takes for a line whose best take failed")
    ap.add_argument("--report-peak", action="store_true", help="print the peak MLX memory in GB to stderr")
    a = ap.parse_args()

    # The libraries print progress to stdout; demo-kit.mjs reads stdout for line lengths.
    result = os.fdopen(os.dup(1), "w")
    os.dup2(2, 1)
    sys.stdout = sys.stderr

    with open(a.lines, encoding="utf-8") as f:
        lines = json.load(f)
    # A line is a string, or {"say", "text"}: the voice reads say, Whisper may match either.
    refs = {k: [v] if isinstance(v, str) else [v["say"], v.get("text") or v["say"]] for k, v in lines.items()}
    scores = {}
    if a.check_existing:
        for key in lines:
            wav = f"{a.out}/{key}.wav"
            scores[key] = record([check(wav, refs[key], a.lang, a.engine or "kokoro")], 0)
            print(key, scores[key]["takes"][0]["sec"], file=result, flush=True)
        write_scores(a.out, scores)
        return
    if not a.engine:
        sys.exit("--engine is required unless --check-existing")
    spec = ENGINES[a.engine]
    voice = a.voice or QWEN3_VOICE
    ref = reference(a.lang, a.voice) if spec["voice"] == "clone" else None
    model = load(spec["repo"])
    if a.engine == "qwen3" and voice.lower() not in model.get_supported_speakers():
        # Qwen3 ignores an unknown speaker and picks a random voice for every line.
        sys.exit(f"--voice {voice}: qwen3 speakers are {', '.join(model.get_supported_speakers())}")
    if ref and getattr(model, "preserve_ref_audio_path", False) is not True:
        # Same as mlx_audio.tts.generate: most engines take the clip as samples at their own rate.
        from mlx_audio.utils import load_audio
        ref = (load_audio(ref[0], sample_rate=model.sample_rate), ref[1])
    for key in lines:
        text = refs[key][0]
        takes = []
        def pick():
            """Among passing takes the steady one, then the closest; with none passing, the closest."""
            passing = [i for i, t in enumerate(takes) if t["miss"] <= WER_FAIL]
            if passing:
                return min(passing, key=lambda i: (takes[i]["slow"], takes[i]["miss"]))
            return min(range(len(takes)), key=lambda i: takes[i]["miss"])
        # A random take can fail on its own; a failed line gets up to --retries more takes before it is
        # reported, so one bad sample does not stop a whole demo.
        for n in range(max(1, a.takes) + a.retries):
            if n >= max(1, a.takes) and any(t["miss"] <= WER_FAIL for t in takes):
                break
            audio, rate = synth(model, a.engine, text, a.lang, voice, ref, a.speed)
            if audio is None or not len(audio):
                continue
            wav = f"{a.out}/{key}.take{n}.wav"
            sf.write(wav, audio, rate)
            takes.append({"wav": wav, **check(wav, refs[key], a.lang, a.engine)})
        if not takes:
            sys.exit(f"line {key}: {a.engine} produced no audio for {text!r}")
        best = pick()
        os.replace(takes[best]["wav"], f"{a.out}/{key}.wav")
        for i, t in enumerate(takes):
            if i != best:
                os.remove(t["wav"])
        scores[key] = record(takes, best)
        print(key, takes[best]["sec"], file=result, flush=True)
    write_scores(a.out, scores)
    if a.report_peak:
        import mlx.core as mx
        print(f"peak_gb {mx.get_peak_memory() / 1e9:.1f}", file=sys.stderr)


def write_scores(out, scores):
    with open(f"{out}/takes.json", "w", encoding="utf-8") as f:
        json.dump(scores, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
