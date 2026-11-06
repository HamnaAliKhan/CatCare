"""CatCare web app: streamlit run app/streamlit_app.py

Light for a slow 3G connection: a 3 KB logo and two small WebP photos (~28 KB), plus
two Google Fonts. No charts.
Like the engine, it never mentions a specific question or condition: all
wording comes from the knowledge base.
"""

import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / "app" / "assets" / "cat.webp"  # 128x128 WebP; keep it tiny for 3G
sys.path.insert(0, str(ROOT))  # find engine/

import streamlit as st  # noqa: E402

from engine import explain  # noqa: E402
from engine.cf import THRESHOLD  # noqa: E402
from engine.describe import read_description  # noqa: E402
from engine.inference import Engine, NeedAnswer  # noqa: E402
from engine.kb import KB  # noqa: E402
from engine.normalize import MAX_TRIES, AnswerError, not_sure, parse_answer  # noqa: E402

st.set_page_config(page_title="CatCare", page_icon=str(LOGO) if LOGO.exists() else "🐱",
                   layout="wide")


@st.cache_resource
def load_kb():
    return KB(ROOT / "kb")


kb = load_kb()
state = st.session_state
DEFAULTS = {"stage": "describe", "description": None, "answers": {}, "history": [],
            "misunderstood": {}, "notice": None, "text": ""}
for key, value in DEFAULTS.items():
    if key not in state:
        state[key] = value.copy() if isinstance(value, (dict, list)) else value


# ----- helpers -----
def restart():
    for key, value in DEFAULTS.items():
        state[key] = value.copy() if isinstance(value, (dict, list)) else value


def shown(param, answer):
    """How an answer reads back to the owner: "Yes", "Probably yes", "Kitten (under 1 year)"."""
    value, certainty = answer
    info = kb.params[param]
    if certainty == 0.0:
        return "Not sure"
    text = info["labels"].get(value, value.replace("_", " ").capitalize())
    return text if certainty == 1.0 else f"{text} (probably)"


def record(param, answer, notice=None):
    state.answers[param] = answer
    state.history.append(param)
    state.misunderstood.pop(param, None)
    state.notice = notice


def go_back():
    if state.history:
        state.answers.pop(state.history.pop(), None)
    elif state.description is not None:
        state.answers = {}
        state.stage = "confirm"
    state.notice = None


def lines(text):
    return text.replace("\n", "  \n")


STEPS = ["Describe", "Check", "Questions", "Result"]


def step_tracker(current):
    """A one-line 'Describe › Check › Questions › Result' guide; done steps get a tick."""
    now = STEPS.index(current)
    skipped_check = current in ("Questions", "Result") and state.description is None
    parts = []
    for i, step in enumerate(STEPS):
        if step == "Check" and skipped_check:
            parts.append(f'<span style="color:#776B63;text-decoration:line-through">{step}</span>')
        elif i < now:
            parts.append(f'<span style="color:#6B5E55">✓ {step}</span>')
        elif i == now:
            parts.append(f'<span style="color:#B4532A;font-weight:700">● {step}</span>')
        else:
            parts.append(f'<span style="color:#776B63">○ {step}</span>')
    sep = '<span style="color:#C9BFB7"> › </span>'
    st.markdown(f'<div style="font-size:0.9rem;margin:-0.25rem 0 0.75rem;line-height:1.6">'
                f'{sep.join(parts)}</div>', unsafe_allow_html=True)


def answer_buttons(param):
    """(label, answer) pairs for the quick buttons of a question."""
    info = kb.params[param]
    if info["values"] == ["yes", "no"]:
        return [(key.replace("_", " ").capitalize(), (a["value"], a["certainty"]))
                for key, a in kb.settings["answers"].items()]
    return ([(info["labels"].get(v, v), (v, 1.0)) for v in info["values"]]
            + [("Not sure", not_sure(kb, param))])


# ----- stage 1: describe -----
def describe_stage():
    words = kb.settings["description"]
    step_tracker("Describe")
    st.subheader(words["prompt"], anchor=False)
    text = st.text_area("Description", value=state.text, placeholder=words["example"],
                        max_chars=1000, label_visibility="collapsed", key="description_box")
    left, right = st.columns(2)
    if left.button("Continue", type="primary", key="describe_continue", width="stretch"):
        if not text.strip():
            # The grey example is only a placeholder: don't skip silently, say what to do.
            state.notice = ("warning", "Please describe the problem first (the grey text is only an "
                                       "example), or press **Skip, just ask me**.")
            st.rerun()
        state.text, state.notice = text, None
        state.description = read_description(kb, text)
        state.stage = "confirm"
        st.rerun()
    if right.button("Skip, just ask me", key="describe_skip", width="stretch"):
        state.description, state.stage, state.notice = None, "questions", None
        st.rerun()
    if state.notice:
        st.warning(state.notice[1])


