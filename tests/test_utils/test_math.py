"""Tests for the math utility module."""

from seo_pipeline.utils.math import js_round


class TestJsRound:
    """Tests for the js_round function."""

    def test_js_round_positive_half(self):
        """js_round(0.5) should return 1, matching JavaScript behavior."""
        assert js_round(0.5) == 1

    def test_js_round_negative_half(self):
        """js_round(-0.5) should return 0, matching JavaScript behavior."""
        assert js_round(-0.5) == 0

    def test_js_round_1_5(self):
        """js_round(1.5) should return 2."""
        assert js_round(1.5) == 2

    def test_js_round_2_5(self):
        """js_round(2.5) should return 3."""
        assert js_round(2.5) == 3

    def test_js_round_negative_1_5(self):
        """js_round(-1.5) should return -1."""
        assert js_round(-1.5) == -1

    def test_js_round_negative_2_5(self):
        """js_round(-2.5) should return -2."""
        assert js_round(-2.5) == -2

    def test_js_round_positive_integers(self):
        """js_round should handle positive integers."""
        assert js_round(1.0) == 1
        assert js_round(2.0) == 2
        assert js_round(100.0) == 100

    def test_js_round_negative_integers(self):
        """js_round should handle negative integers."""
        assert js_round(-1.0) == -1
        assert js_round(-2.0) == -2
        assert js_round(-100.0) == -100

    def test_js_round_zero(self):
        """js_round(0) should return 0."""
        assert js_round(0.0) == 0
        assert js_round(0) == 0

    def test_js_round_quarter_values(self):
        """js_round should round quarter values correctly."""
        assert js_round(1.25) == 1
        assert js_round(1.75) == 2
        assert js_round(2.25) == 2
        assert js_round(2.75) == 3

    def test_js_round_differs_from_python_round(self):
        """
        js_round should differ from Python's round() for .5 values.

        Python uses banker's rounding (round-to-even):
        - round(0.5) = 0
        - round(1.5) = 2

        JavaScript uses half-away-from-zero:
        - Math.round(0.5) = 1
        - Math.round(1.5) = 2
        """
        assert js_round(0.5) == 1
        assert round(0.5) == 0  # Python's banker's rounding
        assert js_round(2.5) == 3
        assert round(2.5) == 2  # Python's banker's rounding

    def test_js_round_very_small_positive(self):
        """js_round should handle very small positive numbers."""
        assert js_round(0.1) == 0
        assert js_round(0.4) == 0
        assert js_round(0.49) == 0
        assert js_round(0.51) == 1

    def test_js_round_very_small_negative(self):
        """js_round should handle very small negative numbers."""
        assert js_round(-0.1) == 0
        assert js_round(-0.4) == 0
        assert js_round(-0.49) == 0
        assert js_round(-0.51) == -1
