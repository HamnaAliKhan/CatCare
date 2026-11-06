# CatCare: Cat Health Expert System

Course project (Intro to Artificial Intelligence, CCP). A rule-based expert system that helps a cat owner decide what to do: it checks danger signs, diagnoses one of three conditions (Cat Flu, Cat Parvo, Blocked Bladder), decides the urgency, and lays out options with pros and cons. The design and its reasoning are in `docs/catcare_plan.md`; this file holds what you need while coding. (The folder is still called NetFix: the project started as a network-fault system; that version is in git history up to commit `3ddbb2d`.)

## Instructor's requirements (all must hold)

- At least **50 rules**; 2–3 conditions (medical-style domain). Currently 58 rules, 3 conditions.
- Python, structured declaratively: knowledge base + our own inference engine. **No database as the expert system.**
- **Flexible input**: "100", "hundred", "100°F", "39 C", "and"/"&", synonyms (incl. Roman Urdu).
- **Certainty words**, not just yes/no: not sure → maybe → quite possible → definitely.
- **Robust**: incomplete, redundant and garbage input must never crash it.
- **Decision making** (urgency + condition) **and decision support** (options with pros/cons; the owner decides).
- Be able to explain the rule order and hierarchy, and show the decision tree the rules produce.
- **Streamlit, deployed live** (not localhost), light enough for 3G.

## Non-negotiable design rules

- **Knowledge is data, not code.** Questions, synonyms, units, bands, rules, goals, options and wording live in `kb/*.json`. The engine and normaliser never mention a specific question, condition or rule ID. Adding a condition must need no code change. (Only English number words are built into `normalize.py`.)
- **No hard-coded question order.** The next question comes from backward chaining over current beliefs.
- **The engine is a pure function of the answers so far.** `Engine(kb, answers).run()` returns a `Result` or raises `NeedAnswer(param, goals)`. It never calls `input()`. Every UI re-runs it with one more answer (this gives Back for free).
- **Never claim certainty without "see a vet".** Every result shows the disclaimer. Danger signs always lead to Emergency.
- **Nothing unvalidated reaches the engine.** All typed input goes through `parse_answer`, which returns `(value, certainty)` or raises `AnswerError` with a helpful message.
- **A consultation can never get stuck.** After `MAX_TRIES` (2) answers it can't understand, a UI treats the question as `not_sure(kb, param)` and carries on (Back lets the user answer again). Every UI must do this, and `tests/test_cli.py` checks it with nonsense-only input.
- **Understanding is phrase-based, not free NLP**: exact phrase (longest first), then the same with spaces removed ("standup"), then a close match for typos (5+ letters, difflib cutoff 0.85). New ways of saying things go in the question's `synonyms`, not in code.
- **No rule-engine libraries** (experta, CLIPS, PyKE).
- **Never invent medical facts.** Every rule has a `source`; claims not found in a source are marked as a "safety rule" and justified in the report. Record verification in `docs/kb_changes.md`.

## Layout

```
kb/settings.json      start_with (triage), start_alert, description words (separators, negations), certainty words, answer words, units, disclaimer
kb/params.json        24 questions (short, help, why, values, labels, synonyms, number bands, text_cues) + 7 derived facts
kb/goals.json         goal groups in order: condition (policy highest), urgency (policy most_severe, fallback vet_soon)
kb/rules.json         58 rules: id, if, then, cf, why, source  — ORDER MATTERS
kb/options.json       decision support: options with pros/cons + warning, per urgency goal
engine/cf.py          combine() + THRESHOLD, PRUNE, STOP
engine/kb.py          Pydantic-validated loader + cross-checks; word(cf), name(), group_of
engine/inference.py   Engine, NeedAnswer, Result, GroupResult
engine/normalize.py   parse_answer(): flexible input -> (value, certainty); not_sure(); MAX_TRIES
engine/describe.py    read_description(): free text -> facts, conflicts, not understood
engine/explain.py     Why? / How? / Why not?
app/streamlit_app.py  web app: describe -> confirm -> questions -> result + options (light, for 3G)
tools/kb_check.py     knowledge-base checker
tools/draw_tree.py    writes docs/decision_tree.md (Mermaid) + .txt from the rules
cli.py                text UI for fast testing
tests/                cf, normalize, describe, scenarios, explain, kb_check, cli, app (AppTest), draw_tree
docs/catcare_plan.md  design plan;  docs/kb_changes.md  verification + change log
requirements.txt      deploy deps only (streamlit, pydantic); requirements-dev.txt adds pytest
.streamlit/config.toml  no usage stats, minimal toolbar, light theme
```

