#!/usr/bin/env python3
"""Checks the text of slides.html against claims.md, and the share of states that only print text.

    check_slides.py slides.html claims.md

Errors, exit code 1:
- a token of slide text that holds a digit (a number, a date, an identifier such as FR-12) and that
  neither the claim nor the values column of claims.md holds, matched as a whole and ignoring case.
  The claim column counts too: the script says "forty-eight" and lists that as the value, while the
  claim holds 48. A figure typed from memory is the error the claim check exists to stop;
- list and thesis states above 30% of the deck: they print what the voice already says.

Exempt from the claim check: a state with class `code` or `artefact`, which quotes a real file, and an element with
class `tick`, an axis scale rather than a fact. Text inside <style> and <script>, attributes and CSS
counters is no slide text. Every <section class="slide"> is one state, as in assets/slides-template.html.
The check reads the HTML as written, with no browser, so a hidden element counts as well.
"""
import html.parser
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from lint_script import claims  # noqa: E402

TEXT_ONLY = ("list", "thesis")
MAX_TEXT_SHARE = 0.3
TOKEN = re.compile(r"[\w.,:/-]*\d[\w.,:/-]*")
EDGE = ".,:/-"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class Slides(html.parser.HTMLParser):
    """Collects each state's id, classes and text. Tolerates an unclosed element such as <li>: an end tag
    closes everything opened after the element it names."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.states = []  # [{"id", "classes", "text": [str]}]
        self.stack = []  # [(tag, opens_a_state, skips_text)]

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        state = tag == "section" and "slide" in classes
        if state:
            self.states.append({"id": a.get("id", ""), "classes": classes, "text": []})
        skip = tag in ("style", "script") or "tick" in classes
        self.stack.append((tag, state, skip))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if not self.stack or any(skip for _, _, skip in self.stack):
            return
        if any(state for _, state, _ in self.stack) and data.strip():
            self.states[-1]["text"].append(data)


def states(page):
    p = Slides()
    p.feed(page)
    p.close()
    # Text nodes joined by spaces: "4" and "12" in two elements are two tokens, not "412".
    return [{**s, "text": " ".join(s["text"])} for s in p.states]


def claim_values(claims_text):
    """The claim and every value of each row in claims.md, lower-cased."""
    out = []
    for row in claims(claims_text).values():
        out += [v.lower() for v in row["values"]]
        if row["claim"]:
            out.append(row["claim"].lower())
    return out


def unclaimed(text, values):
    """Tokens of text that hold a digit and appear in no value as a whole: "12" does not match "FR-12"
    or "12.5"."""
    out = []
    for raw in TOKEN.findall(text):
        token = raw.strip(EDGE).lower()
        if not re.search(r"\d", token) or token in out:
            continue
        whole = re.compile(rf"(?<![\w/:-])(?<!\d[.,]){re.escape(token)}(?![\w/:-]|[.,]\d)")
        if not any(whole.search(v) for v in values):
            out.append(token)
    return out


def check(page, claims_text):
    deck = states(page)
    values = claim_values(claims_text)
    problems = []
    for s in deck:
        if "code" in s["classes"] or "artefact" in s["classes"]:
            continue
        problems += [f"{s['id']}: '{t}' is no value in claims.md" for t in unclaimed(s["text"], values)]
    text_only = sum(1 for s in deck if set(TEXT_ONLY) & set(s["classes"]))
    if deck and text_only / len(deck) > MAX_TEXT_SHARE:
        problems.append(f"{text_only} of {len(deck)} states are {' or '.join(TEXT_ONLY)}, above {MAX_TEXT_SHARE:.0%}; "
                        "redraw some as diagrams")
    return problems


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: check_slides.py slides.html claims.md")
    page, claims_md = (pathlib.Path(p).read_text(encoding="utf-8") for p in sys.argv[1:3])
    problems = check(page, claims_md)
    for p in problems:
        print(f"error: {p}")
    print(f"{len(states(page))} states, {len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
