from pathlib import Path

import pytest

from engine import explain
from engine.inference import Engine, NeedAnswer
from engine.kb import KB

Y, N = ("yes", 1.0), ("no", 1.0)
TRIAGE_CLEAR = {"breathing_trouble": N, "collapsed": N, "straining": N, "litter_often": N, "blood_in_stool": N}
BLOCKED_MALE = {"breathing_trouble": N, "collapsed": N, "straining": Y, "litter_often": Y,
                "little_urine": Y, "blood_in_stool": N}


@pytest.fixture(scope="module")
def kb():
    return KB(Path(__file__).parents[1] / "kb")


def test_why_during_triage(kb):
    with pytest.raises(NeedAnswer) as q:
        Engine(kb, {"breathing_trouble": N, "collapsed": N, "straining": Y, "litter_often": Y}).run()
    assert q.value.goals == ["danger_sign", "R3", "urine_blocked", "R9", "little_urine"]
    text = explain.why(kb, q.value.goals)
    assert text.startswith("Before anything else, I check for danger signs")
    assert "Rule R9: Your cat is trying to urinate but little or no urine comes out" in text
    assert '"When it tries, does your cat pass only a little urine, or none at all?"' in text


def test_why_during_diagnosis(kb):
    with pytest.raises(NeedAnswer) as q:
        Engine(kb, TRIAGE_CLEAR).run()
    assert q.value.goals[:3] == ["cat_flu", "R27", "respiratory_signs"]
    assert explain.why(kb, q.value.goals).startswith("I'm testing whether your cat has Cat Flu.")


def test_how_shows_the_chain_to_emergency(kb):
    text = explain.how(kb, Engine(kb, BLOCKED_MALE).run())
    assert "R9: Your cat is trying to urinate but little or no urine comes out" in text
    assert text.index("R38:") < text.index("R47:")
    assert "Emergency: go to a vet now" in text


def test_why_not_cat_flu(kb):
    result = Engine(kb, {**TRIAGE_CLEAR, "sneezing": N, "eye_discharge": N, "nose_discharge": N,
                         "vomiting": N, "diarrhoea": N, "appetite": ("normal", 1.0)}).run()
    text = explain.why_not(kb, result, "cat_flu")
    assert text.startswith("R32 lowered Cat Flu")
    assert "(ruled out)" in text


def test_why_not_never_tested(kb):
    result = Engine(kb, BLOCKED_MALE).run()  # diagnosed during triage, flu never tested
    assert "was never tested" in explain.why_not(kb, result, "cat_flu")
