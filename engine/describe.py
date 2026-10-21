"""Free-text description: "my 4 month old kitten is vomiting & has dast, not
vaccinated, not eating since yesterday" -> answers the engine won't need to ask.

How it reads a description:
  1. Split into clauses at separators (",", "&", "and", "aur", ...).
  2. In each clause, find the questions' own phrases, longest first. A phrase
     shared by two questions ("blood": stool or urine?) is skipped as ambiguous,
     and so are generic words ("yes", "none") and words under 4 letters.
  3. A negation next to a phrase flips a yes/no answer: "no runny nose",
     "ulti nahi". Phrases that already contain a negation ("not eating") keep
     their own meaning.
  4. Numbers count only near a question's text cues: "4 month OLD" -> age,
     "not EATING since 2 days" -> hours since it ate.
  5. The same fact twice is kept once (redundant); two different answers to
     the same question are a conflict, left for the engine to ask.

All the words come from the knowledge base. The UI shows what was understood
so the owner can correct it before the questions start.
"""

import re
from dataclasses import dataclass, field

from .normalize import MAX_LENGTH, NUMBER_WORDS, AnswerError, _phrases, clean, parse_answer

MAX_DESCRIPTION = MAX_LENGTH * 5
MIN_WORD = 4  # single-word phrases shorter than this are too vague in free text
NUMBER = re.compile(r"\d|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
                    r"twenty|thirty|forty|fifty|hundred|half|a couple)\b")


@dataclass
class Finding:
    param: str
    value: str
    certainty: float
    text: str        # the words that were understood


@dataclass
class Description:
    facts: dict = field(default_factory=dict)       # param -> (value, certainty), safe to use
    findings: list = field(default_factory=list)    # every Finding, for "I understood: ..."
    conflicts: dict = field(default_factory=dict)   # param -> [Finding, ...] that disagree
    not_understood: list = field(default_factory=list)  # clauses with nothing understood


def read_description(kb, text):
    words = kb.settings["description"]
    text = str(text or "")[:MAX_DESCRIPTION].lower().replace("’", "'")
    result = Description()
    index = _phrase_index(kb)
    text = _protect(text, index, words["separators"])
    for clause in _clauses(text, words["separators"]):
        clause = clause.replace("_", " ")
        found = _read_clause(kb, clause, index, words)
        if found:
            result.findings += found
        elif clean(clause):
            result.not_understood.append(clean(clause))
    _merge(result)
    return result


def _protect(text, index, separators):
    """Keep phrases that contain a separator word whole: "again and again"."""
    words = {s for s in separators if s[0].isalnum()}
    text = text.replace("_", " ")
    for phrase, _ in index:
        if words & set(phrase.split()):
            text = re.sub(rf"(?<!\w){re.escape(phrase)}(?!\w)", phrase.replace(" ", "_"), text)
    return text


def _clauses(text, separators):
    symbols = [re.escape(s) for s in separators if not s[0].isalnum()]
    wordlike = [re.escape(s) for s in separators if s[0].isalnum()]
    pattern = "|".join(symbols + [rf"\b{w}\b" for w in sorted(wordlike, key=len, reverse=True)])
    text = re.sub(r"(\d)\.(\d)", r"\1<dot>\2", text)        # keep "102.5" whole
    return [c.replace("<dot>", ".").strip() for c in re.split(pattern, text) if c.strip()]


def _phrase_index(kb):
    """phrase -> (param, value, certainty), longest first, without ambiguous phrases."""
    generic = {clean(w) for a in kb.settings["answers"].values() for w in a["words"]}
    owners = {}
    for pid, param in kb.params.items():
        if param["type"] != "askable":
            continue
        for phrase, (value, certainty), _ in _phrases(kb, param):
            if phrase in generic or (" " not in phrase and len(phrase) < MIN_WORD):
                continue
            if certainty == 0.0:
                continue
            owners.setdefault(phrase, set()).add((pid, value, certainty))
    index = [(phrase, next(iter(o))) for phrase, o in owners.items()
             if len({pid for pid, _, _ in o}) == 1 and len(o) == 1]
    return sorted(index, key=lambda x: -len(x[0]))


def _read_clause(kb, clause, index, words):
    text = " " + clean(clause) + " "
    found = []
    for phrase, (pid, value, certainty) in index:
        flexible = r"\s*".join(re.escape(w) for w in phrase.split())  # "stand up" also matches "standup"
        match = re.search(rf"(?<![\w']){flexible}(?![\w'])", text)
        if not match:
            continue
        if _negated(text, match, words) and kb.values(pid) == ["yes", "no"]:
            value = "no" if value == "yes" else "yes"
        found.append(Finding(pid, value, certainty, phrase))
        text = text[:match.start()] + " " * (match.end() - match.start()) + text[match.end():]
    found += _numbers(kb, clean(clause))
    return found


def _negated(text, match, words):
    before = text[:match.start()].split()[-2:]
    after = text[match.end():].split()[:2]
    before_words = {w for w in words["negations_before"] if " " not in w}
    before_phrases = [w for w in words["negations_before"] if " " in w]
    return (any(w in before_words for w in before)
            or any(" ".join(before).endswith(p) for p in before_phrases)
            or any(w in words["negations_after"] for w in after))


def _numbers(kb, clause):
    """Numbers tied to a question by its text cues.

    For each cue ("old", "eating", "temperature") take the number closest to it
    (after it on a tie) and read it with the words that follow (its unit):
    "2 years old aur khana nahi kha rahi 2 din se" -> age "2 years", ate "2 din".
    """
    if not NUMBER.search(clause):
        return []
    tokens = clause.split()
    starts = _number_starts(tokens)
    found = []
    for pid, param in kb.params.items():
        cues = set(param.get("text_cues") or [])
        for i, token in enumerate(tokens):
            if token not in cues and not any(c in token for c in cues if not c.isalpha()):
                continue
            near = [s for s in starts if abs(s - i) <= 6]
            if not near:
                continue
            start = min(near, key=lambda s: (abs(s - i), s < i))
            end = start
            while end < len(tokens) and (tokens[end] in NUMBER_WORDS or _is_digit(tokens[end])
                                         or tokens[end] in ("and", "point", "a", "half")):
                end += 1
            segment = " ".join(tokens[start:end + 2])
            try:
                value, certainty = parse_answer(kb, pid, segment)
            except AnswerError:
                continue
            if certainty > 0:
                found.append(Finding(pid, value, certainty, segment))
                break
    return found


def _is_digit(token):
    return bool(re.fullmatch(r"\d+(?:\.\d+)?[^\d\s]*", token))


def _number_starts(tokens):
    """Positions where a number begins: "102", "6mo", "a hundred and two", "half a year"."""
    starts = []
    for i, t in enumerate(tokens):
        is_number = _is_digit(t) or t in NUMBER_WORDS or t == "half"
        prev_is_number = i > 0 and (_is_digit(tokens[i - 1]) or tokens[i - 1] in NUMBER_WORDS
                                    or tokens[i - 1] in ("and", "point", "half"))
        if is_number and not prev_is_number:
            starts.append(i - 1 if i > 0 and tokens[i - 1] == "a" else i)
    return starts


def _merge(result):
    by_param = {}
    for f in result.findings:
        by_param.setdefault(f.param, []).append(f)
    for pid, fs in by_param.items():
        values = {f.value for f in fs}
        if len(values) == 1:
            result.facts[pid] = (fs[0].value, max(f.certainty for f in fs))
        else:
            result.conflicts[pid] = fs
