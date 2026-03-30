"""Tests for the resolve_location module."""

import pytest

from seo_pipeline.utils.resolve_location import resolve_location


class TestResolveLocation:
    """Tests for the resolve_location function."""

    def test_resolves_de_to_2276(self):
        """Resolves de to 2276."""
        assert resolve_location('de') == 2276

    def test_resolves_us_to_2840(self):
        """Resolves us to 2840."""
        assert resolve_location('us') == 2840

    def test_resolves_gb_to_2826(self):
        """Resolves gb to 2826."""
        assert resolve_location('gb') == 2826

    def test_handles_uppercase_input(self):
        """Handles uppercase input (DE -> 2276)."""
        assert resolve_location('DE') == 2276

    def test_handles_mixed_case_input(self):
        """Handles mixed case input (De -> 2276)."""
        assert resolve_location('De') == 2276

    def test_raises_error_for_unknown_market(self):
        """Raises ValueError for unknown market."""
        with pytest.raises(ValueError) as exc_info:
            resolve_location('zz')
        assert 'Unknown market' in str(exc_info.value)

    def test_produces_deterministic_output(self):
        """Produces deterministic output for identical input."""
        run1 = resolve_location('de')
        run2 = resolve_location('de')
        assert run1 == run2

    def test_all_supported_markets(self):
        """Tests all supported markets."""
        expected = {
            'de': 2276,
            'at': 2040,
            'ch': 2756,
            'us': 2840,
            'gb': 2826,
            'fr': 2250,
            'es': 2724,
            'it': 2380,
            'nl': 2528,
            'pl': 2616,
            'br': 2076,
            'au': 2036,
            'ca': 2124,
            'in': 2356,
            'jp': 2392,
        }
        for market, code in expected.items():
            assert resolve_location(market) == code
