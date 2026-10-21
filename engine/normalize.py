"""Flexible input: turns what the user types into (value, certainty).

  "yes", "haan", "probably", "not sure"      -> answer words (settings.json)
  "male", "tom", "billi"                       -> a parameter's own synonyms
  "102", "a hundred and two", "39.5 C"         -> numbers with units, converted
  "6 months", "half a year", "a day and a half"   and sorted into bands

All the words come from the knowledge base except English number words.
Anything that can't be understood raises AnswerError with a helpful message,
so nothing unvalidated ever reaches the engine.
"""

import difflib
import re

SMALL = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
         "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
         "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
         "eighteen": 18, "nineteen": 19}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
        "seventy": 70, "eighty": 80, "ninety": 90}
NUMBER_WORDS = SMALL.keys() | TENS.keys() | {"hundred"}
MAX_LENGTH = 200
MAX_TRIES = 2  # after this many answers we can't understand, UIs treat the question as "not sure"


class AnswerError(ValueError):
    pass


def clean(text):
    text = str(text).lower().replace("’", "'").replace("`", "'").strip()
    if text == "?":
        return text
    text = re.sub(r"[,!;:?()\"]+|\.(?!\d)", " ", text)  # keep decimal points: "102.5"
    return re.sub(r"\s+", " ", text).strip()


def tokens(text):
    """Split digits from letters: "102.5°f" -> ["102.5", "°f"], "6mo" -> ["6", "mo"]."""
    return re.findall(r"\d+(?:\.\d+)?|[^\s\d]+", text)


def parse_answer(kb, pid, text):
    """Return (value, certainty) for parameter pid, or raise AnswerError."""
    param = kb.params[pid]
    if text is None or not str(text).strip():
        raise AnswerError("Please type an answer, or \"not sure\".")
    if len(str(text)) > MAX_LENGTH:
        raise AnswerError("That answer is too long; please keep it short.")
    text = clean(text)

    # Longest phrase first, so "no idea" (not sure) wins over "no". On a tie the
    # question's own phrases win ("none" means yes to "passing little or no urine?").
    # "yes, a lot" and "not eating since yesterday" match by their start; a one-word
    # symptom phrase must match exactly, so "hot dog stand" is not a fever.
    phrases = sorted(_phrases(kb, param), key=lambda x: -len(x[0]))
    for phrase, result, prefix_ok in phrases:
        if text == phrase or (prefix_ok and text.startswith(phrase + " ")):
            return result
    # Spacing doesn't matter: "standup" = "stand up", "cantpee" = "cant pee".
    squeezed = text.replace(" ", "")
    for phrase, result, _ in phrases:
        if phrase.replace(" ", "") == squeezed:
            return result
    if param.get("number"):
        try:
            return _parse_number_answer(kb, param, text)
        except AnswerError:
            if _close_match(text, phrases) is None:
                raise
    # Small typos: "cant stnd up" ~ "cant stand up". Only for phrases of 5+ letters
    # and a close match, so short words like "no" are never guessed.
    found = _close_match(text, phrases)
    if found:
        return found
    raise AnswerError(f"Sorry, I didn't understand \"{text}\". {_examples(kb, param)}")


def not_sure(kb, pid):
    """The "not sure" answer for any question: it adds no evidence either way."""
    return kb.params[pid]["values"][0], 0.0


def _close_match(text, phrases):
    if len(text) < 5:
        return None
    candidates = {phrase: result for phrase, result, _ in phrases if len(phrase) >= 5}
    best = difflib.get_close_matches(text, list(candidates), n=1, cutoff=0.85)
    return candidates[best[0]] if best else None


def _phrases(kb, param):
    """Every phrase this question accepts: [(phrase, (value, certainty), prefix_ok)]."""
    pairs = []
    is_yes_no = param["values"] == ["yes", "no"]

    def own(phrase, result):
        phrase = clean(phrase)
        pairs.append((phrase, result, " " in phrase))

    for value in param["values"]:              # the question's own phrases first
        if not is_yes_no:
            own(value.replace("_", " "), (value, 1.0))
        if value in param["labels"]:
            own(param["labels"][value], (value, 1.0))
        for syn in param["synonyms"].get(value, []):
            phrase, certainty = (syn, 1.0) if isinstance(syn, str) else syn
            own(phrase, (value, certainty))
    for a in kb.settings["answers"].values():
        if is_yes_no:
            pairs += [(clean(w), (a["value"], a["certainty"]), True) for w in a["words"]]
        elif a["certainty"] == 0.0:            # "not sure" works for every question
            pairs += [(clean(w), (param["values"][0], 0.0), True) for w in a["words"]]
    return pairs


