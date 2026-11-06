"""Draw the decision tree the rules produce: python tools/draw_tree.py

The engine is run on every combination of clear answers (yes/no, or each
category) up to a depth limit. Each node is the question the engine actually
asks at that point, so the tree is an *output* of the rules: change a rule
and the tree redraws. Branches cut at the depth limit are labelled with the
result the owner would get by answering "not sure" to everything after.

Two trees, matching the system's hierarchy:
  1. triage: the danger-sign questions asked first
  2. diagnosis: what happens after triage finds no danger sign

Writes docs/decision_tree.md (Mermaid, renders as a diagram on GitHub) and
docs/decision_tree.txt (indented text).
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # find engine/

from engine.inference import Engine, NeedAnswer  # noqa: E402
from engine.kb import KB  # noqa: E402
from engine.normalize import not_sure  # noqa: E402


CONTINUES = " (the diagnosis continues with more questions)"


class Node:
    def __init__(self, label, kind):
        self.label, self.kind, self.children = label, kind, []   # children: [(edge, Node)]


def build(kb, given, depth):
    """The tree below the answers already given, `depth` questions deep."""
    try:
        result = Engine(kb, given).run()
    except NeedAnswer as q:
        if depth == 0:
            return Node("… " + outcome(kb, finish(kb, given)), "cut")
        info = kb.params[q.param]
        node = Node(info.get("short") or info["question"], "question")
        for value in kb.values(q.param):
            edge = info["labels"].get(value, value.replace("_", " ").capitalize())
            node.children.append((edge, build(kb, {**given, q.param: (value, 1.0)}, depth - 1)))
        return collapse(node, most_severe(kb))
    return Node(outcome(kb, result), "result")


def collapse(node, most_severe):
    """Draw one box when the answers below a question no longer change anything:
    every outcome identical, or every outcome the most severe urgency (triage decided it)."""
    labels = {leaf.label for leaf in leaves(node)}
    if len(labels) == 1:
        leaf = leaves(node)[0]
        return Node(leaf.label, leaf.kind)
    urgencies = {label.lstrip("… ").split(" · ")[0].removesuffix(CONTINUES) for label in labels}
    if urgencies == {most_severe}:
        return Node(most_severe + CONTINUES, "result")
    return node


def most_severe(kb):
    group = next(g for g in kb.groups if g["policy"] == "most_severe")
    return kb.name(group["goal_ids"][0])


def leaves(node):
    if not node.children:
        return [node]
    return [leaf for _, child in node.children for leaf in leaves(child)]


def finish(kb, given):
    """Complete a consultation answering "not sure" (no evidence either way) to every remaining question."""
    answers = dict(given)
    while True:
        try:
            return Engine(kb, answers).run()
        except NeedAnswer as q:
            answers[q.param] = not_sure(kb, q.param)


def outcome(kb, result):
    parts = []
    for group in kb.groups:
        g = result.groups[group["id"]]
        if group["policy"] == "most_severe":
            parts.insert(0, kb.name(g.decision))
        elif g.kind == "none":
            parts.append("no known condition")
        else:
            parts.append(f"{kb.name(g.decision)}: {kb.word(g.ranking[0][1])}")
    return " · ".join(parts)


def triage_clear(kb):
    """Answers that clear the start_with checks with "no" (the start of the diagnosis tree)."""
    answers = {}
    while True:
        engine = Engine(kb, answers)
        try:
            engine.run()
            return answers
        except NeedAnswer as q:
            if q.goals and q.goals[0] not in kb.start_with:
                return answers
            answers[q.param] = (kb.values(q.param)[-1], 1.0)


def to_text(node, indent="", edge=None):
    head = f"{indent}{'[' + edge + '] ' if edge else ''}"
    mark = {"question": "?", "result": "=>", "cut": "=>"}[node.kind]
    lines = [f"{head}{node.label} {mark}" if node.kind == "question" else f"{head}{mark} {node.label}"]
    for child_edge, child in node.children:
        lines += to_text(child, indent + "    ", child_edge)
    return lines


def to_mermaid(node, prefix):
    lines, counter = [], [0]

    def walk(n):
        counter[0] += 1
        nid = f"{prefix}{counter[0]}"
        text = n.label.replace('"', "'")
        shape = f'{nid}["{text}"]' if n.kind == "question" else f'{nid}(["{text}"])'
        lines.append(f"    {shape}")
        if n.kind != "question":
            lines.append(f"    class {nid} {'result' if n.kind == 'result' else 'cut'}")
        for edge, child in n.children:
            cid = walk(child)
            lines.append(f"    {nid} -->|{edge}| {cid}")
        return nid

    walk(node)
    return lines


def count(node):
    return 1 + sum(count(c) for _, c in node.children)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--depth", type=int, default=6, help="questions per tree (default 6)")
    args = parser.parse_args()

    kb = KB(ROOT / "kb")
    trees = [
        ("1. Triage: danger signs first", "t", build(kb, {}, args.depth)),
        ("2. Diagnosis: after triage finds no danger sign", "d",
         build(kb, triage_clear(kb), args.depth)),
    ]
    md = ["# CatCare decision tree", "",
          "Generated by `python tools/draw_tree.py` from the rules in `kb/` (do not edit by hand).",
          f"Each tree shows up to {args.depth} questions; a rounded box is a result. Boxes starting",
          "with … are cut at the depth limit and show the result if every later answer is \"not sure\".", ""]
    txt = []
    for title, prefix, tree in trees:
        md += [f"## {title}", "", f"{count(tree)} nodes.", "", "```mermaid", "flowchart TD",
               "    classDef result fill:#e8f5e9,stroke:#2e7d32",
               "    classDef cut fill:#f5f5f5,stroke:#9e9e9e,stroke-dasharray: 4 3"]
        md += to_mermaid(tree, prefix) + ["```", ""]
        txt += [title, ""] + to_text(tree) + [""]
    (ROOT / "docs" / "decision_tree.md").write_text("\n".join(md), encoding="utf-8")
    (ROOT / "docs" / "decision_tree.txt").write_text("\n".join(txt), encoding="utf-8")
    print(f"Wrote docs/decision_tree.md and .txt: {', '.join(str(count(t)) for _, _, t in trees)} nodes")


if __name__ == "__main__":
    main()