Run from the project root inside the venv (`.venv\Scripts\activate`): `streamlit run app/streamlit_app.py`, `python cli.py`, `python -m pytest`, `python tools/kb_check.py`, `python tools/draw_tree.py`. `pytest.ini` puts the project root on the import path. Re-run `draw_tree.py` after changing rules so the diagram stays current.

App notes: `AppTest` paths must be absolute (`tests/test_app.py` builds one from `__file__`); in a form, set the text input and click submit before calling `.run()`. Streamlit's own JS is ~2 MB on first load; keep CatCare's own additions small: a 3 KB logo, two WebP photos (~28 KB together, in `app/assets/`), two Google Fonts set in `.streamlit/config.toml`, and no charts. Compress any new picture to WebP under ~30 KB.

## Knowledge base format

- **Parameters**: `askable` or `derived`. Yes/no by default; `values` + `labels` for categories (sex, appetite). Numeric questions (age, temperature, hours_since_ate) have `number: {unit, range, bands}`: typed numbers are converted to the unit's base (months, °F, hours) and sorted into band values, so rules stay categorical. `synonyms` per value; an entry may be `[phrase, certainty]` ("feels hot" = high at 0.6).
- **Rules**: `{"id", "if": {param: value}, "then": [targets], "cf", "why", "source"}`. Conclusions are on "yes"; negative CF counts against. A rule may use a **goal of an earlier group** as a premise (urgency rules use conditions); the loader enforces this.
- **Rule order is meaningful** (file order = order tried), and so is **premise order** within a rule (premises are established left to right and the rule stops at the first false one). Put cheap/known premises first so needless questions aren't asked.
- **Goal groups** run in order after `start_with`. `highest`: diagnosis ≥ 0.85, else differential, else "none". `most_severe`: the first goal in rank order with CF > 0.2, else `fallback` ("when unsure, more urgent").

## Certainty factor maths

- Answers: Yes 1.0, Probably 0.6, Maybe 0.4, Not sure 0.0, Probably not = "no" at 0.6, No 1.0. Storing (p, v) = c stores every other value of p at −c.
- A premise holds only if its CF > `THRESHOLD = 0.2`. Rule strength = rule CF × min(premise CFs).
- Combine: both ≥ 0 → a + b(1 − a); both < 0 → a + b(1 + a); else (a + b) / (1 − min(|a|, |b|)), 0 if the denominator is 0.
- `PRUNE = -0.5`, `STOP = 0.85`. Certainty words: ≥ 0.85 definitely, ≥ 0.6 quite possible, ≥ 0.4 maybe, ≥ 0.2 not sure, else unlikely.
- Watch out for "no danger" style rules: a negative rule that fires early can cancel later positive evidence. R5/R58 only fire when *all* danger checks are clear for this reason.

## Engine loop

1. Establish every `start_with` fact (triage: `danger_sign`).
2. For each goal group in order: run its policy (backward chaining on the best/most severe alive goal's next untried rule; one question at a time).
3. After every new fact, forward-fire every rule whose premises are all established and true; fired rules are also marked tried.
4. After a group finishes, its goals become known facts for later groups.

## Tests that must always pass

- `tests/scenarios/*.json`: each condition reaches **definitely (≥ 0.85)** on its clean path; blocked male → Emergency in exactly 6 questions; a collapsed cat with no known condition → Emergency; passing urine → not Blocked Bladder; all "not sure" → no crash, vet_soon; Roman Urdu answers work.
- Danger signs are asked first; 500 random owners always get an urgency decision; 3000 random strings never crash `parse_answer`.
- `kb_check` reports 0 problems; at least 50 rules.

If you change a CF, a premise or rule order: re-run the scenarios and log it in `docs/kb_changes.md`.

## Gotchas

- A question's own synonyms win over general answer words on a tie: "none" means **yes** to "passing little or no urine?".
- One-word synonyms must match exactly; multi-word phrases and answer words may start a longer answer ("yes, a lot", "not eating since yesterday"). Otherwise "hot dog stand" would read as a fever.
- Temperatures with no unit are guessed: below 50 = °C, else °F. Ages with no unit are years.
## Conventions

- Python 3.11+ (venv is 3.14), standard library + streamlit, pydantic, pytest.
- Keep `engine/` UI-independent; no Streamlit imports there.
- User-facing text: plain words, one question at a time, every question has a "how to check" help line.
