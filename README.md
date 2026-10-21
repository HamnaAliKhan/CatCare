<img src="app/assets/cat.webp" alt="CatCare logo" width="96" align="right">

# CatCare: cat health expert system

**Live app: https://catcare.streamlit.app/**

A rule-based expert system that helps a cat owner decide what to do. It checks danger signs first, diagnoses one of three conditions, decides how urgent it is, and lays out the options with pros and cons so the owner can choose.

| Condition | Medical name | Typical urgency |
|---|---|---|
| Cat Flu | Feline upper respiratory infection | Home care to vet in 1–2 days |
| Cat Parvo | Feline panleukopenia | Vet today; emergency for kittens |
| Blocked Bladder | Urethral obstruction | Emergency |

CatCare is a course project (Intro to Artificial Intelligence), **not a vet**. Always confirm with a vet.

## Using the app

1. **Describe the problem** in your own words, or skip. For example: *"my 4 month old kitten is vomiting & has diarrhea, not vaccinated, not eating since yesterday"*.
2. **Check what CatCare understood** and untick anything wrong.
3. **Answer the remaining questions** with the buttons (Yes / Probably / Maybe / Not sure / Probably not / No) or in your own words. Each question has *How do I check?* and *Why are you asking?*. **Back** undoes the last answer.
4. **Read the result**: what to do (Emergency / vet today / vet in 1–2 days / home care), the most likely condition with a certainty word, care steps, and **your options with pros and cons**. Choose one. *How did CatCare decide?* and *Why not something else?* explain the reasoning.

## How it works

```
 description / answers ──► normaliser ──► inference engine ◄── knowledge base (kb/*.json)
  "102 F", "haan", "&"     (flexible       triage → condition      58 rules, 24 questions,
                            input)          → urgency               7 intermediate facts
                                               │
                                               ▼
                       urgency + condition + certainty word + options + explanations
```

- **Knowledge base** (`kb/*.json`): questions, synonyms, units, rules, conditions, urgency levels and options are all data. Every rule cites its source (Cornell Feline Health Center, WSU Veterinary Hospital, VCA, ASPCApro). No database: the rules are the expert system.
- **Inference engine** (`engine/`): our own code, no rule-engine library. Backward chaining with certainty factors, plus a forward pass after every answer. Danger signs are checked first; when unsure, the more urgent advice wins.
- **The question order is not hard-coded**: it comes from the rules and the answers so far, so different cats get different questions.

## The instructor's requirements

| Requirement | Where it's met |
|---|---|
| At least 50 rules, 2–3 conditions | 58 rules in `kb/rules.json`; Cat Flu, Cat Parvo, Blocked Bladder |
| Python, declarative (knowledge base + inference), no database | `kb/*.json` + `engine/inference.py` |
| Rule order and hierarchy; a decision tree | Triage → condition → urgency; tree generated from the rules in [`docs/decision_tree.md`](docs/decision_tree.md) |
| Flexible input ("100", "hundred", "100°F", "&", synonyms) | `engine/normalize.py`, `engine/describe.py`: number words, °F/°C, months/years/days, "and"/"&"/"aur", Roman Urdu ("haan", "ulti", "khana nahi kha rahi"), typos |
| Certainty: not sure → maybe → quite possible → definitely | `kb/settings.json` certainty words |
| Incomplete, redundant, wrong input; must not fail | "Not sure" anywhere; repeated facts kept once; contradictions asked again; nonsense twice → counted as "not sure"; fuzz-tested |
| Decision making and decision support | The urgency decision and condition, plus options with pros and cons that the owner chooses from (`kb/options.json`) |
| Streamlit, live, light enough for 3G | https://catcare.streamlit.app/, text only apart from a 3 KB logo |

## Project layout

```
kb/                knowledge base (settings, params, goals, rules, options)
engine/            cf.py, kb.py, inference.py, normalize.py, describe.py, explain.py
app/               streamlit_app.py and the logo
tools/             kb_check.py (finds knowledge-base mistakes), draw_tree.py (decision tree)
tests/             152 tests: scenarios, input forms, descriptions, the app, fuzzing
docs/              design plan, source checks and change log, decision tree
cli.py             text version of the app
```

## Run it locally

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt

streamlit run app/streamlit_app.py   # the web app
python cli.py                        # text version
python -m pytest                     # all tests
python tools/kb_check.py             # check the knowledge base
python tools/draw_tree.py            # redraw docs/decision_tree.md
```

## Deploy

On [Streamlit Community Cloud](https://share.streamlit.io): New app → this repository → branch `main` → main file `app/streamlit_app.py`. `requirements.txt` holds only what the app needs.

## Sources

- [Cornell Feline Health Center: Respiratory infections](https://www.vet.cornell.edu/departments-centers-and-institutes/cornell-feline-health-center/health-information/feline-health-topics/respiratory-infections)
- [Cornell Feline Health Center: Feline lower urinary tract disease](https://www.vet.cornell.edu/departments-centers-and-institutes/cornell-feline-health-center/health-information/feline-health-topics/feline-lower-urinary-tract-disease)
- [WSU Veterinary Teaching Hospital: Feline panleukopenia virus](https://hospital.vetmed.wsu.edu/2026/03/02/feline-panleukopenia-virus-fpv-in-cats/)
- [VCA Hospitals: Feline Panleukopenia](https://vcahospitals.com/know-your-pet/feline-panleukopenia)
- [ASPCApro: Feline Panleukopenia](https://www.aspcapro.org/node/104430)

Which claims were checked, and every rule change, are in [`docs/kb_changes.md`](docs/kb_changes.md).
