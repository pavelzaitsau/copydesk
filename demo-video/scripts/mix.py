#!/usr/bin/env python3
"""Turns a demo-kit recording into an MP4 and prints what to check.

    mix.py <run-dir> <out.mp4> [--frames SECONDS,...]

Reads <run-dir>/run.json and the WebM it names. Trims the video to [startOffset, endAt]. Places
each voice clip (<run-dir>/voice/<key>.wav) at its logged start. Mixes them to -16 LUFS with a
-2 dBTP true-peak target, and encodes H.264/AAC at 25 fps. AAC overshoots the limiter: with a
-1.5 dBTP target, a test run peaked at -1.3 dB. At -2 dBTP the same run peaked at -1.7 dB. Without clips the MP4 has no audio track.

Then prints duration, size and loudness. Writes one frame per line to <run-dir>/frames/, one
second into the line, or into its middle when the line is shorter than two seconds. Each --frames
time adds frames/t=<seconds>.jpg. The frames show the picture under each line, so it can be
checked. Lines are logged with and without a voice.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys

FPS = 25


def run(*cmd, capture=False):
    return subprocess.run(cmd, check=True, text=True, capture_output=capture)


def main():
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
