#!/usr/bin/env python3
"""Checks an explainer script against its rules and its claims, and estimates its length.

    lint_script.py script.md claims.md [--target-minutes 12] [--json]

script.md:
    # Title
    lang: ru
    ## Chapter title
    [host] A paragraph, one voice line. A claim carries its mark [c3].

    [expert] The next paragraph.

claims.md holds a Markdown table whose columns include id, claim, source and values: the names,
numbers and dates the claim rests on, separated by ";".

Errors, which stop the stage:
- a line outside a paragraph, or a paragraph without a [speaker];
- a sentence longer than 20 words;
- a stop phrase from assets/stop-phrases.<lang>.txt;
- a quotation longer than 25 words, counted over the whole paragraph;
- a mark [cN] with no row in claims.md, or a claim row with no source;
- a sentence that holds a value of a claim but no mark of any claim that rests on that value;
- in a dialogue, an `expert` who speaks outside 60-80% of the words.
The value match is literal: list in `values` every form the script uses, such as each case form of a
Russian name.

Warnings:
- a word count outside the range for the target length, at the language's pace;
- a claim value that is one lowercase word, such as "integrity" or "целостность": the literal match
  finds it in sentences that do not rest on the claim. A value is a name, a number or a date; give a
  more specific one, or none. A number in words, such as "forty-eight" or "сорок", is a number.

Exit code 1 on errors. The marks are stripped before the text reaches demo-video.
"""
import argparse
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
WPM = {"en": 140, "ru": 120}  # the language's default pace; the chosen voice reads faster or slower
PAUSE = {"paragraph": 0.7, "chapter": 1.5}  # demo-video's default gaps, in seconds
MARK = re.compile(r"\[c(\d+)\]")
# One lowercase word in any script, hyphens and apostrophes inside it allowed: "integrity", "read-only".
COMMON_WORD = re.compile(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*")
# Cardinals in words, which match only where the figure is said. A copy of the cardinal part of
# NUMBER_WORDS and _RU_NUMBER in demo-video/scripts/wer.py, which owns the full list: this script runs
# without demo-video. Ordinals stay out on purpose: "fourth" is said far more often than it is a value.
CARDINALS = {
    "en": set("""zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen
        fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety
        hundred thousand million billion""".split()),
    "ru": set("""ноль нуль один одна одно одного одной одному одним одну одном два две двух двум двумя
        три трех трем тремя четыре четырех четырем четырьмя сорок сорока девяносто девяноста
        сто ста двести двухсот триста трехсот четыреста четырехсот полтора полторы полутора""".split()),
}
RU_CARDINAL = re.compile(
    r"(пят|шест|сем|восем|восьм|девят|десят|одиннадцат|двенадцат|тринадцат|четырнадцат|пятнадцат|"
    r"шестнадцат|семнадцат|восемнадцат|девятнадцат|двадцат|тридцат)(ь|и|ью)"
    r"|(пят|шест|сем|восем)ьдесят|(пятидесят|шестидесят|семидесят|восьмидесят)(и|ью)"
    r"|(пят|шест|сем|восем|восьм|девят)(ь|и|ью)(сот|стам|стами|стах)"
    r"|(тысяч|миллион|миллиард)(а|и|у|е|ей|ам|ами|ах|ов|ом|ью)?")


def is_cardinal(word):
    word = word.replace("ё", "е")
    return word in CARDINALS["en"] or word in CARDINALS["ru"] or bool(RU_CARDINAL.fullmatch(word))


def vague_value(value):
    """True for a value that is one lowercase word and not a number in words."""
    return bool(COMMON_WORD.fullmatch(value)) and value == value.lower() and value != value.upper() \
        and not all(is_cardinal(part) for part in value.split("-"))


def parse(text):
    """Returns (title, lang, chapters): chapters are [(title, [(speaker, paragraph)])]. Raises ValueError
    on text it cannot place, so nothing is dropped silently."""
    title, lang, chapters = "", "en", []
    block = []

    def flush():
        if block:
            m = re.match(r"\[(\w+)\]\s*(.*)", " ".join(block), re.S)
            if not m:
                raise ValueError(f"paragraph without a [speaker]: {' '.join(block)[:60]}")
            if not chapters:
                raise ValueError("a paragraph before the first ## chapter")
            chapters[-1][1].append((m.group(1), m.group(2).strip()))
            block.clear()

    for line in text.splitlines():
        if line.startswith("# ") and not chapters:
            title = line[2:].strip()
        elif re.match(r"lang:\s*\w+\s*$", line) and not chapters and not block:
            lang = re.match(r"lang:\s*(\w+)", line).group(1)
        elif line.startswith("## "):
            flush()
            chapters.append((line[3:].strip(), []))
        elif not line.strip():
            flush()
        elif not chapters:
            raise ValueError(f"text before the first ## chapter: {line[:60]}")
        else:
            if block and re.match(r"\[(?!c\d+\])\w+\]", line.strip()):
                flush()  # a new speaker opens a new paragraph, even without a blank line
            block.append(line.strip())
    flush()
    return title, lang, chapters


def claims(text):
    """Rows of the first Markdown table with an id column: {id: {claim, source, values}}."""
    rows, head = {}, None
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if head is None:
            head = [c.lower() for c in cells]
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        row = dict(zip(head, cells))
        cid = row.get("id", "").lstrip("c")
        if cid.isdigit():
            rows[int(cid)] = {"claim": row.get("claim", ""), "source": row.get("source", ""),
                              "values": [v.strip() for v in row.get("values", "").split(";") if v.strip()]}
    return rows


def sentences(paragraph):
    # A sentence may end inside a closing quote or bracket: «Why?» Then the next one starts. A claim mark
    # after the closing quote (do.» [c5]) belongs to the sentence before it, so no split happens there.
    return [s for s in re.split(r"(?<=[.!?…])[»\"”)]*\s+(?!\[c\d+\])|(?<=[.!?…][»\"”)])\s+(?!\[c\d+\])", paragraph) if s.strip()]


QUOTE = re.compile(r"«([^»]+)»|\"([^\"]+)\"|“([^”]+)”")


def words(text):
    return re.findall(r"[\w'’-]+", MARK.sub("", text))


def lint(script, claims_text, target_minutes=None, outline_text=None, known=()):
    title, lang, chapters = parse(script)
    table = claims(claims_text)
    owners = {}  # a value -> the claims that rest on it
    for cid, row in table.items():
        for v in row["values"]:
            owners.setdefault(v.lower(), set()).add(cid)
    stops = [s.strip().lower() for s in (HERE.parent / "assets" / f"stop-phrases.{lang}.txt").read_text(encoding="utf-8").splitlines()
             if s.strip() and not s.startswith("#")]
    errors, warnings = [], []
    total, by_speaker, paragraphs = 0, {}, 0
    for ch, paras in chapters:
        for speaker, p in paras:
            paragraphs += 1
            n = len(words(p))
            total += n
            by_speaker[speaker] = by_speaker.get(speaker, 0) + n
            for q in QUOTE.findall(p):
                q = next(x for x in q if x)
                if len(words(q)) > 25:
                    errors.append(f"{ch}: a quotation of {len(words(q))} words, more than 25: {q[:40]}")
            for s in sentences(p):
                where = f"{ch}: {s[:50]}"
                if len(words(s)) > 20:
                    errors.append(f"{where}: {len(words(s))} words, more than 20")
                low = s.lower()
                for stop in stops:
                    if stop in low:
                        errors.append(f"{where}: stop phrase '{stop}'")
                marks = {int(m) for m in MARK.findall(s)}
                for m in marks:
                    if m not in table:
                        errors.append(f"{where}: [c{m}] has no row in claims.md")
                bare = MARK.sub("", s)
                # A hypothetical ("Say someone deletes FR-1.") runs a mechanism on the example; the fact it
                # rests on carries its mark in the next sentence (references/explaining.md).
                hypothetical = re.match(r"(Say|Suppose|Скажем|Допустим|Предположим)\b", bare.strip()) is not None
                for value, cids in owners.items():
                    if hypothetical or cids & marks or not re.search(rf"(?<![\w-]){re.escape(value)}(?![\w-])", bare, re.I):
                        continue
                    names = ", ".join(f"[c{c}]" for c in sorted(cids))
                    errors.append(f"{where}: holds '{value}' without a mark of a claim that rests on it: {names}")
    for cid, row in table.items():
        if not row["source"]:
            errors.append(f"claims.md: c{cid} has no source")
        warnings += [f"claims.md: c{cid} value '{v}' is one lowercase word and matches sentences that do not rest "
                     "on the claim; give a name, a number or a date, or no value" for v in row["values"] if vague_value(v)]
    if len(by_speaker) > 1:
        if set(by_speaker) != {"host", "expert"}:
            errors.append(f"a dialogue has the speakers host and expert, not {', '.join(sorted(by_speaker))}")
        else:
            share = by_speaker["expert"] / max(total, 1)
            if not 0.6 <= share <= 0.8:
                errors.append(f"the expert speaks {share:.0%} of the words, outside 60-80%")
    pauses = paragraphs * PAUSE["paragraph"] + len(chapters) * PAUSE["chapter"]
    minutes = (total / WPM.get(lang, 140)) + pauses / 60
    if target_minutes:
        if abs(minutes - target_minutes) > 0.2 * target_minutes:
            warnings.append(f"about {minutes:.1f} minutes at {WPM.get(lang, 140)} words a minute, not {target_minutes}")
    load_errors, load_counts, dense = load(chapters, target_minutes, outline_text, known)
    errors += load_errors
    warnings += dense
    return {"load": load_counts, "title": title, "lang": lang, "chapters": len(chapters), "paragraphs": paragraphs, "words": total,
            "minutes": round(minutes, 1), "errors": errors, "warnings": warnings}


# The viewer's load: what a chapter asks the viewer to keep. A name, an acronym or an identifier is found
# here; a coined term in plain words ("the gate") is not, so it comes from the outline's "New terms" line.
# Over budget, the viewer stops following: reviewers of three scripts scored load lowest of every axis.
# An English month is a name and starts with a capital, so "may" the verb is no date; a Russian one is lower case.
MONTHS = set("January February March April May June July August September October November December "
             "января февраля марта апреля мая июня июля августа сентября октября ноября декабря".split())
# "One" and "two" read as plain words ("one repository"); from three up, a spoken number is a figure to keep.
ORDINALS = set("third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth fifteenth "
               "sixteenth seventeenth eighteenth nineteenth twentieth thirtieth".split())
BIG_NUMBERS = set("three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty "
                  "fifty sixty seventy eighty ninety hundred thousand million billion".split())
KNOWN = {"CI", "ID", "IDs", "API", "APIs", "URL", "HTTP", "PR", "PRs", "AI", "OK", "I"}
# A capital that starts a quotation or follows a colon is no name.
FUNCTION_WORDS = set("The A An And But Or So Then If In On At To Of For With From By As It Its This That These Those "
                     "What Why How When Where Who Which Here There Each Every No Not Say Suppose Yes "
                     "И А Но Или Так Если В На К С По Это Этот Что Как Когда Где Кто".split())
CHAPTER_TERMS, CHAPTER_FIGURES, PARAGRAPH_ITEMS = 4, 3, 3
TOKEN = re.compile(r"[\w’'.,-]+")
CAPITAL = re.compile(r"[A-ZА-ЯЁ][a-zа-яё]")
ACRONYM = re.compile(r"[A-ZА-ЯЁ][A-ZА-ЯЁ0-9]*(?:-[A-ZА-ЯЁ0-9]+)+|[A-ZА-ЯЁ]{2,}s?")


def _bare(token):
    t = token.strip(".,'’-")
    return re.sub(r"['’]s$", "", t)


def _figure(t):
    low = t.lower()
    return bool(re.search(r"\d", t)) or t in MONTHS or low in BIG_NUMBERS or low in ORDINALS or (
        "-" in low and low.split("-")[0] in BIG_NUMBERS)


def outline_terms(outline_text):
    """The "New terms" line of each chapter in outline.md, in order: a list of term lists."""
    out = []
    for line in (outline_text or "").splitlines():
        m = re.match(r"\s*-\s*New terms:\s*(.*)", line)
        if m:
            text = m.group(1).strip().rstrip(".")
            out.append([] if text.lower().startswith(("none", "нет")) or not text else [t.strip() for t in text.split(",") if t.strip()])
    return out


def load(chapters, target_minutes=None, outline_text=None, known=()):
    """Errors for every chapter and for the video over the load budget, and the counts per chapter."""
    known = KNOWN | set(known)
    names = set()
    for _, paras in chapters:
        for _, p in paras:
            for s in sentences(MARK.sub("", p)):
                for t in [_bare(x) for x in TOKEN.findall(s)][1:]:
                    if CAPITAL.match(t) and t not in MONTHS and t not in FUNCTION_WORDS:
                        names.add(t)
    coined = outline_terms(outline_text)
    seen, errors, counts, dense = set(), [], [], []
    for i, (title, paras) in enumerate(chapters):
        terms, figures = [], []
        for term in coined[i] if i < len(coined) else []:
            if term.lower() not in seen:
                seen.add(term.lower())
                terms.append(term)
        for _, p in paras:
            before = len(terms) + len(figures)
            for s in sentences(MARK.sub("", p)):
                run_name, run_fig = [], []
                raw = TOKEN.findall(s) + [""]
                tokens = [_bare(x) for x in raw]
                for j, t in enumerate(tokens):
                    is_name = bool(t) and t not in known and (ACRONYM.fullmatch(t) is not None or t in names)
                    is_fig = bool(t) and not is_name and _figure(t)
                    # A run of names is one name ("Ivan Trifonov"); a comma or a stop between two names ends it.
                    if run_name and (not is_name or raw[j - 1][-1:] in ",.:;"):
                        key = " ".join(run_name)
                        # "Ivan" after "Ivan Trifonov" is the same person: a run whose every part is known adds nothing.
                        # "FR" beside "FR-1" is one idea: an identifier also marks its prefix as seen.
                        prefixes = [x.split("-")[0].lower() for x in run_name if "-" in x]
                        if key.lower() not in seen and not all(x.lower() in seen for x in run_name):
                            terms.append(key)
                        seen.update([key.lower()] + [x.lower() for x in run_name] + prefixes)
                        run_name = []
                    if is_name:
                        run_name.append(t)
                        continue
                    if is_fig or (run_fig and t.lower() in ("and", "of", "the")):
                        run_fig.append(t)
                    elif run_fig:
                        while run_fig and run_fig[-1].lower() in ("and", "of", "the"):
                            run_fig.pop()
                        key = " ".join(run_fig)
                        if key.lower() not in seen:
                            seen.add(key.lower())
                            figures.append(key)
                        run_fig = []
            # A paragraph is heard in one breath: more than 3 new items in it is the densest spot reviewers name.
            if len(terms) + len(figures) - before > PARAGRAPH_ITEMS:
                dense.append(f"{title}: a paragraph brings {len(terms) + len(figures) - before} new terms, names and figures, "
                             f"more than {PARAGRAPH_ITEMS}: {p[:40]}")
        counts.append({"chapter": title, "terms": terms, "figures": figures})
        if len(terms) > CHAPTER_TERMS:
            errors.append(f"{title}: {len(terms)} new terms and names, more than {CHAPTER_TERMS}: {', '.join(terms)}; "
                          "describe one instead of naming it, or move it to the chapter that needs it")
        if len(figures) > CHAPTER_FIGURES:
            errors.append(f"{title}: {len(figures)} new figures and dates, more than {CHAPTER_FIGURES}: "
                          f"{', '.join(figures)}; keep the ones the mechanism needs")
    if target_minutes:
        budget_terms, budget_figures = round(1.5 * target_minutes), round(target_minutes)
        n_terms = sum(len(c["terms"]) for c in counts)
        n_figures = sum(len(c["figures"]) for c in counts)
        if n_terms > budget_terms:
            errors.append(f"{n_terms} new terms and names in the video, more than {budget_terms} for "
                          f"{target_minutes:g} minutes")
        if n_figures > budget_figures:
            errors.append(f"{n_figures} new figures and dates in the video, more than {budget_figures} for "
                          f"{target_minutes:g} minutes")
    return errors, counts, dense


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script", type=pathlib.Path)
    ap.add_argument("claims", type=pathlib.Path)
    ap.add_argument("--target-minutes", type=float)
    ap.add_argument("--outline", type=pathlib.Path, help="outline.md, whose New terms lines count toward the load")
    ap.add_argument("--known", default="", help="comma-separated names and acronyms the viewer already knows")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = lint(a.script.read_text(encoding="utf-8"), a.claims.read_text(encoding="utf-8"), a.target_minutes,
                 a.outline.read_text(encoding="utf-8") if a.outline else None,
                 [k.strip() for k in a.known.split(",") if k.strip()])
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print(f"{r['title']}: {r['chapters']} chapters, {r['paragraphs']} paragraphs, {r['words']} words, about {r['minutes']} minutes")
        for e in r["errors"]:
            print(f"error: {e}")
        for w in r["warnings"]:
            print(f"warning: {w}")
    sys.exit(1 if r["errors"] else 0)


if __name__ == "__main__":
    main()
