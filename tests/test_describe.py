"""Free-text descriptions: separators, negation, numbers, redundancy, conflicts, junk."""

import random
import string
from pathlib import Path

import pytest

from engine.describe import read_description
from engine.inference import Engine, NeedAnswer
from engine.kb import KB


@pytest.fixture(scope="module")
def kb():
    return KB(Path(__file__).parents[1] / "kb")


@pytest.mark.parametrize("text, expected", [
    ("my 4 month old kitten is vomiting & has dast, not vaccinated, not eating since yesterday",
     {"age": "kitten", "vomiting": "yes", "diarrhoea": "yes", "vaccinated": "no",
      "appetite": "none", "hours_since_ate": "over_24"}),
    ("sneezing and runny eyes but still eating, no runny nose",
     {"sneezing": "yes", "eye_discharge": "yes", "appetite": "normal", "nose_discharge": "no"}),
    ("male cat straining in litter box, only drops of urine, crying",
     {"sex": "male", "straining": "yes", "little_urine": "yes", "cries_urinating": "yes"}),
    ("ulti nahi, dast hai, bukhar", {"vomiting": "no", "diarrhoea": "yes", "temperature": "high"}),
    ("temperature is 39.8 c and he is lethargic", {"temperature": "high", "tired": "yes"}),
    ("my cat is not able to standup and breathing fast", {"collapsed": "yes", "breathing_trouble": "yes"}),
    ("blood in urine", {"blood_in_urine": "yes"}),
    ("she is 2 years old aur khana nahi kha rahi 2 din se",
     {"age": "adult", "appetite": "none", "hours_since_ate": "over_24"}),
])
def test_understood(kb, text, expected):
    d = read_description(kb, text)
    assert {p: v for p, (v, _) in d.facts.items()} == expected


def test_redundant_facts_are_kept_once(kb):
    d = read_description(kb, "sneezing, sneezing a lot, keeps sneezing")
    assert d.facts == {"sneezing": ("yes", 1.0)} and not d.conflicts


def test_contradiction_is_left_for_the_engine_to_ask(kb):
    d = read_description(kb, "sneezing. not sneezing")
    assert "sneezing" in d.conflicts and "sneezing" not in d.facts


def test_ambiguous_word_is_not_guessed(kb):
    d = read_description(kb, "blood")           # stool or urine? ask instead
    assert d.facts == {} and d.not_understood == ["blood"]


def test_description_saves_questions(kb):
    d = read_description(kb, "male cat straining in litter box again and again, only drops of urine")
    answers = dict(d.facts)
    asked = []
    while True:
        try:
            result = Engine(kb, answers).run()
            break
        except NeedAnswer as q:
            answers[q.param] = ("no", 1.0)
            asked.append(q.param)
    assert result.groups["urgency"].decision == "emergency"
    assert asked == ["breathing_trouble", "collapsed", "blood_in_stool"]  # 3 questions instead of 6


def test_junk_never_crashes(kb):
    rng = random.Random(11)
    alphabet = string.printable + "°½😺ابپ&,"
    for _ in range(1000):
        text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 120)))
        d = read_description(kb, text)
        for pid, (value, certainty) in d.facts.items():
            assert value in kb.values(pid) and 0 < certainty <= 1
    assert read_description(kb, None).facts == {}
    assert read_description(kb, "x" * 100000).facts == {}