# ----- stage 2: confirm what was understood -----
def confirm_stage():
    d = state.description
    step_tracker("Check")
    st.subheader("Here's what I understood", anchor=False)
    keep = {}
    for param, answer in d.facts.items():
        keep[param] = st.checkbox(f"{kb.params[param]['question']} **{shown(param, answer)}**",
                                  value=True, key=f"keep_{param}")
    if not d.facts:
        st.info("I couldn't pick out any signs from that. No problem: I'll ask you questions instead.")
    for param in d.conflicts:
        st.warning(f"You said different things about: *{kb.params[param]['question']}* I'll ask you.")
    if d.not_understood:
        st.caption("I didn't understand: " + "; ".join(f"“{t}”" for t in d.not_understood[:5]))
    st.caption("Untick anything that's wrong.")
    left, right = st.columns(2)
    if left.button("Start the questions", type="primary", key="confirm_start", width="stretch"):
        state.answers = {p: a for p, a in d.facts.items() if keep.get(p)}
        state.history, state.stage = [], "questions"
        st.rerun()
    if right.button("Change my description", key="confirm_edit", width="stretch"):
        state.stage = "describe"
        st.rerun()


# ----- stage 3: questions, then the result -----
def question_stage():
    engine = Engine(kb, state.answers)
    try:
        result = engine.run()
    except NeedAnswer as q:
        step_tracker("Questions")
        if any(engine.cf(p) > THRESHOLD for p in kb.start_with):
            st.error(kb.settings["start_alert"])
        ask(q)
        return
    step_tracker("Result")
    show_result(result)


def ask(q):
    param, info = q.param, kb.params[q.param]
    st.caption(f"Question {len(state.history) + 1}")
    st.subheader(info["question"], anchor=False)
    with st.expander("How do I check?"):
        st.write(info["help"])
    with st.expander("Why are you asking?"):
        st.markdown(lines(explain.why(kb, q.goals)))

    buttons = list(enumerate(answer_buttons(param)))  # keep each button's key stable
    if info["values"] == ["yes", "no"]:
        # Clear answers (Yes / No) first and large; graded answers below, "Not sure" last.
        sure = [b for b in buttons if b[1][1][1] == 1.0]
        unsure = sorted((b for b in buttons if b[1][1][1] != 1.0), key=lambda b: b[1][1][1] == 0.0)
        rows = [(sure, None), (unsure, "Not certain? Pick one of these:")]
    else:
        rows = [(buttons, None)]
    for row, caption in rows:
        if caption:
            st.caption(caption)
        columns = st.columns(max(1, min(len(row), 4)))
        for n, (i, (label, answer)) in enumerate(row):
            if columns[n % len(columns)].button(label, key=f"btn_{param}_{i}", width="stretch"):
                record(param, answer)
                st.rerun()

    with st.form(key=f"form_{param}", clear_on_submit=True):
        typed = st.text_input("Or type your answer in your own words", key=f"typed_{param}",
                              max_chars=200)
        if st.form_submit_button("Answer"):
            try:
                answer = parse_answer(kb, param, typed)
                record(param, answer, notice=("info", f"Got it: {shown(param, answer)}"))
            except AnswerError as e:
                state.misunderstood[param] = state.misunderstood.get(param, 0) + 1
                if state.misunderstood[param] < MAX_TRIES:
                    state.notice = ("warning", str(e))
                else:
                    record(param, not_sure(kb, param), notice=(
                        "warning", "I still couldn't understand, so I counted that as “not sure”. "
                                   "Press Back to answer it again."))
            st.rerun()

    if state.notice:
        kind, text = state.notice
        (st.warning if kind == "warning" else st.info)(text)
    if state.history or state.description is not None:
        st.button("Back", key="back", on_click=go_back)
    if state.answers:
        with st.expander(f"Your answers so far ({len(state.answers)})"):
            answers_list()


def answers_list():
    """Every answer given so far, marking the ones taken from the description."""
    from_text = state.description.facts if state.description else {}
    for param, answer in state.answers.items():
        note = " *(from your description)*" if param in from_text and param not in state.history else ""
        st.markdown(f"- {kb.params[param]['question']} **{shown(param, answer)}**{note}")


def show_result(result):
    state.notice = None
    # Decisions (urgency) first: they matter most. Then diagnoses.
    groups = sorted(kb.groups, key=lambda g: g["policy"] != "most_severe")
    for group in groups:
        outcome = result.groups[group["id"]]
        if group["policy"] == "most_severe":
            show_decision(group, outcome)
        else:
            show_diagnosis(group, outcome)
    show_options(result)
    show_explanations(result)
    st.divider()
    left, right = st.columns(2)
    left.button("Back (change last answer)", key="result_back", on_click=go_back,
                width="stretch")
    right.button("Start again", key="restart", on_click=restart, type="primary",
                 width="stretch")
    st.caption(kb.settings["disclaimer"])


