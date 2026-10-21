"""Explanation facility: turns the goal stack and the trace into plain sentences.

why(kb, goals)            during a question: what is being tested and why this fact is needed
how(kb, result)           at the result: every fired rule and how it moved each belief
why_not(kb, result, g)    at the result: what lowered goal g, or that it was never tested
"""

from .cf import PRUNE


def _cf(c):
    return f"{c:+.2f}"


def _opening(kb, top):
    if kb.is_goal(top):
        return kb.group_of[top]["testing_text"].format(name=kb.name(top))
    return kb.settings["start_text"].format(label=kb.params[top]["label"])


def why(kb, goals):
    """goals = [goal or start param, rule, param, rule, param, ..., askable param]."""
    top, rest = goals[0], goals[1:]
    lines = [_opening(kb, top)]
    for i in range(0, len(rest) - 1, 2):
        rule, param = kb.rule_info[rest[i]], rest[i + 1]
        lines.append(f"Rule {rule['id']}: {rule['why']}")
        info = kb.params[param]
        if info["type"] == "derived":
            lines.append(f"To use it, I first need to know whether {info['label']}.")
        else:
            lines.append(f"For that I need your answer to: \"{info['question']}\"")
            lines.append(info["why"])
    if len(goals) == 1 and goals[0] in kb.params and kb.params[goals[0]]["type"] == "askable":
        lines.append(kb.params[goals[0]]["why"])
    return "\n".join(lines)


def how(kb, result):
    """Every fired rule in order, its why text, and the beliefs it changed."""
    lines, last = [], None
    for rule_id, target, old, new in result.trace:
        if rule_id == "fix failed":
            lines.append(f"You said the advice for {kb.name(target)} did not help, so it was ruled out ({_cf(new)}).")
            last = None
            continue
        if rule_id != last:
            lines.append(f"{rule_id}: {kb.rule_info[rule_id]['why']}")
            last = rule_id
        lines.append(f"    {kb.name(target)}: {_cf(old)} -> {_cf(new)}")
    return "\n".join(lines) if lines else "No rules fired."


def why_not(kb, result, goal):
    """The rules that changed a goal's belief, or that it was never tested."""
    name = kb.name(goal)
    entries = [t for t in result.trace if t[1] == goal]
    if not entries:
        return f"{name} was never tested: the evidence pointed elsewhere before it was reached."
    lines = []
    for rule_id, _, old, new in entries:
        if rule_id == "fix failed":
            lines.append(f"You said the advice did not help, so it was ruled out ({_cf(new)}).")
            continue
        verb = "lowered" if new < old else "raised"
        lines.append(f"{rule_id} {verb} {name} from {_cf(old)} to {_cf(new)}: "
                     f"{kb.rule_info[rule_id]['why']}")
    final = result.wm.get((goal, "yes"), 0.0)
    status = " (ruled out)" if final <= PRUNE else ""
    lines.append(f"Final belief in {name}: {_cf(final)}, {kb.word(final)}{status}.")
    return "\n".join(lines)
