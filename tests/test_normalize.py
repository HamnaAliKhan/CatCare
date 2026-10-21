"""Flexible input: every way of writing an answer the instructor listed, and more."""

import random
import string
from pathlib import Path

import pytest

from engine.kb import KB
from engine.normalize import AnswerError, parse_answer, read_number


@pytest.fixture(scope="module")
def kb():
    return KB(Path(__file__).parents[1] / "kb")


@pytest.mark.parametrize("param, text, expected", [
    # yes / no and certainty words, English and Roman Urdu
    ("sneezing", "yes", ("yes", 1.0)), ("sneezing", "Yeah!", ("yes", 1.0)), ("sneezing", "haan", ("yes", 1.0)),
    ("sneezing", "ji", ("yes", 1.0)), ("sneezing", "NO", ("no", 1.0)), ("sneezing", "nahi", ("no", 1.0)),
    ("sneezing", "probably", ("yes", 0.6)), ("sneezing", "maybe", ("yes", 0.4)),
    ("sneezing", "not sure", ("yes", 0.0)), ("sneezing", "no idea", ("yes", 0.0)), ("sneezing", "pata nahi", ("yes", 0.0)),
    ("sneezing", "probably not", ("no", 0.6)), ("sneezing", "yes, a lot", ("yes", 1.0)),
    # symptom words
    ("vomiting", "throwing up", ("yes", 1.0)), ("vomiting", "ulti", ("yes", 1.0)),
    ("diarrhoea", "loose motions", ("yes", 1.0)), ("diarrhoea", "dast", ("yes", 1.0)),
    ("little_urine", "only drops", ("yes", 1.0)), ("little_urine", "none at all", ("yes", 1.0)),
    ("little_urine", "none", ("yes", 1.0)), ("little_urine", "normal amount", ("no", 1.0)),
    ("vaccinated", "FVRCP done", ("yes", 1.0)), ("vaccinated", "teeka nahi", ("no", 1.0)),
    # categories and synonyms
    ("sex", "tom", ("male", 1.0)), ("sex", "billi", ("female", 1.0)), ("sex", "Female", ("female", 1.0)),
    ("appetite", "not eating", ("none", 1.0)), ("appetite", "kam", ("less", 1.0)), ("appetite", "yes", ("normal", 1.0)),
    ("appetite", "no idea", ("normal", 0.0)),
    # temperature: digits, words, units, °, conversion, unit guessing
    ("temperature", "100", ("normal", 1.0)), ("temperature", "hundred", ("normal", 1.0)),
    ("temperature", "100°F", ("normal", 1.0)), ("temperature", "103 F", ("high", 1.0)),
    ("temperature", "a hundred and three", ("high", 1.0)), ("temperature", "one hundred and two", ("normal", 1.0)),
    ("temperature", "39 c", ("normal", 1.0)), ("temperature", "39.8°C", ("high", 1.0)),
    ("temperature", "39.8", ("high", 1.0)), ("temperature", "thirty nine point eight", ("high", 1.0)),
    ("temperature", "102.5 degrees", ("normal", 1.0)), ("temperature", "fever", ("high", 1.0)),
    ("temperature", "feels hot", ("high", 0.6)), ("temperature", "not sure", ("normal", 0.0)),
    # age: units, words, halves
    ("age", "6 months", ("kitten", 1.0)), ("age", "6mo", ("kitten", 1.0)), ("age", "half a year", ("kitten", 1.0)),
    ("age", "2 years", ("adult", 1.0)), ("age", "two yrs old", ("adult", 1.0)), ("age", "3", ("adult", 1.0)),
    ("age", "10 weeks", ("kitten", 1.0)), ("age", "kitten", ("kitten", 1.0)), ("age", "bacha", ("kitten", 1.0)),
    ("age", "a year and a half", ("adult", 1.0)),
    # hours since it ate
    ("hours_since_ate", "10 hours", ("under_24", 1.0)), ("hours_since_ate", "2 days", ("over_24", 1.0)),
    ("hours_since_ate", "since yesterday", ("over_24", 1.0)), ("hours_since_ate", "a day and a half", ("over_24", 1.0)),
    ("hours_since_ate", "36 hrs", ("over_24", 1.0)), ("hours_since_ate", "this morning", ("under_24", 1.0)),
])
def test_understood(kb, param, text, expected):
    assert parse_answer(kb, param, text) == expected


@pytest.mark.parametrize("param, text", [
    ("sneezing", ""), ("sneezing", "   "), ("sneezing", "banana"), ("sex", "yes"),
    ("temperature", "500"), ("temperature", "-3"), ("temperature", "hot dog stand"),
    ("age", "200 years"), ("hours_since_ate", "9999 days"), ("age", "x" * 500),
])
def test_rejected_with_a_message(kb, param, text):
    with pytest.raises(AnswerError) as e:
        parse_answer(kb, param, text)
    assert str(e.value)


def test_read_number_words_and_units(kb):
    months = kb.settings["units"]["months"]
    assert read_number("a year and a half", months) == (1.5, "year")
    assert read_number("one hundred and two", months) == (102.0, None)


def test_fuzz_never_crashes(kb):
    """Random garbage must give an answer or an AnswerError, never anything else."""
    rng = random.Random(42)
    alphabet = string.printable + "°½€😺ابپ"
    askable = [p for p, info in kb.params.items() if info["type"] == "askable"]
    for _ in range(3000):
        text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 40)))
        param = rng.choice(askable)
        try:
            value, certainty = parse_answer(kb, param, text)
        except AnswerError:
            continue
        assert value in kb.values(param) and 0.0 <= certainty <= 1.0
