# 🐱 CatCare: cat health expert system

A rule-based expert system that helps a cat owner decide what to do. It checks danger signs first, diagnoses one of three conditions, decides how urgent it is, and lays out the options with pros and cons so the owner can choose.

| Condition | Medical name | Typical urgency |
|---|---|---|
| Cat Flu | Feline upper respiratory infection | Home care to vet in 1–2 days |
| Cat Parvo | Feline panleukopenia | Vet today; emergency for kittens |
| Blocked Bladder | Urethral obstruction | Emergency |

CatCare is a course project (Intro to Artificial Intelligence), **not a vet**. Always confirm with a vet.

## How it works

- **Knowledge base** (`kb/*.json`): 24 questions, 7 intermediate facts, 58 rules, each citing its source (Cornell Feline Health Center, WSU, VCA, ASPCApro). No database: the rules are the expert system.
- **Inference engine** (`engine/`): our own backward chaining with certainty factors and a forward pass after every answer. Triage first, then the condition, then the urgency ("when unsure, more urgent").
- **Flexible input**: "102", "a hundred and two", "39.8 C", "6 months", "half a year", "since yesterday", "haan", "nahi", "ulti", typos, and a free-text description ("my kitten is vomiting & has dast, not vaccinated").
- **Certainty words**: not sure → maybe → quite possible → definitely.
- **Explanations**: Why? (during a question), How? and Why not? (at the result).
- **Decision tree**: `docs/decision_tree.md`, generated from the rules.

## Run it

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
