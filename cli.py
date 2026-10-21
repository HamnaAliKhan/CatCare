"""Text interface for fast testing: python cli.py"""

import sys
from textwrap import indent as _indent

from engine import explain
from engine.inference import Engine, NeedAnswer
from engine.kb import KB
from engine.normalize import MAX_TRIES, AnswerError, not_sure, parse_answer


def indent(text):
    return _indent(text, "  ")


def ask(kb, q, misunderstood):
    """Ask one question; return an answer tuple, "back", or None to re-ask.

    misunderstood[param] counts answers we couldn't understand; after MAX_TRIES
    the question is treated as "not sure", so a consultation can never get stuck.
    """
    p = kb.params[q.param]
    reply = input(f"\n{p['question']}\n  [type your answer, or help / why / back] > ").strip()
    command = reply.lower()
    if command == "help":
        print(indent("How to check: " + p["help"]))
    elif command == "why":
        print(indent(explain.why(kb, q.goals)))
    elif command == "back":
        return "back"
    else:
        try:
            value, certainty = parse_answer(kb, q.param, reply)
        except AnswerError as e:
            misunderstood[q.param] = misunderstood.get(q.param, 0) + 1
            if misunderstood[q.param] < MAX_TRIES:
                print(indent(str(e)))
                return None
            print(indent("I still couldn't understand, so I'll count this as \"not sure\" and carry on. "
                         "(Type back to answer it again.)"))
            return not_sure(kb, q.param)
        if certainty == 0.0:
            print(indent("-> not sure (I'll work with the other answers)"))
        else:
            shown = p["labels"].get(value, value)
            print(indent(f"-> {shown}" + ("" if certainty == 1.0 else f" (certainty {certainty:.1f})")))
        return value, certainty
    return None


def show_result(kb, result):
    urgency = result.groups["urgency"]
    print(f"\n=== {kb.name(urgency.decision).upper()} ===")
    condition = result.groups["condition"]
    group = kb.group_of[kb.goals[0]]
    if condition.kind == "none":
        print(group["none_text"])
    else:
        for goal, cf in condition.ranking:
            print(f"  {kb.name(goal)}: {kb.word(cf)} ({cf:.0%})")
        info = kb.goal_info[condition.decision]
        print(f"\nAbout {info['name']} ({info['medical_name']}): {info['about']}")
        for step in info["care"]:
            print(f"  - {step}")

    options = kb.options[urgency.decision]
    print("\nYour options (you decide):")
    for i, option in enumerate(options["options"], 1):
        print(f"  {i}. {option['name']}")
        print(f"     + {'; '.join(option['pros'])}")
        print(f"     - {'; '.join(option['cons'])}")
    print(f"  Warning: {options['warning']}")
    print(f"\n{kb.settings['disclaimer']}")


def explain_result(kb, result):
    """Answer "how" and "why not <goal>" until the user presses Enter."""
    while True:
        reply = input("\n[how / why not <name, e.g. cat parvo> / Enter to finish] > ").strip().lower()
        if not reply:
            return
        if reply == "how":
            print(indent(explain.how(kb, result)))
            continue
        target = reply.removeprefix("why not").strip().replace(" ", "_")
        match = next((g for g in kb.goals if target and (g == target or kb.name(g).lower() == reply[8:].strip())), None)
        if reply.startswith("why not") and match:
            print(indent(explain.why_not(kb, result, match)))
        else:
            print("  Try: how, or why not " + ", why not ".join(kb.name(g).lower() for g in kb.goals[:3]))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    kb = KB("kb")
    answers, misunderstood = {}, {}
    print(f"{kb.settings['name']}: answer in your own words, e.g. yes, no, probably, not sure, "
          f"\"6 months\", \"102 F\".")
    while True:
        try:
            result = Engine(kb, answers).run()
            break
        except NeedAnswer as q:
            reply = ask(kb, q, misunderstood)
            if reply == "back":
                if answers:
                    answers.popitem()
            elif reply:
                answers[q.param] = reply
    show_result(kb, result)
    explain_result(kb, result)


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print("\nStopped. Run again any time.")
