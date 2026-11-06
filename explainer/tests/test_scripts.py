"""Tests for the scripts in scripts/: python3 -m unittest discover explainer/tests"""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
from build_deck import anchors, apply, lexicon  # noqa: E402
from check_slides import check, claim_values, unclaimed  # noqa: E402
from lint_script import lint, parse  # noqa: E402

CLAIMS = """| id | claim | source | values |
| --- | --- | --- | --- |
| c1 | Intake is decoupled | https://example.org/a | |
| c2 | Peak was 1,200 a minute | https://example.org/b | 1,200; March 2025 |
"""


def script(*paragraphs, lang="en"):
    return f"# Title\nlang: {lang}\n\n## One\n\n" + "\n\n".join(paragraphs) + "\n"


CLAIMS_LOAD = "| id | claim | source | values |\n| --- | --- | --- | --- |\n"

class LintTest(unittest.TestCase):
    def errors(self, *paragraphs, claims=CLAIMS, lang="en"):
        return lint(script(*paragraphs, lang=lang), claims)["errors"]

    def test_clean_script_passes(self):
        self.assertEqual(self.errors("[host] A queue absorbs a spike [c1]. Peak was 1,200 a minute [c2]."), [])

    def test_long_sentence(self):
        long = "[host] " + " ".join(["word"] * 21) + "."
        self.assertIn("21 words, more than 20", self.errors(long)[0])

    def test_stop_phrase_in_each_language(self):
        self.assertIn("stop phrase", self.errors("[host] Let's dive in and see the queue.")[0])
        ru = (SCRIPTS.parent / "assets" / "stop-phrases.ru.txt").read_text(encoding="utf-8")
        phrase = next(s for s in ru.splitlines() if s.strip() and not s.startswith("#"))
        self.assertIn("stop phrase", self.errors(f"[host] {phrase.capitalize()} очередь.", lang="ru")[0])

    def test_long_quotation(self):
        quote = '"' + " ".join(["said"] * 26) + '"'
        errors = self.errors(f"[host] The author wrote {quote} once.")
        self.assertTrue(any("quotation of 26 words" in e for e in errors), errors)

    def test_unknown_mark_and_missing_source(self):
        self.assertIn("[c9] has no row", self.errors("[host] A fact [c9].")[0])
        claims = CLAIMS + "| c3 | No source | | |\n"
        self.assertIn("c3 has no source", self.errors("[host] Fine [c1].", claims=claims)[0])

    def test_value_without_its_mark(self):
        errors = self.errors("[host] The shop took 1,200 orders a minute.")
        self.assertIn("holds '1,200' without a mark of a claim that rests on it: [c2]", errors[0])
        # The value matches as a whole token, so 21,200 is not 1,200.
        self.assertEqual(self.errors("[host] The shop took 21,200 orders [c1]."), [])

    def test_a_value_inside_a_hyphenated_word_is_no_match(self):
        # "TID" is part of "EP-TID-01", not a mention of the prefix on its own.
        claims = CLAIMS + "| c3 | The prefix | manifest | TID |\n"
        self.assertEqual(self.errors("[host] The epic EP-TID-01 absorbs a spike [c1].", claims=claims), [])
        self.assertEqual(len(self.errors("[host] The prefix is TID, and a queue absorbs a spike [c1].", claims=claims)), 1)

    def test_a_mark_after_a_closing_quote_stays_with_its_sentence(self):
        self.assertEqual(self.errors('[host] The report says "peak was 1,200 a minute." [c2] Then it stops.'), [])

    def test_expert_share_is_an_error_and_length_a_warning(self):
        text = script("[host] " + " ".join(["host"] * 10) + ".", "[expert] " + " ".join(["expert"] * 10) + ".")
        r = lint(text, CLAIMS, target_minutes=5)
        self.assertTrue(any("expert speaks 50%" in e for e in r["errors"]), r["errors"])
        self.assertTrue(any("not 5" in w for w in r["warnings"]), r["warnings"])
        self.assertIn("host and expert", lint(script("[host] One.", "[guest] Two."), CLAIMS)["errors"][0])

    def test_a_shared_value_needs_a_mark_of_any_claim_that_rests_on_it(self):
        claims = CLAIMS + "| c3 | Launch year | https://example.org/c | March 2025 |\n"
        self.assertEqual(self.errors("[host] It shipped in March 2025 [c3].", claims=claims), [])
        self.assertIn("[c2], [c3]", self.errors("[host] It shipped in March 2025.", claims=claims)[0])

    def test_quotation_spanning_sentences_and_closing_quotes(self):
        ten = " ".join(["word"] * 9)
        errors = self.errors(f"[host] The author wrote: «{ten} one. {ten} two. {ten} three.» Then stopped [c1].", lang="ru")
        self.assertTrue(any("quotation of 30 words" in e for e in errors), errors)
        fifteen = " ".join(["word"] * 15)
        self.assertEqual(self.errors(f"[host] He asked: «Why bother?» {fifteen} [c1]."), [])

    def test_one_lowercase_word_as_a_value_is_a_warning(self):
        # "integrity" matches any sentence that says the word; "March 2025" and "1,200" are specific.
        claims = CLAIMS + "| c3 | The audit checks integrity | https://example.org/c | integrity; read-only; fourth; FR-12 |\n"
        r = lint(script("[host] A queue absorbs a spike [c1]."), claims)
        self.assertEqual(r["errors"], [])
        self.assertEqual([w.split("'")[1] for w in r["warnings"]], ["integrity", "read-only", "fourth"], r["warnings"])
        self.assertIn("c3 value 'integrity' is one lowercase word", r["warnings"][0])

    def test_a_lowercase_russian_word_as_a_value_is_a_warning(self):
        claims = CLAIMS + "| c3 | Аудит | https://example.org/c | целостность; Москва; Москве |\n"
        r = lint(script("[host] Очередь гасит пик [c1].", lang="ru"), claims)
        self.assertEqual([w.split("'")[1] for w in r["warnings"]], ["целостность"], r["warnings"])

    def test_a_number_in_words_as_a_value_is_no_warning(self):
        claims = CLAIMS + ("| c3 | The engine has 48 lines | https://example.org/c | "
                           "forty-eight; seventeen; сорок; пятидесяти; тысячи; трёх |\n")
        self.assertEqual(lint(script("[host] A queue absorbs a spike [c1]."), claims)["warnings"], [])
        self.assertEqual(lint(script("[host] A queue absorbs a spike [c1]."), CLAIMS)["warnings"], [])

    def test_parse_rejects_text_it_cannot_place(self):
        for text in ["# T\n\n## One\n\nNo speaker here.\n", "# T\n\nNote: stray line.\n\n## One\n\n[host] Fine.\n"]:
            with self.assertRaises(ValueError):
                parse(text)
        # A line inside a paragraph that looks like a key stays text.
        _, lang, chapters = parse("# T\nlang: ru\n\n## One\n\n[host] First line\nlang: en second line.\n")
        self.assertEqual((lang, chapters[0][1][0][1]), ("ru", "First line lang: en second line."))
        # A new speaker on the next line opens a new paragraph.
        _, _, chapters = parse("# T\n\n## One\n\n[host] Why?\n[expert] Because.\n")
        self.assertEqual(chapters[0][1], [("host", "Why?"), ("expert", "Because.")])
        # A claim mark at a line start stays in its paragraph.
        _, _, chapters = parse("# T\n\n## One\n\n[host] A fact holds here\n[c3]. Next sentence.\n")
        self.assertEqual(chapters[0][1], [("host", "A fact holds here [c3]. Next sentence.")])

    def test_cli_exit_code(self):
        fixture = SCRIPTS.parent / "evals" / "fixtures" / "lint"
        r = subprocess.run([sys.executable, str(SCRIPTS / "lint_script.py"), str(fixture / "script.md"), str(fixture / "claims.md")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("holds '1,200' without a mark of a claim that rests on it: [c2]", r.stdout)


def page(*sections):
    return "<!doctype html><html><head><style>.x::before { content: '99'; }</style></head><body>" + "".join(sections) + "</body></html>"


class CheckSlidesTest(unittest.TestCase):
    CLAIMS = CLAIMS + "| c3 | FR-12 names EP-3 | https://example.org/c | FR-12; EP-3; 40 s; 12.5 |\n"

    def unclaimed(self, text):
        return unclaimed(text, claim_values(self.CLAIMS))

    def test_every_digit_on_a_slide_is_a_claim_value(self):
        self.assertEqual(self.unclaimed("FR-12 belongs to EP-3, peak 1,200 in March 2025, median 40 s"), [])
        self.assertEqual(self.unclaimed("FR-13 took 12 days, 40.5 s, 2026"), ["fr-13", "12", "40.5", "2026"])

    def test_a_part_of_a_value_is_no_match(self):
        self.assertEqual(self.unclaimed("12 and 5 and FR-1 and 200"), ["12", "5", "fr-1", "200"])

    def test_a_figure_in_the_claim_text_counts(self):
        # The script says "forty-eight" and lists that as the value; the claim holds the digits.
        claims = CLAIMS + "| c3 | The engine has 48 lines | https://example.org/c | forty-eight |\n"
        self.assertEqual(unclaimed("48 lines", claim_values(claims)), [])

    def test_states_code_ticks_and_styles(self):
        deck = page('<section class="slide diagram" id="a"><style>.box { width: 99px; }</style><h2>Peak</h2><div class="box">1,200<small>a minute</small></div></section>',
                    '<section class="slide chart" id="b"><svg><g class="tick"><text>0</text><text>2,000</text></g>'
                    '<text class="value">7</text></svg></section>',
                    '<section class="slide code" id="c"><pre>workers: 4</pre></section>',
                    '<section class="slide artefact" id="e"><div class="tree">retries: 3</div></section>',
                    '<section class="slide diagram" id="d"><ul><li>4<li>12</ul></section>')
        # An unclosed <li> still ends its text; "12" is only a part of FR-12 and 12.5.
        self.assertEqual(check(deck, self.CLAIMS), ["b: '7' is no value in claims.md", "d: '4' is no value in claims.md",
                                                    "d: '12' is no value in claims.md"])

    def test_text_only_states_above_30_percent(self):
        deck = page(*[f'<section class="slide {k}" id="s{i}">Text</section>' for i, k in enumerate(["list", "thesis", "diagram", "steps"])])
        self.assertIn("2 of 4 states are list or thesis", check(deck, CLAIMS)[0])
        deck = page(*[f'<section class="slide {k}" id="s{i}">Text</section>' for i, k in enumerate(["list", "hub", "diagram", "steps"])])
        self.assertEqual(check(deck, CLAIMS), [])

    def test_cli_exit_code(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "slides.html").write_text(page('<section class="slide title" id="t">As of 2026-11-05</section>'), encoding="utf-8")
            (d / "claims.md").write_text(CLAIMS, encoding="utf-8")
            r = subprocess.run([sys.executable, str(SCRIPTS / "check_slides.py"), str(d / "slides.html"), str(d / "claims.md")],
                               capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("t: '2026-11-05' is no value in claims.md", r.stdout)


class BuildDeckTest(unittest.TestCase):
    def test_lexicon_longest_form_first_and_whole_words(self):
        pairs = lexicon("| written | say |\n| --- | --- |\n| `RAG` | rag |\n| Claude | Klod |\n| Claude Code | Klod Kod |\n")
        self.assertEqual(pairs[0][0], "Claude Code")
        self.assertEqual(apply("Claude Code and Claude read RAG, not RAGS.", pairs), "Klod Kod and Klod read rag, not RAGS.")

    def test_deck_paragraphs_from_script(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "script.md").write_text(script("[host] RAG finds passages [c1].", "[expert] Then it answers [c1]?") +
                                         "\n## Two\n\n[host] Done.\n", encoding="utf-8")
            (d / "lexicon.en.md").write_text("| written | say |\n| --- | --- |\n| RAG | rag |\n", encoding="utf-8")
            (d / "slides.json").write_text(json.dumps({"html": "slides.html", "states": [{"id": "s1", "anchor": "RAG finds"}]}), encoding="utf-8")
            subprocess.run([sys.executable, str(SCRIPTS / "build_deck.py"), str(d / "script.md"), str(d / "lexicon.en.md"),
                            str(d / "slides.json")], check=True, capture_output=True)
            deck = json.loads((d / "slides.json").read_text(encoding="utf-8"))
        self.assertEqual(deck["states"], [{"id": "s1", "anchor": "rag finds", "anchorText": "RAG finds", "anchorSaid": "rag finds"}])
        self.assertEqual((deck["lang"], deck["version"]), ("en", 1))
        first, second, third = deck["paragraphs"]
        self.assertEqual(first, {"id": "c01p01", "chapter": "One", "speaker": "host",
                                 "text": "RAG finds passages.", "say": "rag finds passages."})
        self.assertEqual((second["id"], second["speaker"], second["text"], "say" in second), ("c01p02", "expert", "Then it answers?", False))
        self.assertEqual((third["id"], third["chapter"]), ("c02p01", "Two"))

    def test_anchors_survive_a_second_run_and_a_hand_edit(self):
        pairs = lexicon("| written | say |\n| --- | --- |\n| K8s | Kubernetes |\n| Kubernetes | koo ber net eez |\n")
        states = [{"id": "s", "anchor": "K8s at scale"}]
        anchors(states, pairs)
        anchors(states, pairs)
        self.assertEqual(states[0]["anchor"], "Kubernetes at scale")
        states[0]["anchor"] = "clusters at scale"
        anchors(states, pairs)
        self.assertEqual((states[0]["anchor"], states[0]["anchorText"]), ("clusters at scale", "clusters at scale"))
        # A lexicon change between runs respells the anchor from its written form.
        states = [{"id": "s", "anchor": "nginx at scale"}]
        anchors(states, [("nginx", "engine ex")])
        anchors(states, [("nginx", "engine x")])
        self.assertEqual((states[0]["anchor"], states[0]["anchorText"]), ("engine x at scale", "nginx at scale"))
        # An anchor removed by hand stays removed.
        del states[0]["anchor"]
        anchors(states, [("nginx", "engine x")])
        self.assertEqual(states[0], {"id": "s"})


class LoadTest(unittest.TestCase):
    """The viewer's load: names, acronyms and identifiers found in the text, coined terms from the outline."""

    def chapter(self, *paragraphs):
        return "# T\nlang: en\n## One\n\n" + "\n\n".join(paragraphs) + "\n"

    def run_load(self, text, **kw):
        return lint(text, CLAIMS_LOAD, **kw)

    def test_a_full_name_and_its_short_form_count_once(self):
        r = self.run_load(self.chapter("[host] Then Ivan Trifonov met Ilya. Later Ivan agreed, and Ilya left."))
        self.assertEqual(r["load"][0]["terms"], ["Ivan Trifonov", "Ilya"])

    def test_identifiers_acronyms_and_a_date_are_counted_once_each(self):
        r = self.run_load(self.chapter("[host] Then FR-1 names EP-TID-01, and the PRD holds it, since 4 November 2026."))
        self.assertEqual(r["load"][0]["terms"], ["FR-1", "EP-TID-01", "PRD"])
        self.assertEqual(r["load"][0]["figures"], ["4 November 2026"])

    def test_a_verb_is_no_month_and_a_known_acronym_is_free(self):
        r = self.run_load(self.chapter("[host] Then the CI may fail on the API."))
        self.assertEqual((r["load"][0]["terms"], r["load"][0]["figures"]), ([], []))

    def test_a_chapter_over_its_budget_is_an_error(self):
        r = self.run_load(self.chapter("[host] Then Anna, Boris, Clara, Dmitri and Elena met."))
        self.assertTrue(any("5 new terms and names, more than 4" in e for e in r["errors"]), r["errors"])

    def test_outline_terms_count_toward_the_budget(self):
        outline = "## One\n- New terms: gate, spoke, fold plan\n"
        r = self.run_load(self.chapter("[host] Then Anna and Boris met."), outline_text=outline)
        self.assertEqual(r["load"][0]["terms"], ["gate", "spoke", "fold plan", "Anna", "Boris"])
        self.assertTrue(any("more than 4" in e for e in r["errors"]))

    def test_small_spoken_numbers_and_ordinals_are_figures(self):
        r = self.run_load(self.chapter("[host] Then teams kept it three months, until the sixth of November."))
        self.assertEqual(r["load"][0]["figures"], ["three", "sixth of November"])

    def test_a_prefix_beside_its_identifier_counts_once(self):
        r = self.run_load(self.chapter("[host] Then FR-1 fails. Every FR names an epic."))
        self.assertEqual(r["load"][0]["terms"], ["FR-1"])

    def test_a_hypothetical_needs_no_mark(self):
        claims = CLAIMS_LOAD + "| c9 | FR-7 names its epic | prd | FR-7 |\n"
        r = lint(self.chapter("[host] Say someone deletes the tag from FR-7. The check fails [c9]."), claims)
        self.assertFalse(any("without a mark" in e for e in r["errors"]), r["errors"])

    def test_a_dense_paragraph_is_a_warning(self):
        r = self.run_load(self.chapter("[host] Then Anna met Boris in 2024, and FR-9 had 40 rows."))
        self.assertTrue(any("a paragraph brings 5 new terms, names and figures" in w for w in r["warnings"]), r["warnings"])

    def test_the_video_budget_scales_with_the_target(self):
        r = self.run_load(self.chapter("[host] Then FR-1 met FR-2. Next FR-3 met FR-4."), target_minutes=2)
        self.assertTrue(any("4 new terms and names in the video, more than 3 for 2 minutes" in e for e in r["errors"]), r["errors"])


if __name__ == "__main__":
    unittest.main()