def show_decision(group, outcome):
    name = kb.name(outcome.decision)
    rank = group["goal_ids"].index(outcome.decision)
    box, icon = [(st.error, "🚨"), (st.warning, "⚠️"), (st.info, "🩺")][rank] if rank < 3 else (st.success, "🏠")
    # The decision in bold (a ### heading would bring back Streamlit's link icon), with the
    # knowledge base's "act sooner if…" line under it.
    warning = kb.options.get(outcome.decision, {}).get("warning")
    box(f"**{name}**" + (f"\n\n{warning}" if warning else ""), icon=icon)


def show_diagnosis(group, outcome):
    st.subheader(group["title"], anchor=False)
    if outcome.kind == "none":
        st.info(group["none_text"])
        return
    for goal, cf in outcome.ranking:
        st.progress(min(max(cf, 0.0), 1.0), text=f"**{kb.name(goal)}**: {kb.word(cf)}")
    info = kb.goal_info[outcome.decision]
    if info.get("about"):
        st.markdown(f"**About {info['name']}** ({info.get('medical_name', '')}): {info['about']}")
    for step in info.get("care", []):
        st.markdown(f"- {step}")


def show_options(result):
    decisions = [result.groups[g["id"]].decision for g in kb.groups if g["policy"] == "most_severe"]
    for decision in decisions:
        options = kb.options.get(decision)
        if not options:
            continue
        st.subheader("Your options: you decide", anchor=False)
        for option in options["options"]:
            with st.container(border=True):
                st.markdown(f"**{option['name']}**")
                st.markdown("  \n".join([f"✅ {p}" for p in option["pros"]]
                                        + [f"⚠️ {c}" for c in option["cons"]]))
        names = [o["name"] for o in options["options"]]
        choice = st.radio("Which will you do?", names, index=None, key=f"choice_{decision}")
        if choice:
            st.success(f"You chose: **{choice}**.")


def show_explanations(result):
    with st.expander("How did CatCare decide?"):
        st.text(explain.how(kb, result))
    diagnosis_goals = [g for group in kb.groups if group["policy"] == "highest"
                       for g in group["goal_ids"]]
    with st.expander("Why not something else?"):
        goal = st.selectbox("Why not…", diagnosis_goals, format_func=kb.name, key="why_not")
        st.markdown(lines(explain.why_not(kb, result, goal)))
    with st.expander("Your answers"):
        answers_list()


# ----- page -----
def title():
    """The name with the round logo beside it (stays on one line on phones)."""
    name = kb.settings["name"]
    if not LOGO.exists():
        st.title(f"🐱 {name}", anchor=False)
        return
    logo = base64.b64encode(LOGO.read_bytes()).decode()
    st.markdown(
        '<div style="display:flex;align-items:center;gap:1rem;margin:0.5rem 0 0.75rem">'
        f'<img src="data:image/webp;base64,{logo}" alt="" '
        'style="width:4.5rem;height:4.5rem;border-radius:50%;object-fit:cover">'
        f'<span style="font-family:Fredoka,sans-serif;font-size:2.7rem;font-weight:600;'
        f'line-height:1">{name}</span></div>',
        unsafe_allow_html=True)


# Wide layout, but never wider than is comfortable to read on a laptop.
PAGE_CSS = """<style>
[data-testid="stMainBlockContainer"] { max-width: 1100px; padding-top: 2.5rem; }
[data-testid="stImage"] img { border-radius: 0.75rem; }
[data-testid="stCaptionContainer"] { opacity: 1; }  /* Streamlit fades captions to 60% */
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: #4F443D; }
</style>"""

# Small WebP photos (about 28 KB together) so the app stays quick on 3G.
PICTURES = {"start": ROOT / "app" / "assets" / "kittens.webp",
            "consult": ROOT / "app" / "assets" / "calico.webp"}


def side_panel():
    """Right-hand panel on laptops (drops below the consultation on phones)."""
    picture = PICTURES["start" if state.stage in ("describe", "confirm") else "consult"]
    if picture.exists():
        st.image(str(picture), width="stretch")
    with st.container(border=True):
        st.markdown("**How CatCare works**")
        st.markdown("1. Tell it what's wrong, in your own words.\n"
                    "2. Check what it understood.\n"
                    "3. Answer a few questions (danger signs first).\n"
                    "4. Get the urgency, the likely condition and your options.")
        st.caption("You can answer in English or Roman Urdu, and say “not sure” to any question.")


st.markdown(PAGE_CSS, unsafe_allow_html=True)
title()
st.caption(kb.settings["disclaimer"])
main, side = st.columns([2, 1], gap="large")
with main:
    {"describe": describe_stage, "confirm": confirm_stage, "questions": question_stage}[state.stage]()
with side:
    side_panel()
