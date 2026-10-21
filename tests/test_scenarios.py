"""Runs every tests/scenarios/*.json through the normaliser and the engine.

A scenario lists what the owner types for each question. The engine is
consulted like a real interface would: re-run with one more answer each time.
Asking for a parameter the scenario doesn't answer is a failure.

expect keys:
  condition: {kind, goal, min_cf, cf}   kind/goal of the condition group
  urgency:   the decided urgency goal
  max_questions, questions (exact order)
"""

import json
from pathlib import Path

import pytest
from pytest import approx

from engine.inference import Engine, NeedAnswer
from engine.kb import KB
from engine.normalize import parse_answer

SCENARIOS = sorted(Path(__file__).parent.glob("scenarios/*.json"))


@pytest.fixture(scope="module")
def kb():
    return KB(Path(__file__).parents[1] / "kb")


def consult(kb, answers):
    given, asked = {}, []
    while True:
        try:
            return Engine(kb, given).run(), asked
        except NeedAnswer as q:
            assert q.param in answers, f"engine asked {q.param} (after {asked}), not in scenario"
            answer = answers[q.param]
            given[q.param] = (parse_answer(kb, q.param, answer) if isinstance(answer, str)
                              else tuple(answer))
            asked.append(q.param)


@pytest.mark.parametrize("path", SCENARIOS, ids=lambda p: p.stem)
def test_scenario(kb, path):
    s = json.loads(path.read_text(encoding="utf-8"))
    result, asked = consult(kb, s["answers"])
    exp = s["expect"]
    condition, urgency = result.groups["condition"], result.groups["urgency"]
    info = f"condition {condition}, urgency {urgency.decision}, asked {asked}"

    c = exp["condition"]
    if "kind" in c:
        assert condition.kind == c["kind"], info
    if "goal" in c:
        assert condition.decision == c["goal"], info
    top_cf = condition.ranking[0][1] if condition.ranking else None
    if "min_cf" in c:
        assert top_cf >= c["min_cf"], info
    if "cf" in c:
        assert top_cf == approx(c["cf"], abs=1e-3), info
    assert urgency.decision == exp["urgency"], info
    if "max_questions" in exp:
        assert len(asked) <= exp["max_questions"], info
    if "questions" in exp:
        assert asked == exp["questions"], info


def test_every_condition_has_a_definite_scenario(kb):
    covered = set()
    for path in SCENARIOS:
        c = json.loads(path.read_text(encoding="utf-8"))["expect"]["condition"]
        if c.get("kind") == "diagnosis" and c.get("min_cf", 0) >= 0.85:
            covered.add(c["goal"])
    assert covered == set(kb.group_of["cat_flu"]["goal_ids"])


def test_random_owners_always_get_a_decision(kb):
    """500 owners answering at random (incl. "not sure"): no crash, urgency always decided."""
    import random
    rng = random.Random(7)
    urgency_goals = set(kb.group_of["emergency"]["goal_ids"])
    for _ in range(500):
        given = {}
        while True:
            try:
                result = Engine(kb, given).run()
                break
            except NeedAnswer as q:
                given[q.param] = (rng.choice(kb.values(q.param)), rng.choice([1.0, 0.6, 0.4, 0.0]))
        assert result.groups["urgency"].decision in urgency_goals
        if result.groups["condition"].kind == "diagnosis":
            assert result.groups["condition"].ranking[0][1] >= 0.85


def test_danger_signs_are_asked_first(kb):
    with pytest.raises(NeedAnswer) as q:
        Engine(kb, {}).run()
    assert q.value.param == "breathing_trouble"
    assert q.value.goals[0] == "danger_sign"
