#!/usr/bin/env python3
"""Builds the paragraphs of demo-video's slides.json from an explainer script.

    build_deck.py script.md lexicon.md deck.json

deck.json is the deck the agent wrote: html, speakers, states, apps, inserts and the rest of
demo-video's assets/slides-schema.json, without paragraphs. The script writes its paragraphs from
script.md: an id per paragraph, c<chapter>p<n> with two digits each (c01p01, c01p02, c02p01), the
chapter title, the speaker, `text` with the claim marks stripped, and `say` with the pronunciation
dictionary applied. Each state's anchor is written as in the text and kept in `anchorText`; the
script sets `anchor`, a phrase of `say`, from it on every run, so a second run never respells twice.
An `anchor` edited by hand since the last run becomes the new `anchorText`; a lexicon change since
the last run respells the anchor again; an anchor removed by hand stays removed. It sets `version` 1, keeps every other key of deck.json and writes it in place.

lexicon.md is a Markdown table | written | say |: each written form, matched as a whole word with
its case, is read as `say`. Numbers belong there too when the voice should read them a set way.
"""
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from lint_script import parse  # noqa: E402


def lexicon(text):
    pairs = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else []
        if len(cells) >= 2 and cells[0].lower() not in ("written", "") and not set(cells[0]) <= set("-: "):
            pairs.append((cells[0].strip("`"), cells[1].strip("`")))
    # Longer forms first, so "Claude Code" wins over "Claude".
    return sorted(pairs, key=lambda p: -len(p[0]))


def apply(text, pairs):
    for written, said in pairs:
        text = re.sub(rf"(?<!\w){re.escape(written)}(?!\w)", said, text)
    return text


def anchors(states, pairs):
    """Keeps each anchor's written form in anchorText and the form last written to anchor in
    anchorSaid. An anchor that differs from anchorSaid was edited by hand and becomes the new written
    form; otherwise anchor is rebuilt from anchorText with the current lexicon."""
    for s in states:
        if not s.get("anchor") and s.get("anchorSaid"):
            # Removed by hand: the state now shows at its paragraph's start.
            s.pop("anchor", None), s.pop("anchorText", None), s.pop("anchorSaid", None)
            continue
        if s.get("anchor") and s["anchor"] != s.get("anchorSaid"):
            s["anchorText"] = s["anchor"]
        if s.get("anchorText"):
            s["anchor"] = s["anchorSaid"] = apply(s["anchorText"], pairs)


def main():
    script, lex, deck_path = (pathlib.Path(p) for p in sys.argv[1:4])
    _, lang, chapters = parse(script.read_text(encoding="utf-8"))
    pairs = lexicon(lex.read_text(encoding="utf-8")) if lex.exists() else []
    deck = json.loads(deck_path.read_text(encoding="utf-8"))
    paras = []
    for k, (title, items) in enumerate(chapters, 1):
        for n, (speaker, p) in enumerate(items, 1):
            text = re.sub(r"\s+", " ", re.sub(r"\s*\[c\d+\]", "", p)).strip()
            said = apply(text, pairs)
            para = {"id": f"c{k:02d}p{n:02d}", "chapter": title, "speaker": speaker, "text": text}
            if said != text:
                para["say"] = said
            paras.append(para)
    deck["paragraphs"] = paras
    deck.setdefault("version", 1)
    deck.setdefault("lang", lang)
    anchors(deck.get("states", []), pairs)
    deck_path.write_text(json.dumps(deck, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{deck_path}: {len(paras)} paragraphs in {len(chapters)} chapters")


if __name__ == "__main__":
    main()
