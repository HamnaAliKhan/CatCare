"""The CLI must reach a result whatever is typed: nonsense, emoji, empty lines."""

import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]


def run_cli(lines):
    return subprocess.run([sys.executable, "cli.py"], cwd=ROOT, input="\n".join(lines) + "\n",
                          capture_output=True, text=True, encoding="utf-8", timeout=60)


def test_only_nonsense_still_reaches_a_result():
    junk = ["asdfgh", "😺😺😺", "", "!!!", "DROP TABLE cats;", "x" * 500, "-1e999", "<script>"]
    out = run_cli(junk * 20)
    assert out.returncode == 0, out.stderr
    assert "===" in out.stdout                       # the urgency headline was shown
    assert "count this as \"not sure\"" in out.stdout
    assert "Traceback" not in out.stdout + out.stderr


def test_random_mix_of_real_and_nonsense_answers():
    rng = random.Random(3)
    words = ["yes", "no", "haan", "nahi", "not sure", "probably", "6 months", "102 F", "back",
             "why", "help", "???", "🙂", "lorem ipsum", "", "tom", "not eating", "2 days"]
    for _ in range(5):
        out = run_cli([rng.choice(words) for _ in range(300)])
        assert out.returncode == 0, out.stderr
        assert "Traceback" not in out.stdout + out.stderr
