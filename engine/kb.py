"""Loads and validates the knowledge base (kb/*.json).

Pydantic checks each file's shape; _cross_check makes sure rules, bands,
synonyms and options only mention parameters, values and goals that exist.
Any mistake stops the load with a clear error. The engine then gets plain dicts.
"""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

YES_NO = ["yes", "no"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Band(Strict):
    max: float | None = None   # value applies up to and including max; None = everything above
    value: str


class NumberSpec(Strict):
    unit: str
    range: tuple[float, float]
    bands: list[Band] = Field(min_length=2)


class Param(Strict):
    type: Literal["askable", "derived"]
    short: str | None = None      # a few words, for diagrams and answer lists
    question: str | None = None
    help: str | None = None
    why: str | None = None
    label: str | None = None
    values: list[str] = Field(default_factory=lambda: list(YES_NO), min_length=2)
    labels: dict[str, str] = Field(default_factory=dict)
    synonyms: dict[str, list[str | tuple[str, float]]] = Field(default_factory=dict)
    number: NumberSpec | None = None
    text_cues: list[str] = Field(default_factory=list)  # words that tie a number in a description to this question

    @model_validator(mode="after")
    def _texts(self):
        if self.type == "askable":
            missing = [f for f in ("question", "help", "why") if not getattr(self, f)]
            if missing:
                raise ValueError(f"askable parameter needs {missing}")
        elif not self.label:
            raise ValueError("derived parameter needs a label")
        for field in ("labels", "synonyms"):
            unknown = set(getattr(self, field)) - set(self.values)
            if unknown:
                raise ValueError(f"{field} for unknown values {sorted(unknown)}")
        if self.number:
            bands = self.number.bands
            if bands[-1].max is not None or any(b.max is None for b in bands[:-1]):
                raise ValueError("only the last band may (and must) have no max")
            if [b.max for b in bands[:-1]] != sorted(b.max for b in bands[:-1]):
                raise ValueError("bands must be in increasing order")
            unknown = {b.value for b in bands} - set(self.values)
            if unknown:
                raise ValueError(f"bands use unknown values {sorted(unknown)}")
        return self


class Rule(Strict):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    if_: dict[str, str] = Field(alias="if", min_length=1)
    then: list[str] = Field(min_length=1)
    cf: float = Field(ge=-1, le=1)
    why: str = Field(min_length=1)
    source: str = Field(min_length=1)


class Goal(Strict):
    id: str
    name: str
    rank: int
    medical_name: str | None = None
    about: str | None = None
    care: list[str] = Field(default_factory=list)


class Group(Strict):
    id: str
    title: str
    policy: Literal["highest", "most_severe"]
    testing_text: str
    none_text: str | None = None
    fallback: str | None = None
    goals: list[Goal] = Field(min_length=1)


class Goals(Strict):
    groups: list[Group] = Field(min_length=1)


class Unit(Strict):
    default: str
    names: dict[str, list[str]]
    factor: dict[str, float] | None = None
    convert: dict[str, tuple[float, float]] | None = None   # unit -> (a, b): base = a*x + b
    guess: list[dict] = Field(default_factory=list)          # [{"below": n, "unit": u}] when no unit is typed


class AnswerWords(Strict):
    value: str
    certainty: float = Field(ge=0, le=1)
    words: list[str]


class CertaintyWord(Strict):
    min: float
    word: str


class DescriptionWords(Strict):
    prompt: str
    example: str
    separators: list[str]
    negations_before: list[str]
    negations_after: list[str]


class Settings(Strict):
    name: str
    disclaimer: str
    start_with: list[str] = Field(default_factory=list)
    start_text: str
    start_alert: str
    description: DescriptionWords
    certainty_words: list[CertaintyWord]
    below_words: str
    answers: dict[str, AnswerWords]
    units: dict[str, Unit]


class Option(Strict):
    name: str
    pros: list[str] = Field(min_length=1)
    cons: list[str] = Field(min_length=1)


class GoalOptions(Strict):
    options: list[Option] = Field(min_length=1)
    warning: str


class KBError(ValueError):
    pass


class KB:
    def __init__(self, folder="kb"):
        folder = Path(folder)
        load = lambda name: json.loads((folder / name).read_text(encoding="utf-8"))

        params = {pid: Param.model_validate(p) for pid, p in load("params.json").items()}
        rules = [Rule.model_validate(r) for r in load("rules.json")]
        goals = Goals.model_validate(load("goals.json"))
        settings = Settings.model_validate(load("settings.json"))
        options = {gid: GoalOptions.model_validate(o) for gid, o in load("options.json").items()}
        self._cross_check(params, rules, goals, settings, options)

        self.params = {pid: p.model_dump() for pid, p in params.items()}
        self.rules = [r.model_dump(by_alias=True) for r in rules]
        self.settings = settings.model_dump()
        self.options = {gid: o.model_dump() for gid, o in options.items()}
        self.start_with = settings.start_with

        self.groups, self.goal_info, self.group_of = [], {}, {}
        for group in goals.groups:
            g = group.model_dump()
            g["goal_ids"] = [x.id for x in sorted(group.goals, key=lambda x: x.rank)]
            self.groups.append(g)
            for goal in g["goals"]:
                self.goal_info[goal["id"]] = goal
                self.group_of[goal["id"]] = g
        self.goals = [gid for g in self.groups for gid in g["goal_ids"]]

        self.by_target = {}
        for rule in self.rules:
            for target in rule["then"]:
                self.by_target.setdefault(target, []).append(rule)
        self.rule_info = {r["id"]: r for r in self.rules}

    @staticmethod
    def _cross_check(params, rules, goals, settings, options):
        def dupes(ids):
            seen, out = set(), set()
            for i in ids:
                (out if i in seen else seen).add(i)
            return sorted(out)

        problems = []
        group_index = {g.id: i for i, gr in enumerate(goals.groups) for g in gr.goals}
        if d := dupes([r.id for r in rules]):
            problems.append(f"duplicate rule ids: {d}")
        if d := dupes([g.id for gr in goals.groups for g in gr.goals]):
            problems.append(f"duplicate goal ids: {d}")
        for gr in goals.groups:
            if d := dupes([g.rank for g in gr.goals]):
                problems.append(f"group {gr.id}: duplicate ranks {d}")
            if gr.fallback and gr.fallback not in {g.id for g in gr.goals}:
                problems.append(f"group {gr.id}: fallback {gr.fallback!r} is not one of its goals")
        if clash := group_index.keys() & params.keys():
            problems.append(f"ids used as both goal and parameter: {sorted(clash)}")

        derived = {pid for pid, p in params.items() if p.type == "derived"}
        for r in rules:
            target_groups = [group_index.get(t) for t in r.then]
            for pid, value in r.if_.items():
                if pid in params:
                    if value not in params[pid].values:
                        problems.append(f"{r.id}: {pid} has no value {value!r}")
                elif pid in group_index:
                    if value not in YES_NO:
                        problems.append(f"{r.id}: goal {pid} can only be yes/no")
                    if any(t is None or t <= group_index[pid] for t in target_groups):
                        problems.append(f"{r.id}: uses goal {pid}, so it may only conclude goals of a later group")
                else:
                    problems.append(f"{r.id}: unknown parameter {pid!r}")
            for target in r.then:
                if target not in derived and target not in group_index:
                    problems.append(f"{r.id}: concludes {target!r}, which is not a goal or derived parameter")
                elif target in derived and params[target].values != YES_NO:
                    problems.append(f"{r.id}: concludes {target!r}, which must be yes/no")

        for pid in settings.start_with:
            if pid not in derived:
                problems.append(f"start_with: {pid!r} is not a derived parameter")
        for pid, p in params.items():
            if p.number and p.number.unit not in settings.units:
                problems.append(f"{pid}: unknown unit {p.number.unit!r}")
        for name, unit in settings.units.items():
            table = unit.factor or unit.convert or {}
            if set(unit.names) != set(table) or unit.default not in table:
                problems.append(f"unit {name}: names, factor/convert and default must match")
        for word in settings.answers.values():
            if word.value not in YES_NO:
                problems.append(f"answer words must map to yes/no, not {word.value!r}")
        for gid in options:
            if gid not in group_index:
                problems.append(f"options for unknown goal {gid!r}")
        if problems:
            raise KBError("knowledge base is invalid:\n  " + "\n  ".join(problems))

    def rules_concluding(self, p):
        return self.by_target.get(p, [])

    def values(self, p):
        return self.params.get(p, {}).get("values", YES_NO)

    def is_goal(self, p):
        return p in self.goal_info

    def name(self, p):
        """Plain-language name of a goal or parameter, for explanations."""
        if p in self.goal_info:
            return self.goal_info[p]["name"]
        param = self.params[p]
        return param["label"] or param["question"]

    def word(self, cf):
        """Certainty word for a CF, e.g. 0.9 -> "definitely"."""
        for band in self.settings["certainty_words"]:
            if cf >= band["min"]:
                return band["word"]
        return self.settings["below_words"]
