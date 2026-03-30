"""Tests for the slugify utility function."""

import pytest

from seo_pipeline.utils.slugify import slugify


class TestCoreTransforms:
    """Test core slug transformation behavior."""

    def test_converts_spaces_to_hyphens_and_lowercases(self):
        """Spaces should become hyphens and text should be lowercased."""
        assert slugify('thailand urlaub') == 'thailand-urlaub'

    def test_replaces_ae_oe_ue_umlauts(self):
        """Lowercase German umlauts should be transliterated correctly."""
        assert slugify('schönste Strände Thailand') == 'schoenste-straende-thailand'

    def test_replaces_uppercase_umlauts(self):
        """Uppercase German umlauts should be transliterated correctly."""
        assert slugify('Ärger Öffnung Übung') == 'aerger-oeffnung-uebung'

    def test_replaces_eszett_with_ss(self):
        """German Eszett (ß) should be replaced with 'ss'."""
        assert slugify('Straße') == 'strasse'

    def test_handles_mixed_german_and_english_input(self):
        """Mixed German and English text should be handled correctly."""
        assert slugify('Urlaub Mallorca') == 'urlaub-mallorca'


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_returns_empty_string_for_empty_input(self):
        """Empty string input should return empty string."""
        assert slugify('') == ''

    def test_returns_empty_string_for_non_string_input(self):
        """Non-string inputs should return empty string."""
        assert slugify(None) == ''  # type: ignore
        assert slugify(42) == ''  # type: ignore
        assert slugify(3.14) == ''  # type: ignore
        assert slugify([]) == ''  # type: ignore
        assert slugify({}) == ''  # type: ignore

    def test_returns_empty_string_when_input_is_only_special_characters(self):
        """Input with only special characters should return empty string."""
        assert slugify('!!!@@@###$$$') == ''

    def test_handles_numeric_only_input(self):
        """Numeric input should be preserved."""
        assert slugify('2026') == '2026'
        assert slugify('123 456') == '123-456'

    def test_collapses_consecutive_hyphens(self):
        """Consecutive special characters should collapse into a single hyphen."""
        assert slugify('a   b') == 'a-b'
        assert slugify('a---b') == 'a-b'
        assert slugify('a - b') == 'a-b'

    def test_trims_leading_and_trailing_hyphens(self):
        """Leading and trailing hyphens should be removed."""
        assert slugify('--hello--') == 'hello'
        assert slugify(' hello ') == 'hello'

    def test_is_idempotent(self):
        """Re-slugifying should produce the same result (idempotence)."""
        once = slugify('schönste Strände Thailand')
        twice = slugify(once)
        assert once == twice


class TestDeterminism:
    """Test deterministic behavior."""

    def test_produces_identical_output_across_multiple_calls(self):
        """Multiple calls with the same input should produce identical output."""
        input_text = 'AI-driven Development & SEO Reporting 2026'
        results = [slugify(input_text) for _ in range(100)]
        assert len(set(results)) == 1, 'all 100 calls must return the same value'


class TestRegressionExistingDirectoryNames:
    """Regression tests against existing directory names."""

    @pytest.mark.parametrize('input_text,expected', [
        ('thailand urlaub', 'thailand-urlaub'),
        ('schönste Strände Thailand', 'schoenste-straende-thailand'),
        ('keyword recherche', 'keyword-recherche'),
        ('Urlaub Mallorca', 'urlaub-mallorca'),
        ('AI-driven development', 'ai-driven-development'),
        ('SEO Reporting', 'seo-reporting'),
    ])
    def test_regression_cases(self, input_text: str, expected: str):
        """Verify existing directory name slugifications are preserved."""
        assert slugify(input_text) == expected
