"""Word error rate between a voice line and what Whisper heard, for the take check.

    from wer import line_wer
    miss = line_wer(["the say text", "the shown text"], heard, "ru")

WER = (substitutions + deletions + insertions) / words in the reference. Before the count, both
strings lose their numbers in both forms: Whisper writes "312" where the voice said "three hundred
and twelve", so a correct take would otherwise fail. The check therefore does not hear numbers; the user
does. In Russian a Latin word in the line stands for any one heard word, or none: Whisper writes
OK as ОК and email as имейл. The smallest WER over the given references wins, so a line can pass on
`say` or on `text`.
"""
import re

# Number words that Whisper writes as digits: cardinals, ordinals and currency words. English lists
# the words; Russian lists the irregular forms and matches the regular ones by stem and ending below.
NUMBER_WORDS = {
    "en": set("""zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen
        fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty
        ninety hundred hundreds thousand thousands million millions billion billions percent
        first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth
        fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth thirtieth fortieth
        fiftieth sixtieth seventieth eightieth ninetieth hundredth thousandth millionth
        dollar dollars euro euros pound pounds cent cents""".split()),
    "ru": set("""ноль нуль нуля нулю нолем нулем ноле нуле
        один одна одно одни одного одной одному одним одними одну одних одном
        два две двух двум двумя три трех трем тремя четыре четырех четырем четырьмя
        сорок сорока девяносто девяноста сто ста стам стами стах сотня сотни сотню сотен сотнями
        двести двухсот двумстам двумястами двухстах триста трехсот тремстам тремястами трехстах
        четыреста четырехсот четыремстам четырьмястами четырехстах полтора полторы полутора
        процент процента проценту процентов процентами процентах евро
        доллар доллара доллару долларов долларами рубль рубля рублю рублей рублями""".split()),
}
_RU_NUMBER = [re.compile(p) for p in (
    # пять, пяти, пятью ... тридцать, тридцати, тридцатью
    r"^(пят|шест|сем|восем|восьм|девят|десят|одиннадцат|двенадцат|тринадцат|четырнадцат|пятнадцат|"
    r"шестнадцат|семнадцат|восемнадцат|девятнадцат|двадцат|тридцат)(ь|и|ью)$",
    r"^(пят|шест|сем|восем)ьдесят$|^(пятидесят|шестидесят|семидесят|восьмидесят)(и|ью)$",
    # пятьсот, пятисот, пятистам, пятьюстами, пятистах ... девятьсот
    r"^(пят|шест|сем|восем|восьм|девят)(ь|и|ью)(сот|стам|стами|стах)$",
    r"^(тысяч|миллион|миллиард)(а|и|у|е|ей|ам|ами|ах|ов|ом|ью)?$",
    # Ordinals in every gender, number and case: первый, пятого, двадцатую, сотых ...
    r"^(перв|втор|трет|четверт|пят|шест|седьм|восьм|девят|десят|одиннадцат|двенадцат|тринадцат|"
    r"четырнадцат|пятнадцат|шестнадцат|семнадцат|восемнадцат|девятнадцат|двадцат|тридцат|сороков|"
    r"пятидесят|шестидесят|семидесят|восьмидесят|девяност|сот|двухсот|трехсот|четырехсот|пятисот|"
    r"шестисот|семисот|восьмисот|девятисот|тысячн|миллионн)(ый|ой|ий|ая|ое|ые|ого|ому|ым|ом|ую|ых|ыми|"
    r"ья|ье|ьи|ьего|ьему|ьим|ьем|ьей|ью|ьих|ьими|ей|его|ему|им|ем|ее|юю|яя)$",
)]


# The ending Whisper writes after a digit: 6-й, 25-го, 1st, 3rd.
DIGIT_SUFFIXES = {"й", "я", "е", "го", "му", "м", "х", "ми", "ый", "ой", "ая", "ое", "ые", "th", "st", "nd", "rd"}


def is_number(word, lang):
    if any(c.isdigit() for c in word) or word in NUMBER_WORDS.get(lang, ()):
        return True
    return lang == "ru" and any(p.match(word) for p in _RU_NUMBER)


