from pathlib import Path

from engine.kb import KB
from tools.draw_tree import build, most_severe, triage_clear

KB_DIR = Path(__file__).parents[1] / "kb"


def test_triage_tree_starts_with_breathing_and_emergency():
    kb = KB(KB_DIR)
    tree = build(kb, {}, depth=6)
    assert tree.label == "Struggling to breathe?"
    edge, child = tree.children[0]
    assert edge == "Yes" and child.label.startswith(most_severe(kb))


def test_diagnosis_tree_starts_after_clear_triage():
    kb = KB(KB_DIR)
    assert set(triage_clear(kb)) == {"breathing_trouble", "collapsed", "straining", "litter_often", "blood_in_stool"}
    assert build(kb, triage_clear(kb), depth=3).label == "Sneezing?"
