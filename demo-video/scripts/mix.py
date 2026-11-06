#!/usr/bin/env python3
"""Turns a demo-kit recording into an MP4 and prints what to check.

    mix.py <run-dir> <out.mp4> [--frames SECONDS,...]
    mix.py join <out.mp4> --parts A.mp4 B.mp4 ... --chapters chapters.json --vtt subs.vtt [--mp3 OUT.mp3]

Reads <run-dir>/run.json and the WebM it names. Trims the video to [startOffset, endAt]. Places
each voice clip (<run-dir>/voice/<key>.wav) at its logged start. Mixes them to -16 LUFS with a
-2 dBTP true-peak target, and encodes H.264/AAC at 25 fps. AAC overshoots the limiter: with a
-1.5 dBTP target, a test run peaked at -1.3 dB. At -2 dBTP the same run peaked at -1.7 dB. Without clips the MP4 has no audio track.

Then prints duration, size and loudness. Writes one frame per line to <run-dir>/frames/, one
second into the line, or into its middle when the line is shorter than two seconds. Each --frames
time adds frames/t=<seconds>.jpg. The frames show the picture under each line, so it can be
checked. Lines are logged with and without a voice.

join glues the MP4s of separately recorded chapters into one: the picture as is, the voice
normalised once more over the whole, chapters from chapters.json ([{"title", "start"}] in seconds)
and the VTT as a subtitle track a player can switch off. It checks the result against the loudness
criterion, LOUDNESS below, measured with ebur128 after the join, and exits 1 when it misses.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys

FPS = 25
# The loudness a finished video must meet: integrated -16 +/- 1 LU, true peak at or below -1.5 dBTP.
LOUDNESS = {"target": -16.0, "tolerance": 1.0, "max_true_peak": -1.5}


def run(*cmd, capture=False):
    return subprocess.run(cmd, check=True, text=True, capture_output=capture)


def loudness(path):
    """Integrated loudness and true peak of a file, by ebur128."""
    out = run("ffmpeg", "-v", "info", "-i", str(path), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-",
              capture=True).stderr
    summary = out[out.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+|-inf) LUFS", summary)
    tp = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summary)
    val = lambda m: float("-inf") if not m or m.group(1) == "-inf" else float(m.group(1))
    return val(i), val(tp)


def join(argv):
    ap = argparse.ArgumentParser(prog="mix.py join")
    ap.add_argument("out", type=pathlib.Path)
    ap.add_argument("--parts", nargs="+", type=pathlib.Path, required=True)
    ap.add_argument("--chapters", type=pathlib.Path, required=True)
    ap.add_argument("--vtt", type=pathlib.Path, required=True)
    ap.add_argument("--mp3", type=pathlib.Path)
    ap.add_argument("--title", default="")
    ap.add_argument("--lang", default="en")
    a = ap.parse_args(argv)
    work = a.parts[0].parent / "join"
    work.mkdir(parents=True, exist_ok=True)
    (work / "list.txt").write_text("".join(f"file '{p.resolve()}'\n" for p in a.parts))
    durations = [float(json.loads(run("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json",
                                       str(p), capture=True).stdout)["format"]["duration"]) for p in a.parts]
    total = sum(durations)
    chapters = json.loads(a.chapters.read_text(encoding="utf-8"))
    meta = [";FFMETADATA1", f"title={a.title}"]
    for k, c in enumerate(chapters):
        end = chapters[k + 1]["start"] if k + 1 < len(chapters) else total
        meta += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(c['start'] * 1000)}", f"END={int(end * 1000)}", f"title={c['title']}"]
    (work / "meta.txt").write_text("\n".join(meta) + "\n", encoding="utf-8")
    lang3 = {"en": "eng", "ru": "rus"}.get(a.lang, "und")
    run("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(work / "list.txt"),
        "-i", str(work / "meta.txt"), "-i", str(a.vtt), "-map", "0:v", "-map", "0:a", "-map", "2:s",
        "-map_metadata", "1", "-map_chapters", "1", "-c:v", "copy",
        "-af", "loudnorm=I=-16:TP=-2:LRA=11", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
        "-c:s", "mov_text", "-metadata:s:s:0", f"language={lang3}", "-metadata:s:a:0", f"language={lang3}",
        # ffmpeg 9 writes the chapter track at the subtitle track's timescale unless the movie's is set,
        # which collapses every chapter after the first few onto one start time.
        "-movie_timescale", "1000", "-movflags", "+faststart", str(a.out))
    if a.mp3:
        run("ffmpeg", "-v", "error", "-y", "-i", str(a.out), "-vn", "-c:a", "libmp3lame", "-q:a", "2", str(a.mp3))
    got = [round(float(c["start_time"]), 2) for c in json.loads(run("ffprobe", "-v", "error", "-show_chapters", "-of", "json",
                                                                   str(a.out), capture=True).stdout)["chapters"]]
    want = [round(int(c["start"] * 1000) / 1000, 2) for c in chapters]
    if got != want:
        sys.exit(f"{a.out}: chapters start at {got}, not {want}")
    i, tp = loudness(a.out)
    print(f"{a.out}: {total:.1f} s, {len(chapters)} chapters; loudness {i:.1f} LUFS, true peak {tp:.1f} dBTP")
    silent = i <= -70  # ebur128 reports silence as -70 LUFS
    if not silent and (abs(i - LOUDNESS["target"]) > LOUDNESS["tolerance"] or tp > LOUDNESS["max_true_peak"]):
        print(f"loudness misses {LOUDNESS}", file=sys.stderr)
        sys.exit(1)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "join":
        return join(sys.argv[2:])
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=pathlib.Path)
    ap.add_argument("out", type=pathlib.Path)
    ap.add_argument("--frames", default="", help="extra frame times in seconds of the output, comma-separated")
    a = ap.parse_args()

    d = json.loads((a.run_dir / "run.json").read_text())
    video = pathlib.Path(d["video"]) if d.get("video") else next(a.run_dir.glob("*.webm"))
    s0, end = d["startOffset"], d["endAt"]
    if end <= s0:
        sys.exit(f"run.json: endAt {end} is not after startOffset {s0}")
    lines = d.get("clips", [])
    clips = lines if d.get("voice") else []

    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{s0:.3f}", "-t", f"{end - s0:.3f}", "-i", str(video)]
    filters, labels = [], []
    for i, c in enumerate(clips, start=1):
        cmd += ["-i", str(a.run_dir / "voice" / f"{c['key']}.wav")]
        ms = max(0, round((c["t"] - s0) * 1000))
        filters.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
        labels.append(f"[a{i}]")
    if clips:
        # Pad or cut the audio to the video's exact length.
        filters.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0,"
                       f"loudnorm=I=-16:TP=-2:LRA=11,apad=whole_dur={end - s0:.3f},atrim=0:{end - s0:.3f}[aout]")
        cmd += ["-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[aout]",
                "-c:a", "aac", "-b:a", "160k", "-ar", "48000"]
    else:
        cmd += ["-map", "0:v", "-an"]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-movflags", "+faststart", str(a.out)]
    run(*cmd)

    probe = run("ffprobe", "-v", "error", "-show_entries", "format=duration,size", "-of", "json", str(a.out),
                capture=True)
    fmt = json.loads(probe.stdout)["format"]
    duration = float(fmt["duration"])
    print(f"{a.out}: {duration:.1f} s, {int(fmt['size']) / 1e6:.1f} MB")
    if clips:
        vol = run("ffmpeg", "-v", "info", "-i", str(a.out), "-vn", "-af", "volumedetect", "-f", "null", "-",
                  capture=True).stderr
        print(" ".join(re.findall(r"(?:mean|max)_volume: \S+ dB", vol)))

    frames = a.run_dir / "frames"
    frames.mkdir(exist_ok=True)
    # One second into each line, or the middle of a line shorter than two seconds.
    marks = [(c["key"], c["t"] - s0 + min(1.0, c.get("len", 2.0) / 2)) for c in lines]
    # '=' cannot appear in a line key, so an extra frame never overwrites a line's frame.
    marks += [(f"t={t.strip()}", float(t)) for t in a.frames.split(",") if t.strip()]
    # ffmpeg fails on a seek into the last frame or past it, and the MP4 is already
    # written by then. Skip such a frame instead: 9.99 s failed on a 10.0 s video.
    last = duration - 1 / FPS
    late = [name for name, t in marks if t > last]
    if late:
        print(f"no frame for {', '.join(late)}: past the last frame at {last:.2f} s")
    marks = [(name, t) for name, t in marks if t <= last]
    for name, t in marks:
        run("ffmpeg", "-v", "error", "-y", "-ss", f"{max(0, t):.2f}", "-i", str(a.out), "-frames:v", "1",
            "-vf", "scale=640:-1", str(frames / f"{name}.jpg"))
    if marks:
        print(f"{len(marks)} frames in {frames}")


if __name__ == "__main__":
    main()