# Words that join the parts of a number: "ten and twenty", "one and a half", "three point two".
# Whisper writes such a number in digits, so a joiner next to a number drops out on both sides.
JOINERS = {"en": {"and", "a", "point", "half", "quarter"},
           "ru": {"и", "точка", "запятая", "целых", "десятых", "половина", "половиной"}}


ANY = "\0"  # a reference word that matches any one heard word, or nothing


def tokens(text, lang):
    # Typographic apostrophes: the line may say "don’t", Whisper writes "don't".
    text = re.sub(r"[\u2018\u2019\u02bc]", "'", text.lower().replace("ё", "е"))
    # An apostrophe at a word's edge is a quote mark: 'Save' is Save.
    words = [w.strip("'") for w in re.findall(r"[\w']+", text) if w.strip("'")]
    number = [is_number(w, lang) or (w in DIGIT_SUFFIXES and i > 0 and words[i - 1].isdigit()) for i, w in enumerate(words)]
    joiner = [w in JOINERS.get(lang, ()) for w in words]

    def near_number(i, step):
        j = i + step
        while 0 <= j < len(words) and joiner[j] and not number[j]:
            j += step
        return 0 <= j < len(words) and number[j]

    out = []
    for i, w in enumerate(words):
        if number[i]:
            continue
        if joiner[i] and (near_number(i, -1) or near_number(i, 1)):
            continue
        if lang == "ru" and re.fullmatch(r"[a-z']+", w):
            # Whisper writes a Latin term in a Russian line either way: OK or ОК, email or имейл.
            # It stands for any one heard word, or for none.
            out.append(ANY)
            continue
        out.append(w)
    return out


def sound(word):
    """A rough English sound key, after Metaphone: queue and cue, waits and weights, there and their
    get one key. Whisper picks the spelling of a homophone from context and is often wrong, so a
    correct take would fail on it. Two different words can share a key too (cat, kit): the check
    misses a swapped vowel, which a voice model rarely produces."""
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return word
    for a, b in (("kn", "n"), ("gn", "n"), ("pn", "n"), ("wr", "r"), ("wh", "w"), ("x", "s")):
        if w.startswith(a):
            w = b + w[len(a):]
            break
    for a, b in (("tch", "x"), ("sch", "sk"), ("ph", "f"), ("gh", ""), ("ck", "k"), ("sh", "x"), ("ch", "x"),
                 ("th", "0"), ("dg", "j"), ("qu", "k"), ("q", "k"), ("x", "ks"), ("v", "f"), ("z", "s")):
        w = w.replace(a, b)
    w = re.sub(r"c(?=[eiy])", "s", w).replace("c", "k")
    w = re.sub(r"g(?=[eiy])", "j", w)
    head, tail = w[0], re.sub(r"[aeiouyhw]", "", w[1:])
    key = re.sub(r"(.)\1+", r"\1", (head if head not in "aeiouy" else "a") + tail)
    return key


def same(r, h, lang):
    return r == h or (lang == "en" and sound(r) == sound(h))


def wer(ref, hyp, lang=""):
    """Word-level Levenshtein distance divided by the reference length."""
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        free = r == ANY
        cur = [prev[0] + (0 if free else 1)] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + (0 if free else 1), cur[j - 1] + 1, prev[j - 1] + (0 if free or same(r, h, lang) else 1))
        prev = cur
    return prev[-1] / len(ref)


def line_wer(references, heard, lang):
    """The smallest WER of what Whisper heard against any of the references."""
    hyp = [w for w in tokens(heard, lang) if w != ANY]
    return min(wer(tokens(r, lang), hyp, lang) for r in references if r)


if __name__ == "__main__":
    # python3 wer.py --has-number <lang> reads a JSON list of phrases on stdin and prints, for each,
    # whether it holds a number in either form. slides.mjs refuses such an anchor.
    import json
    import sys
    if sys.argv[1:2] != ["--has-number"] or len(sys.argv) != 3:
        sys.exit("usage: wer.py --has-number <lang> < phrases.json")
    lang = sys.argv[2]
    phrases = json.load(sys.stdin)
    words = [re.findall(r"[\w']+", s.lower().replace("ё", "е")) for s in phrases]
    print(json.dumps([any(is_number(w.strip("'"), lang) for w in ws) for ws in words]))
