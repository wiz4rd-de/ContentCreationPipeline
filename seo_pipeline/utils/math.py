"""Math utilities for the SEO Pipeline."""

import math


def normalize_number(value: int | float | None) -> int | float | None:
    """Convert whole-number floats to int for JSON serialization parity with Node.js.

    JavaScript's JSON.stringify renders 4.0 as 4. Python's json.dumps renders
    4.0 as 4.0. This normalizes so Python output matches Node.js byte-for-byte.
    """
    if isinstance(value, float) and value == int(value) and not (value != value):
        return int(value)
    return value


def js_round(x: float) -> int:
    """
    Round a float using JavaScript Math.round() semantics.

    JavaScript's Math.round() uses "half away from zero" rounding:
    - Math.round(0.5) = 1
    - Math.round(-0.5) = 0
    - Math.round(1.5) = 2

    Python's built-in round() uses banker's rounding (round-to-even):
    - round(0.5) = 0
    - round(1.5) = 2

    This function implements JavaScript semantics by computing floor(x + 0.5).

    Args:
        x: the float to round

    Returns:
        The rounded integer value using JavaScript semantics
    """
    return math.floor(x + 0.5)
