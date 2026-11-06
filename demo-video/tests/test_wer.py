"""Tests for scripts/wer.py: python3 -m unittest discover demo-video/tests"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
from wer import line_wer, tokens, wer  # noqa: E402


class WerTest(unittest.TestCase):
    def test_numbers_in_words_and_digits_match(self):
        self.assertEqual(line_wer(["Three hundred and twelve rows reached the server."], "312 rows reached the server.", "en"), 0)
        self.assertEqual(line_wer(["Сервер принял триста двенадцать запросов."], "Сервер принял 312 запросов.", "ru"), 0)

    def test_case_forms_ordinals_and_currency_match_digits(self):
        for ref, heard, lang in [
            ("в тысяче случаев", "в 1000 случаев", "ru"), ("в одном файле", "в 1 файле", "ru"),
            ("с тридцатью строками", "с 30 строками", "ru"), ("двадцать пятого марта", "25 марта", "ru"),
            ("в пятистах метрах", "в 500 метрах", "ru"), ("шестой этаж", "6-й этаж", "ru"),
            ("the twenty-fifth of May", "the 25th of May", "en"), ("a hundred dollars", "$100", "en"),
        ]:
            self.assertEqual(line_wer([ref], heard, lang), 0, ref)

    def test_typographic_apostrophes_and_number_joiners(self):
        for ref, heard, lang in [
            ("Don’t close the window.", "Don't close the window.", "en"),
            ("between ten and twenty requests", "between 10 and 20 requests", "en"),
            ("one and a half minutes", "1.5 minutes", "en"), ("three point two", "3.2", "en"),
            ("три точка два", "3.2", "ru"),
        ]:
            self.assertEqual(line_wer([ref], heard, lang), 0, ref)
        self.assertEqual(tokens("a cat and a dog", "en"), ["a", "cat", "and", "a", "dog"])
        self.assertEqual(line_wer(["Click ‘Save’ to keep the changes."], "Click Save to keep the changes.", "en"), 0)
        self.assertEqual(line_wer(["Click Save to keep the changes."], "Click 'Save' to keep the changes.", "en"), 0)
        self.assertEqual(line_wer(["Нажмите ‘Сохранить’."], "Нажмите «Сохранить».", "ru"), 0)

    def test_english_homophones_match(self):
        self.assertEqual(line_wer(["Today: why work waits in line."], "Today, why work weights in line?", "en"), 0)
        self.assertEqual(line_wer(["What a message queue does."], "What a message cue does.", "en"), 0)
        self.assertGreater(line_wer(["The worker takes it out."], "The walker takes it out.", "en"), 0)

    def test_words_that_only_look_like_numbers_stay(self):
        self.assertEqual(tokens("пятно семья сотрудник", "ru"), ["пятно", "семья", "сотрудник"])

    def test_and_outside_a_number_stays(self):
        self.assertEqual(tokens("bread and butter", "en"), ["bread", "and", "butter"])

    def test_latin_dropped_in_russian_only(self):
        # The voice reads the respelling; the shown text keeps the Latin name, which drops out.
        self.assertEqual(line_wer(["Сервер энджин-икс упал.", "Сервер nginx упал."], "Сервер nginx упал.", "ru"), 0)
        self.assertGreater(line_wer(["The nginx server fell."], "The server fell.", "en"), 0)

    def test_latin_word_in_russian_matches_any_spelling(self):
        self.assertEqual(line_wer(["Нажмите кнопку OK, чтобы сохранить изменения."], "Нажмите кнопку ОК, чтобы сохранить изменения.", "ru"), 0)
        self.assertEqual(line_wer(["Ссылка придет на email."], "Ссылка придет на имейл.", "ru"), 0)
        self.assertEqual(line_wer(["Ссылка придет на email."], "Ссылка придет на email.", "ru"), 0)
        self.assertGreater(line_wer(["Ссылка придет на email."], "Ссылка уйдет на имейл.", "ru"), 0)

    def test_yo_and_case_do_not_count(self):
        self.assertEqual(line_wer(["Ещё одна тёмная тема"], "еще одна темная тема", "ru"), 0)

    def test_smallest_wer_over_references_wins(self):
        self.assertEqual(line_wer(["Open engine-x now", "Open nginx now"], "Open nginx now", "en"), 0)

    def test_wer_counts_substitutions_deletions_insertions(self):
        self.assertAlmostEqual(wer("a b c d".split(), "a x c".split()), 0.5)
        self.assertEqual(wer([], []), 0.0)
        self.assertEqual(wer([], ["x"]), 1.0)


if __name__ == "__main__":
    unittest.main()
