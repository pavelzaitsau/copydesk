#!/usr/bin/env python3
"""Fits voice strengths to the blind pairwise vote and writes the voice list the skill picks from.

    fit_votes.py [--check]

Reads assets/voice-vote.json, fits a Bradley-Terry model with a normal prior per group (language
and sex), keeps the 3 strongest voices of each group, drops those assets/removed.json names, and writes assets/voices.json, which
demo-kit.mjs reads as VOICES. It also rewrites the generated blocks between
<!-- fit_votes:NAME --> and <!-- /fit_votes --> in SKILL.md and references/voice-vote.md, so no
strength or count is typed by hand. --check writes nothing and fails when any of them is stale, or
when a default voice in assets/defaults.json is missing from the list or not 'clean' in ENGINES.

Strength is the chance, in percent, to beat an average voice of the same group: the logistic of
the fitted log-strength, with the prior centred on an average voice. A sample is named
<engine>-<voice>-<lang>; "ref" means the engine cloned the default reference clip.
"""
import json
import math
import pathlib
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
VOTES = ROOT / "assets" / "voice-vote.json"
OUT = ROOT / "assets" / "voices.json"
DEFAULTS = ROOT / "assets" / "defaults.json"
REMOVED = ROOT / "assets" / "removed.json"
KIT = ROOT / "scripts" / "demo-kit.mjs"
DOCS = {"voices": ROOT / "SKILL.md", "result": ROOT / "references" / "voice-vote.md",
        "stats": ROOT / "references" / "voice-vote.md"}
PRIOR_SIGMA = 1.0  # A wider prior lets a voice with 4 comparisons claim an extreme strength.
KEEP = 3
ENGINES = ("qwen3", "kokoro", "voxcpm2", "chatterbox", "omnivoice", "fish-s2", "drama3", "higgs3")


def parse(sample):
    """Splits '<engine>-<voice>-<lang>' where the engine name may itself hold a hyphen."""
    for engine in sorted(ENGINES, key=len, reverse=True):
        if sample.startswith(engine + "-"):
            voice, lang = sample[len(engine) + 1:].rsplit("-", 1)
            return engine, voice, lang
    raise ValueError(f"unknown engine in sample {sample!r}")


def name_of(engine, voice):
    """The name a demo picks: the preset voice, or the engine for a clone of the default clip."""
    if voice == "ref":
        return "voxcpm" if engine == "voxcpm2" else engine
    if engine == "kokoro":
        return voice.split("_", 1)[1]
    return voice


def fit(votes):
    """MAP Bradley-Terry by gradient ascent. Returns {sample: theta}."""
    samples = sorted({v["a"] for v in votes} | {v["b"] for v in votes})
    theta = {s: 0.0 for s in samples}
    for _ in range(5000):
        grad = {s: -theta[s] / PRIOR_SIGMA ** 2 for s in samples}
        for v in votes:
            p = 1 / (1 + math.exp(theta[v["b"]] - theta[v["a"]]))
            grad[v["a"]] += v["s"] - p
            grad[v["b"]] -= v["s"] - p
        step = max(abs(g) for g in grad.values())
        for s in samples:
            theta[s] += 0.1 * grad[s]
        if step < 1e-9:
            break
    return theta


def build():
    votes = json.loads(VOTES.read_text(encoding="utf-8"))["votes"]
    groups = defaultdict(list)
    for v in votes:
        groups[v["g"]].append(v)
    rows = []
    for group, gv in sorted(groups.items()):
        lang, sex = group.split("-")
        theta = fit(gv)
        record = defaultdict(lambda: [0, 0, 0])
        for v in gv:
            for side, own in (("a", v["s"]), ("b", 1 - v["s"])):
                r = record[v[side]]
                r[0 if own > 0.5 else 1 if own < 0.5 else 2] += 1
        for sample, t in theta.items():
            engine, voice, _ = parse(sample)
            rows.append({"lang": lang, "sex": sex, "name": name_of(engine, voice), "engine": engine,
                         "voice": "default" if voice == "ref" else voice,
                         "strength": round(100 / (1 + math.exp(-t))), "record": record[sample]})
    rows.sort(key=lambda r: (r["lang"], r["sex"], -r["strength"], r["name"]))
    voices = defaultdict(dict)
    kept = defaultdict(int)
    removed = json.loads(REMOVED.read_text(encoding="utf-8")) if REMOVED.exists() else {}
    for r in rows:
        if kept[(r["lang"], r["sex"])] < KEEP and r["name"] in removed.get(r["lang"], []):
            # Removed by ear: the place stays empty, so no voice nobody has heard joins the list.
            kept[(r["lang"], r["sex"])] += 1
            r["removed"] = True
            continue
        if kept[(r["lang"], r["sex"])] < KEEP:
            if r["name"] in voices[r["lang"]]:
                # A Kokoro voice loses its prefix (am_eric -> eric) and can meet a Qwen3 speaker of the same name.
                sys.exit(f"two kept {r['lang']} voices are named '{r['name']}': rename one in name_of()")
            kept[(r["lang"], r["sex"])] += 1
            r["kept"] = True
            voices[r["lang"]][r["name"]] = {k: r[k] for k in ("engine", "voice", "sex", "strength")}
    return rows, {lang: dict(v) for lang, v in sorted(voices.items())}, stats(votes, groups)


