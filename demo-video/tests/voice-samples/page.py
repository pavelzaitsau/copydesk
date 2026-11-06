"""page.py <samples-dir>: writes index.html, a scoring sheet for <dir>/wav/<engine>-<voice>-<lang>.wav.

The sample texts are speech data in the language each voice speaks. The licences in NOTE are a copy of
ENGINES in scripts/demo-kit.mjs, which owns them.
"""
import json, pathlib, sys, html
import soundfile as sf

d = pathlib.Path(sys.argv[1])
TEXT = {
    "en": "Wait, is it really done already? Great! Three hundred and twelve rows checked, and Oleg didn't even finish his coffee.",
    "ru": "Подожди, неужели уже готово? Отлично! Триста двенадцать строк проверены, а Олег даже не успел допить свой кофе.",
}
ORDER = ["drama3", "fish-s2", "higgs3", "qwen3", "voxcpm2", "chatterbox", "omnivoice", "kokoro"]
NOTE = {
    "drama3": "Fish Audio Drama 3 · clone of the reference · conditional licence",
    "fish-s2": "Fish Audio S2 Pro · clone of the reference · non-commercial",
    "higgs3": "Higgs Audio V3 · clone of the reference · non-commercial",
    "qwen3": "Qwen3-TTS 1.7B · preset voices · Apache-2.0",
    "voxcpm2": "VoxCPM2 · clone of the reference · Apache-2.0",
    "chatterbox": "Chatterbox Multilingual · clone of the reference · MIT",
    "omnivoice": "OmniVoice · clone of the reference · CC-BY-NC, non-commercial",
    "kokoro": "Kokoro 82M · preset voices · English only · Apache-2.0",
}
items = []
for w in sorted((d / "wav").glob("*.wav")):
    stem = w.stem
    lang = stem.rsplit("-", 1)[1]
    engine = next(e for e in ORDER if stem.startswith(e + "-"))
    voice = stem[len(engine) + 1 : -len(lang) - 1]
    info = sf.info(w)
    items.append({"id": stem, "file": f"wav/{w.name}", "engine": engine, "voice": voice, "lang": lang, "sec": round(info.duration, 1)})
items.sort(key=lambda i: (i["lang"], ORDER.index(i["engine"]), i["voice"]))

rows = []
for lang in ["en", "ru"]:
    rows.append(f'<h2>{"English" if lang == "en" else "Russian"}</h2><p class="t">{html.escape(TEXT[lang])}</p>')
    for e in ORDER:
        group = [i for i in items if i["lang"] == lang and i["engine"] == e]
        if not group:
            continue
        rows.append(f'<h3>{e} <span>{html.escape(NOTE[e])}</span></h3><div class="g">')
        for i in group:
            stars = "".join(f'<button data-v="{n}">{n}</button>' for n in range(1, 6))
            label = "reference: ryan" if i["voice"] == "ref" else i["voice"]
            rows.append(f'<div class="c" data-id="{i["id"]}"><div class="n">{label} <small>{i["sec"]} s</small></div>'
                        f'<audio controls preload="none" src="{i["file"]}"></audio>'
                        f'<div class="r">{stars}</div><input placeholder="note"></div>')
        rows.append("</div>")

page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Voice samples</title><style>
:root{{--bg:#f6f7f9;--card:#fff;--ink:#1c2430;--mute:#6b7685;--line:#e2e6eb;--acc:#2563eb}}
@media (prefers-color-scheme:dark){{:root{{--bg:#12161c;--card:#1b2129;--ink:#e6eaef;--mute:#8d97a5;--line:#2a323d;--acc:#5b8cff}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,Helvetica,Arial,sans-serif;padding:24px 16px 80px;max-width:1200px;margin:auto}}
h1{{margin:0 0 4px}}h2{{margin:36px 0 4px}}h3{{margin:22px 0 8px;font-size:16px}}h3 span{{color:var(--mute);font-weight:400;font-size:13px;margin-left:8px}}
.t{{color:var(--mute);margin:0 0 8px}}.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}}
.c{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px}}.n{{font-weight:600;margin-bottom:6px}}.n small{{color:var(--mute);font-weight:400}}
audio{{width:100%;height:34px}}.r{{display:flex;gap:4px;margin:6px 0}}.r button{{flex:1;border:1px solid var(--line);background:transparent;color:var(--ink);border-radius:6px;padding:3px 0;cursor:pointer}}
.r button.on{{background:var(--acc);color:#fff;border-color:var(--acc)}}input{{width:100%;box-sizing:border-box;border:1px solid var(--line);background:transparent;color:var(--ink);border-radius:6px;padding:4px 6px}}
#bar{{position:fixed;left:0;right:0;bottom:0;background:var(--card);border-top:1px solid var(--line);padding:10px 16px;display:flex;gap:10px;align-items:center}}
#bar button{{background:var(--acc);color:#fff;border:0;border-radius:8px;padding:8px 14px;font-weight:600;cursor:pointer}}#bar span{{color:var(--mute)}}
</style></head><body>
<h1>Voice samples</h1><p class="t">{len(items)} samples. The 1-5 score and the note stay in this browser. "Copy scores" puts them on the clipboard, to paste into a chat.</p>
{''.join(rows)}
<div id="bar"><button id="copy">Copy scores</button><span id="cnt"></span></div>
<script>
const KEY='voice-samples-ratings';let S={{}};try{{S=JSON.parse(localStorage.getItem(KEY)||'{{}}')}}catch(e){{}}
const save=()=>{{try{{localStorage.setItem(KEY,JSON.stringify(S))}}catch(e){{}};document.getElementById('cnt').textContent=Object.values(S).filter(x=>x.r).length+' scored of {len(items)}'}};
document.querySelectorAll('.c').forEach(c=>{{const id=c.dataset.id,s=S[id]||{{}};const inp=c.querySelector('input');inp.value=s.n||'';
 const paint=()=>c.querySelectorAll('.r button').forEach(b=>b.classList.toggle('on',+b.dataset.v===(S[id]||{{}}).r));paint();
 c.querySelectorAll('.r button').forEach(b=>b.onclick=()=>{{S[id]={{...S[id],r:+b.dataset.v}};paint();save()}});
 inp.oninput=()=>{{S[id]={{...S[id],n:inp.value}};save()}};
 c.querySelector('audio').onplay=e=>document.querySelectorAll('audio').forEach(a=>a!==e.target&&a.pause());}});
document.getElementById('copy').onclick=()=>{{const t=Object.entries(S).filter(([k,v])=>v.r||v.n).map(([k,v])=>k+': '+(v.r||'-')+(v.n?' ('+v.n+')':'')).join('\\n');navigator.clipboard.writeText(t).then(()=>document.getElementById('cnt').textContent='Copied')}};
save();
</script></body></html>"""
(d / "index.html").write_text(page, encoding="utf-8")
print(len(items), "samples")
