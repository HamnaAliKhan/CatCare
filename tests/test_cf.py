from pytest import approx

from engine.cf import combine


def test_both_positive():
    assert combine(0.40, 0.85) == approx(0.91)
    assert combine(0.456, 0.765) == approx(0.872, abs=1e-3)


def test_both_negative():
    assert combine(-0.6, -0.5) == approx(-0.8)


def test_opposite_signs():
    assert combine(0.0, -0.63) == approx(-0.63)
    assert combine(0.456, -0.5) == approx(-0.044 / 0.544)


def test_certain_contradiction_gives_zero():
    assert combine(1.0, -1.0) == 0.0


def test_failed_fix_stays_at_minus_one():
    assert combine(-1.0, 0.9) == approx(-1.0)
