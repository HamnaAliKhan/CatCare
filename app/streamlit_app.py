"""CatCare web app: streamlit run app/streamlit_app.py

Text only apart from a 3 KB logo, so it loads on a slow 3G connection.
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
                   layout="centered")


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
    st.subheader(words["prompt"], anchor=False)
    text = st.text_area("Description", value=state.text, placeholder=words["example"],
                        max_chars=1000, label_visibility="collapsed", key="description_box")
    left, right = st.columns(2)
    if left.button("Continue", type="primary", key="describe_continue", width="stretch"):
        state.text = text
        state.description = read_description(kb, text)
        state.stage = "confirm" if text.strip() else "questions"
        st.rerun()
    if right.button("Skip, just ask me", key="describe_skip", width="stretch"):
        state.description, state.stage = None, "questions"
        st.rerun()


# ----- stage 2: confirm what was understood -----
def confirm_stage():
    d = state.description
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
        if any(engine.cf(p) > THRESHOLD for p in kb.start_with):
            st.error(kb.settings["start_alert"])
        ask(q)
        return
    show_result(result)


def ask(q):
    param, info = q.param, kb.params[q.param]
    st.caption(f"Question {len(state.history) + 1}")
    st.subheader(info["question"], anchor=False)
    with st.expander("How do I check?"):
        st.write(info["help"])
    with st.expander("Why are you asking?"):
        st.markdown(lines(explain.why(kb, q.goals)))

    buttons = answer_buttons(param)
    columns = st.columns(3)
    for i, (label, answer) in enumerate(buttons):
        if columns[i % 3].button(label, key=f"btn_{param}_{i}", width="stretch"):
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
    box(f"**{name}**", icon=icon)


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
        st.warning(options["warning"])


def show_explanations(result):
    with st.expander("How did CatCare decide?"):
        st.text(explain.how(kb, result))
    diagnosis_goals = [g for group in kb.groups if group["policy"] == "highest"
                       for g in group["goal_ids"]]
    with st.expander("Why not something else?"):
        goal = st.selectbox("Why not…", diagnosis_goals, format_func=kb.name, key="why_not")
        st.markdown(lines(explain.why_not(kb, result, goal)))
    with st.expander("Your answers"):
        from_text = state.description.facts if state.description else {}
        for param, answer in state.answers.items():
            note = " *(from your description)*" if param in from_text and param not in state.history else ""
            st.markdown(f"- {kb.params[param]['question']} **{shown(param, answer)}**{note}")


# ----- page -----
def title():
    """The name with the round logo beside it (stays on one line on phones)."""
    name = kb.settings["name"]
    if not LOGO.exists():
        st.title(f"🐱 {name}", anchor=False)
        return
    logo = base64.b64encode(LOGO.read_bytes()).decode()
    st.markdown(
        '<div style="display:flex;align-items:center;gap:0.8rem;margin:0.5rem 0 0.75rem">'
        f'<img src="data:image/webp;base64,{logo}" alt="" '
        'style="width:3.4rem;height:3.4rem;border-radius:50%;object-fit:cover">'
        f'<span style="font-size:2.4rem;font-weight:700;line-height:1">{name}</span></div>',
        unsafe_allow_html=True)


title()
st.caption(kb.settings["disclaimer"])
{"describe": describe_stage, "confirm": confirm_stage, "questions": question_stage}[state.stage]()