def _parse_number_answer(kb, param, text):
    spec = param["number"]
    unit_spec = kb.settings["units"][spec["unit"]]
    number, unit = read_number(text, unit_spec)
    if number is None:
        raise AnswerError(f"Sorry, I didn't understand \"{text}\". {_examples(kb, param)}")
    if unit is None:
        unit = unit_spec["default"]
        for guess in unit_spec.get("guess", []):
            if number < guess["below"]:
                unit = guess["unit"]
                break
    if unit_spec.get("factor"):
        base = number * unit_spec["factor"][unit]
    else:
        a, b = unit_spec["convert"][unit]
        base = a * number + b
    low, high = spec["range"]
    if not low <= base <= high:
        raise AnswerError(f"{_fmt(number)} {unit} doesn't look right for this question. "
                          f"{_examples(kb, param)}")
    for band in spec["bands"]:
        if band["max"] is None or base <= band["max"]:
            return band["value"], 1.0
    raise AssertionError("unreachable: the last band has no max")


def read_number(text, unit_spec):
    """Find the number and its unit in text. Returns (number or None, unit or None)."""
    text = " ".join(tokens(text))
    add_half = bool(re.search(r"\band (a )?half\b", text))
    text = re.sub(r"\band (a )?half\b", " ", text)
    text = re.sub(r"\bhalf an?\b", "0.5", text)
    text = re.sub(r"\bhalf\b", "0.5", text)
    text = re.sub(r"\ba couple of\b|\ba couple\b|\bcouple of\b", "2", text)

    unit_words = {name: unit for unit, names in unit_spec["names"].items() for name in names}
    words = text.split()
    words = ["1" if w in ("a", "an") and i + 1 < len(words)
             and (words[i + 1] in unit_words or words[i + 1] == "hundred") else w
             for i, w in enumerate(words)]

    number, i = None, 0
    while i < len(words) and number is None:
        if words[i] in NUMBER_WORDS or (words[i] == "1" and i + 1 < len(words) and words[i + 1] == "hundred"):
            number, i = _word_number(words, i)  # "a hundred and three" -> "1 hundred and three"
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?", words[i]):
            number = float(words[i])
        i += 1
    if number is None:
        return None, None
    if add_half:
        number += 0.5

    unit = None
    joined = " ".join(words)
    for name in sorted(unit_words, key=len, reverse=True):
        if re.search(rf"(?<![\w°]){re.escape(name)}(?!\w)", joined):
            unit = unit_words[name]
            break
    return number, unit


def _word_number(words, i):
    """Read "one hundred and two" starting at i. Returns (number, next index)."""
    total = 0
    while i < len(words):
        w = words[i]
        if w in SMALL:
            total += SMALL[w]
        elif w in TENS:
            total += TENS[w]
        elif w == "1" and i + 1 < len(words) and words[i + 1] == "hundred":
            total += 1
        elif w == "hundred":
            total = (total or 1) * 100
        elif w == "point" and i + 1 < len(words) and words[i + 1] in SMALL and SMALL[words[i + 1]] < 10:
            total += SMALL[words[i + 1]] / 10  # "thirty nine point five"
            i += 1
        elif w == "and" and i + 1 < len(words) and words[i + 1] in NUMBER_WORDS:
            pass
        else:
            break
        i += 1
    return float(total), i


def _fmt(number):
    return f"{number:g}"


def _examples(kb, param):
    if param.get("number"):
        unit_spec = kb.settings["units"][param["number"]["unit"]]
        units = ", ".join(names[0] for names in unit_spec["names"].values())
        return f"Please type a number with a unit ({units}), or \"not sure\"."
    if param["values"] == ["yes", "no"]:
        return "Please answer yes, no, probably, probably not or not sure."
    labels = [param["labels"].get(v, v) for v in param["values"]]
    return "Please answer one of: " + ", ".join(labels) + ", or \"not sure\"."