def stats(votes, groups):
    """Counts the prose about the vote quotes: answers, repeated pairs, fewest opponents."""
    checks = [v for v in votes if v.get("check")]
    same_side = 0
    for c in checks:
        first = [v for v in votes if not v.get("check") and {v["a"], v["b"]} == {c["a"], c["b"]} and v["n"] < c["n"]][-1]
        s = first["s"] if first["a"] == c["a"] else 1 - first["s"]
        same_side += (s > 0.5) == (c["s"] > 0.5) and (s < 0.5) == (c["s"] < 0.5)
    opponents = defaultdict(set)
    for v in votes:
        opponents[v["a"]].add(v["b"])
        opponents[v["b"]].add(v["a"])
    return {"answers": len(votes), "repeats": len(checks), "same_side": same_side,
            "min_opponents": min(len(o) for o in opponents.values())}


def engine_classes():
    """Licence class per engine, read from ENGINES in demo-kit.mjs, which owns it."""
    import re
    return dict(re.findall(r"^\s+'?([\w-]+)'?: \{ langs: \[[^\]]*\], licence: '(\w+)'", KIT.read_text(), re.M))


def blocks(rows, voices, st):
    table = ["| Group | Voice | Engine | Strength | Wins, losses, ties |", "| --- | --- | --- | --- | --- |"]
    for r in rows:
        w, l, t = r["record"]
        kept = " (kept)" if r.get("kept") else " (removed)" if r.get("removed") else ""
        table.append(f"| {r['lang']}-{r['sex']} | `{r['name']}`{kept} | `{r['engine']}` | {r['strength']} | {w}, {l}, {t} |")
    defaults = json.loads(DEFAULTS.read_text(encoding="utf-8"))
    lst = ["| Language | Male | Female |", "| --- | --- | --- |"]
    for lang, vs in voices.items():
        cell = lambda sex: ", ".join(f"`{n}`" + (" (default)" if defaults.get(lang) == n else "") for n, v in vs.items() if v["sex"] == sex)
        lst.append(f"| `{lang}` | {cell('m')} | {cell('f')} |")
    prose = (f"{st['answers']} answers in all. {st['repeats']} pairs were asked again with the sides swapped; "
             f"{st['same_side']} of them kept the same side (both times A better, both times B better, or both times the same). "
             f"Each voice met at least {st['min_opponents']} different opponents; a group of 3 voices allows no more than 2.")
    return {"voices": "\n".join(lst), "result": "\n".join(table), "stats": prose}


def splice(text, name, body):
    import re
    pat = re.compile(rf"(<!-- fit_votes:{name} -->\n).*?(\n<!-- /fit_votes -->)", re.S)
    if not pat.search(text):
        sys.exit(f"no <!-- fit_votes:{name} --> block")
    return pat.sub(lambda m: m.group(1) + body + m.group(2), text)


def check_defaults(voices):
    classes = engine_classes()
    for lang, name in json.loads(DEFAULTS.read_text(encoding="utf-8")).items():
        v = voices.get(lang, {}).get(name)
        if not v:
            sys.exit(f"defaults.json: '{name}' is not in the {lang} voice list")
        if classes.get(v["engine"]) != "clean":
            sys.exit(f"defaults.json: '{name}' runs on {v['engine']}, whose licence is not 'clean'")


def main():
    rows, voices, st = build()
    check_defaults(voices)
    files = {OUT: json.dumps(voices, ensure_ascii=False, indent=1) + "\n"}
    generated = blocks(rows, voices, st)
    for name, path in DOCS.items():
        text = files.get(path, path.read_text(encoding="utf-8"))
        files[path] = splice(text, name, generated[name])
    stale = [p for p, t in files.items() if not p.is_file() or p.read_text(encoding="utf-8") != t]
    if "--check" in sys.argv:
        if stale:
            sys.exit("stale, run fit_votes.py: " + ", ".join(str(p.relative_to(ROOT)) for p in stale))
        return
    for p in stale:
        p.write_text(files[p], encoding="utf-8")
    print(f"{len(rows)} voices; wrote {', '.join(str(p.relative_to(ROOT)) for p in stale) or 'nothing'}", file=sys.stderr)


if __name__ == "__main__":
    main()
