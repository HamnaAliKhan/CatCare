"""Knowledge-base checker: python tools/kb_check.py [kb folder]

Reports problems the loader can't see on its own. Unknown parameters, bad
values, bands, units and CFs outside -1..+1 already stop KB() from loading,
and are reported here too. Exit code 1 if anything is found.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # find engine/

from engine.kb import KB, KBError  # noqa: E402


def check(kb):
    problems = []
    askable = [p for p, info in kb.params.items() if info["type"] == "askable"]
    derived = [p for p, info in kb.params.items() if info["type"] == "derived"]
    used = {p for r in kb.rules for p in r["if"]} | set(kb.start_with)

    for group in kb.groups:
        for g in group["goal_ids"]:
            cfs = [r["cf"] for r in kb.rules_concluding(g)]
            if g != group.get("fallback") and not any(c > 0 for c in cfs):
                problems.append(f"{g}: no rule supports it, so it can never be chosen")
            if group["policy"] == "highest" and not any(c < 0 for c in cfs):
                problems.append(f"{g}: no rule counts against it")
            if group["policy"] == "most_severe" and g not in kb.options:
                problems.append(f"{g}: no decision-support options")

    for p in askable:
        if p not in used:
            problems.append(f"{p}: askable but no rule uses it")
    for p in derived:
        if not kb.rules_concluding(p):
            problems.append(f"{p}: derived but no rule concludes it")
        if p not in used:
            problems.append(f"{p}: derived but no rule uses it")

    problems += _cycles(kb, derived)

    by_key = {}
    for r in kb.rules:
        if r["cf"] == 0:
            problems.append(f"{r['id']}: CF is 0, so it can never change anything")
        for target in r["then"]:
            key = (frozenset(r["if"].items()), target)
            for other in by_key.get(key, []):
                if (other["cf"] > 0) != (r["cf"] > 0):
                    problems.append(f"{other['id']} and {r['id']}: same premises, "
                                    f"opposite conclusions about {target}")
                else:
                    problems.append(f"{other['id']} and {r['id']}: same premises and "
                                    f"conclusion about {target}, so the evidence counts twice")
            by_key.setdefault(key, []).append(r)
    return problems


def _cycles(kb, derived):
    """Derived facts that (indirectly) need themselves."""
    needs = {p: {q for r in kb.rules_concluding(p) for q in r["if"] if q in derived}
             for p in derived}
    found, state = [], {}  # state: 1 = on the current path, 2 = finished

    def visit(p, path):
        state[p] = 1
        for q in sorted(needs[p]):
            if state.get(q) == 1:
                cycle = path[path.index(q):] + [q]
                found.append("cycle between derived facts: " + " -> ".join(cycle))
            elif q not in state:
                visit(q, path + [q])
        state[p] = 2

    for p in derived:
        if p not in state:
            visit(p, [p])
    return found


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "kb"
    try:
        kb = KB(folder)
    except KBError as e:
        print(e)
        return 1
    problems = check(kb)
    for p in problems:
        print("-", p)
    askable = sum(p["type"] == "askable" for p in kb.params.values())
    print(f"{len(problems)} problem(s): {len(kb.rules)} rules, {askable} questions, "
          f"{len(kb.params) - askable} intermediate facts, {len(kb.goals)} goals")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
