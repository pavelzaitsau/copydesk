#!/bin/sh
# Records the sample deck on the fake engine and checks the picture: a frame of the busiest slide
# state that shows at a paragraph's start must match its PNG render with SSIM 0.95 or better.
# Needs node, ffmpeg and `npm install` in demo-video/ once.
#   e2e-slides.sh [out-dir]
set -eu
here=$(cd "$(dirname "$0")" && pwd)
deck="$here/../evals/fixtures/sample-slides/slides.json"
out=${1:-$(mktemp -d)}; mkdir -p "$out"; out=$(cd "$out" && pwd)
node "$here/../scripts/slides.mjs" "$deck" "$out" > "$out/run.log" 2>&1 || { cat "$out/run.log" >&2; exit 1; }
for f in sample.mp4 sample.vtt sample.mp3 chapters.txt timing.json sheet.jpg slides.pdf; do
  [ -s "$out/$f" ] || { echo "missing $f" >&2; exit 1; }
done
[ "$(wc -c < "$out/slides.pdf")" -gt 50000 ] || { echo "slides.pdf has no images" >&2; exit 1; }
ffprobe -v error -show_entries stream=codec_name -of csv=p=0 "$out/sample.mp4" | grep -q mov_text || { echo "no subtitle track" >&2; exit 1; }
[ "$(ffprobe -v error -show_chapters -of csv=p=0 "$out/sample.mp4" | wc -l)" -eq 4 ] || { echo "expected 4 chapters" >&2; exit 1; }
# The busiest state shown at a paragraph's start: the most characters of slide text.
set -- $(node -e '
  const fs = require("fs"); const deck = JSON.parse(fs.readFileSync(process.argv[1]));
  const html = fs.readFileSync(require("path").join(require("path").dirname(process.argv[1]), deck.html), "utf8");
  const text = (id) => (html.match(new RegExp(`<section id="${id}"[^>]*>([\\s\\S]*?)</section>`)) || ["", ""])[1].replace(/<[^>]+>/g, "").length;
  const t = JSON.parse(fs.readFileSync(process.argv[2] + "/timing.json"));
  const s = deck.states.filter((x) => !x.anchor).sort((a, b) => text(b.id) - text(a.id))[0];
  console.log(s.id, (t.paragraphs[s.para].start + 0.5).toFixed(2));' "$deck" "$out")
ffmpeg -v error -y -ss "$2" -i "$out/sample.mp4" -frames:v 1 "$out/frame-$1.png"
ssim=$(ffmpeg -i "$out/frame-$1.png" -i "$out/png/$1.png" -lavfi ssim -f null - 2>&1 | sed -n 's/.*All:\([0-9.]*\).*/\1/p')
python3 -c "import sys; s=float('$ssim'); print(f'ssim {s:.3f} for $1'); sys.exit(0 if s >= 0.95 else 1)"

# A chapter on its own does not join, and says what is left; a text changed after voicing stops the
# recording instead of playing the old audio under the new subtitles.
cp -R "$(dirname "$deck")" "$out/deck"; d2="$out/deck/slides.json"; o2="$out/by-chapter"
node "$here/../scripts/slides.mjs" "$d2" "$o2" --voice-only 2>/dev/null
node "$here/../scripts/slides.mjs" "$d2" "$o2" --record --chapter 0 2> "$o2/log" || { cat "$o2/log" >&2; exit 1; }
grep -q 'still to record before the join: 1, 2, 3' "$o2/log" || { echo "no list of chapters left" >&2; exit 1; }
[ ! -e "$o2/sample.mp4" ] || { echo "joined with chapters missing" >&2; exit 1; }
sed -i '' 's/in two minutes/in three minutes/' "$d2"
if node "$here/../scripts/slides.mjs" "$d2" "$o2" --record 2> "$o2/log"; then echo "recorded a changed text without voicing it" >&2; exit 1; fi
grep -q 'changed since voicing: p1' "$o2/log" || { cat "$o2/log" >&2; exit 1; }
echo "ok: $out/sample.mp4"
