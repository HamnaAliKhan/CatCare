"""Certainty factor maths (MYCIN-style, range -1 to +1)."""

THRESHOLD = 0.2  # a premise counts as true above this
PRUNE = -0.5     # goals below this are no longer pursued
STOP = 0.85      # report a diagnosis at or above this


def combine(cf1, cf2):
    """Combine the current belief cf1 with new evidence cf2."""
    if cf1 >= 0 and cf2 >= 0:
        return cf1 + cf2 * (1 - cf1)
    if cf1 < 0 and cf2 < 0:
        return cf1 + cf2 * (1 + cf1)
    denom = 1 - min(abs(cf1), abs(cf2))
    return 0.0 if denom == 0 else (cf1 + cf2) / denom
