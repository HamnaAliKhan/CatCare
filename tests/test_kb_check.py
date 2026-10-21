import json
from pathlib import Path

import pytest

from engine.kb import KB, KBError
from tools.kb_check import check

KB_DIR = Path(__file__).parents[1] / "kb"
FILES = ("params.json", "rules.json", "goals.json", "settings.json", "options.json")


def test_real_kb_is_clean():
    assert check(KB(KB_DIR)) == []


def test_at_least_50_rules():
    assert len(KB(KB_DIR).rules) >= 50


def make_kb(tmp_path, edit):
    """Copy the real KB, apply edit(data), load it."""
    data = {n: json.loads((KB_DIR / n).read_text(encoding="utf-8")) for n in FILES}
    edit(data)
    for name, content in data.items():
        (tmp_path / name).write_text(json.dumps(content), encoding="utf-8")
    return KB(tmp_path)


def test_finds_planted_problems(tmp_path):
    def edit(d):
        params, rules = d["params.json"], d["rules.json"]
        rules[:] = [r for r in rules if r["id"] != "R38"]  # keep blocked bladder reachable via R39
        rules[:] = [r for r in rules if r["id"] not in ("R27", "R28", "R29", "R30", "R31")]  # Cat Flu: no support
        params["extra_q"] = {"type": "askable", "question": "q", "help": "h", "why": "w"}  # unused
        params["loop_a"] = {"type": "derived", "label": "a"}
        params["loop_b"] = {"type": "derived", "label": "b"}
        rules += [
            {"id": "X1", "if": {"loop_b": "yes"}, "then": ["loop_a"], "cf": 0.5, "why": "w", "source": "s"},
            {"id": "X2", "if": {"loop_a": "yes"}, "then": ["loop_b"], "cf": 0.5, "why": "w", "source": "s"},
            {"id": "X3", "if": {"sneezing": "yes"}, "then": ["respiratory_signs"], "cf": -0.5, "why": "w", "source": "s"},
        ]
        del d["options.json"]["vet_soon"]

    problems = "\n".join(check(make_kb(tmp_path, edit)))
    assert "cat_flu: no rule supports it" in problems
    assert "extra_q: askable but no rule uses it" in problems
    assert "cycle between derived facts" in problems
    assert "R11 and X3: same premises, opposite conclusions about respiratory_signs" in problems
    assert "vet_soon: no decision-support options" in problems


@pytest.mark.parametrize("edit, message", [
    (lambda d: d["rules.json"].append({"id": "Y1", "if": {"sneezng": "yes"}, "then": ["cat_flu"], "cf": 0.5, "why": "w", "source": "s"}),
     "unknown parameter 'sneezng'"),
    (lambda d: d["rules.json"].append({"id": "Y1", "if": {"emergency": "yes"}, "then": ["cat_flu"], "cf": 0.5, "why": "w", "source": "s"}),
     "may only conclude goals of a later group"),
    (lambda d: d["params.json"]["age"]["number"].update(unit="lightyears"), "unknown unit 'lightyears'"),
    (lambda d: d["goals.json"]["groups"][1].update(fallback="nap"), "fallback 'nap'"),
])
def test_loader_rejects_mistakes(tmp_path, edit, message):
    with pytest.raises(KBError, match=message):
        make_kb(tmp_path, edit)
