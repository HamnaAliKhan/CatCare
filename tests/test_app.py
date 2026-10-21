"""The Streamlit app, driven headlessly: whole consultations, Back, bad input, random clicking."""

import random
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parents[1] / "app" / "streamlit_app.py")


def start():
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    return at


def quick(at, label):
    """Click the quick-answer button with this label on the current question."""
    buttons = [b for b in at.button if b.key and b.key.startswith("btn_") and b.label == label]
    assert buttons, f"no button {label!r}; question: {[s.value for s in at.subheader]}"
    buttons[0].click().run()


def question(at):
    return at.subheader[0].value if at.subheader else None


def type_answer(at, param, text):
    """Type into the question's form and press Answer in one go, as a browser would."""
    at.text_input(key=f"typed_{param}").input(text)
    [b for b in at.button if b.label == "Answer"][0].click().run()


def no_errors(at):
    assert not at.exception, [e.value for e in at.exception]


def test_description_then_emergency():
    at = start()
    at.text_area(key="description_box").input(
        "my male cat is straining in the litter box again and again, only drops of urine").run()
    at.button(key="describe_continue").click().run()
    assert len(at.checkbox) == 4
    at.button(key="confirm_start").click().run()
    for _ in range(3):
        quick(at, "No")
    no_errors(at)
    assert at.error[0].value == "**Emergency: go to a vet now**"
    at.radio[0].set_value("Nearest vet clinic, now").run()
    assert "You chose" in at.success[0].value


def test_danger_alert_appears_straight_away():
    at = start()
    at.button(key="describe_skip").click().run()
    quick(at, "Yes")                                   # struggling to breathe
    assert "Danger sign found" in at.error[0].value    # shown before the questions end
    no_errors(at)


def test_typed_answers_nonsense_and_back():
    at = start()
    at.button(key="describe_skip").click().run()
    first = question(at)
    type_answer(at, "breathing_trouble", "nahi")
    assert question(at) != first
    assert at.info[0].value == "Got it: No"
    second = question(at)
    type_answer(at, "collapsed", "asdfgh 😺")         # nonsense once -> asked again
    assert question(at) == second and "didn't understand" in at.warning[0].value
    type_answer(at, "collapsed", "qwerty")            # twice -> counted as not sure
    assert "counted that as “not sure”" in at.warning[0].value
    at.button(key="back").click().run()
    assert question(at) == second
    no_errors(at)


def test_cat_flu_home_care_and_restart():
    at = start()
    at.text_area(key="description_box").input(
        "sneezing & runny eyes, red eyes, still eating, playful, no blood").run()
    at.button(key="describe_continue").click().run()
    at.button(key="confirm_start").click().run()
    while at.button and any(b.key and b.key.startswith("btn_") for b in at.button):
        quick(at, "Not sure" if "temperature" in (question(at) or "") else "No")
    no_errors(at)
    assert at.success[0].value == "**Care at home and watch closely**"
    at.button(key="restart").click().run()
    assert at.text_area(key="description_box") is not None


@pytest.mark.parametrize("seed", range(15))
def test_random_clicking_never_breaks(seed):
    rng = random.Random(seed)
    junk = ["", "yes", "nahi", "6 months", "103 F", "😺😺", "x" * 300, "DROP TABLE", "2 days", "tom"]
    at = start()
    for _ in range(40):
        if at.text_area and rng.random() < 0.5:
            at.text_area[0].input(rng.choice(junk)).run()
        if at.text_input and rng.random() < 0.3:
            at.text_input[0].input(rng.choice(junk)).run()
        clickable = [b for b in at.button if not b.disabled]
        if not clickable:
            break
        rng.choice(clickable).click().run()
        no_errors(at)
