"""Inference engine: backward chaining to goals with certainty factors,
plus a forward pass after every new fact.

The knowledge base declares what to establish first (start_with) and the goal
groups to decide, in order. Each group has a policy:
  highest      the goal with the highest belief (diagnosis, differential or none)
  most_severe  the first goal in rank order whose belief is above THRESHOLD,
               else the group's fallback (for urgency: when unsure, more urgent)
Rules may use the goals of an earlier group as premises.

The engine is a pure function of the answers so far: run() either returns a
Result or raises NeedAnswer for the next parameter. It never waits for input,
so every interface re-runs it with one more answer.
"""

from dataclasses import dataclass

from .cf import PRUNE, STOP, THRESHOLD, combine


class NeedAnswer(Exception):
    def __init__(self, param, goals):
        super().__init__(param)
        self.param, self.goals = param, goals  # goals = stack for "Why?"


@dataclass
class GroupResult:
    kind: str       # highest: "diagnosis", "differential" or "none"; most_severe: "decision"
    decision: str | None  # the chosen goal (None when kind is "none")
    ranking: list   # [(goal, cf)] above THRESHOLD, best first


@dataclass
class Result:
    groups: dict    # group id -> GroupResult
    trace: list     # [(rule_id, target, old_cf, new_cf)] for "How?"
    wm: dict        # (param, value) -> cf, final working memory for "Why not?"


class Engine:
    def __init__(self, kb, answers):
        self.kb, self.answers = kb, answers  # {param: (value, certainty)}
        self.wm = {}                          # (param, value) -> cf
        self.done, self.tried, self.fired = set(), set(), set()
        self.trace, self.goals = [], []

    # ----- working memory -----
    def cf(self, p, v="yes"):
        return self.wm.get((p, v), 0.0)

    def set_cf(self, p, v, c):
        self.wm[(p, v)] = c
        for other in self.kb.values(p):
            if other != v:
                self.wm[(p, other)] = -c

    # ----- main loop -----
    def run(self):
        for p in self.kb.start_with:          # e.g. triage: danger signs first
            self.goals = [p]
            self.establish(p)
        results = {}
        for group in self.kb.groups:
            decide = self._highest if group["policy"] == "highest" else self._most_severe
            results[group["id"]] = decide(group)
            self.done.update(group["goal_ids"])  # later groups may use these goals
            self.fire_ready_rules()
        return Result(results, self.trace, dict(self.wm))

    def _next_rule(self, goal):
        return next((r for r in self.kb.rules_concluding(goal)
                     if r["id"] not in self.tried), None)

    def _pursue(self, goal, rule):
        self.goals = [goal]
        self.try_rule(rule)

    def _ranking(self, goal_ids):
        return sorted(((g, self.cf(g)) for g in goal_ids if self.cf(g) > THRESHOLD),
                      key=lambda x: -x[1])

    def _highest(self, group):
        ids = group["goal_ids"]
        while True:
            alive = [g for g in ids if self.cf(g) > PRUNE]
            ranked = sorted(alive, key=lambda g: -self.cf(g))  # stable: ties keep rank order
            if ranked and self.cf(ranked[0]) >= STOP:
                return GroupResult("diagnosis", ranked[0], self._ranking(ids))
            for g in ranked:
                rule = self._next_rule(g)
                if rule:
                    self._pursue(g, rule)
                    break
            else:                              # nothing left to try
                ranking = self._ranking(ids)
                if not ranking:
                    return GroupResult("none", None, [])
                return GroupResult("differential", ranking[0][0], ranking)

    def _most_severe(self, group):
        ids = group["goal_ids"]                # rank order: most severe first
        for g in ids:
            while self.cf(g) > PRUNE and self.cf(g) < STOP:
                rule = self._next_rule(g)
                if not rule:
                    break
                self._pursue(g, rule)
            if self.cf(g) > THRESHOLD:
                return GroupResult("decision", g, self._ranking(ids))
        return GroupResult("decision", group["fallback"], self._ranking(ids))

    # ----- backward chaining -----
    def try_rule(self, rule):
        self.tried.add(rule["id"])
        self.goals.append(rule["id"])
        for p, v in rule["if"].items():
            self.goals.append(p)
            self.establish(p)
            self.goals.pop()
            if self.cf(p, v) <= THRESHOLD:
                break                          # premise false: rule fails
        self.goals.pop()
        self.fire_ready_rules()

    def establish(self, p):
        if p in self.done:
            return
        if self.kb.is_goal(p):                 # a goal of a group not decided yet
            return                             # (the KB loader forbids this; stay safe)
        if self.kb.params[p]["type"] == "askable":
            if p not in self.answers:
                raise NeedAnswer(p, list(self.goals))
            value, certainty = self.answers[p]
            self.set_cf(p, value, certainty)
        else:                                  # derived: chain backward
            for rule in self.kb.rules_concluding(p):
                if rule["id"] not in self.tried:
                    self.try_rule(rule)
        self.done.add(p)
        self.fire_ready_rules()

    # ----- forward pass -----
    def fire_ready_rules(self):
        changed = True
        while changed:
            changed = False
            for rule in self.kb.rules:
                if rule["id"] in self.fired:
                    continue
                if not all(p in self.done for p in rule["if"]):
                    continue
                strength = min(self.cf(p, v) for p, v in rule["if"].items())
                if strength <= THRESHOLD:
                    continue
                self.fired.add(rule["id"])
                self.tried.add(rule["id"])     # don't "try" it again later
                for target in rule["then"]:
                    old = self.cf(target)
                    new = combine(old, rule["cf"] * strength)
                    self.set_cf(target, "yes", new)
                    self.trace.append((rule["id"], target, old, new))
                changed = True
