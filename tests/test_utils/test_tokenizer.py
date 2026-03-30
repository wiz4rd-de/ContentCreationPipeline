"""Tests for the tokenizer module."""

from seo_pipeline.utils.tokenizer import (
    load_stopword_set,
    remove_stopwords,
    tokenize,
)


class TestTokenize:
    """Test cases for the tokenize function."""

    def test_lowercases_input(self) -> None:
        """Test that input is lowercased."""
        assert tokenize("Hello WORLD") == ["hello", "world"]

    def test_preserves_german_umlauts(self) -> None:
        """Test that German umlauts are preserved."""
        result = tokenize("aerzte für übergewicht")
        assert "für" in result, '"für" must be preserved'
        assert "übergewicht" in result, '"übergewicht" must be preserved'

    def test_replaces_punctuation_with_spaces(self) -> None:
        """Test that punctuation is replaced with spaces."""
        assert tokenize("hello, world! test.") == ["hello", "world", "test"]

    def test_filters_tokens_with_length_lte_1(self) -> None:
        """Test that tokens with length <= 1 are filtered."""
        assert tokenize("a b cd ef") == ["cd", "ef"]

    def test_returns_empty_array_for_empty_string(self) -> None:
        """Test that empty string returns empty list."""
        assert tokenize("") == []

    def test_returns_empty_array_for_punctuation_only(self) -> None:
        """Test that punctuation-only input returns empty list."""
        assert tokenize("!!! ... ???") == []

    def test_handles_multiple_whitespace(self) -> None:
        """Test that multiple whitespace is handled correctly."""
        assert tokenize("  hello   world  ") == ["hello", "world"]

    def test_handles_digits_and_alphanumeric(self) -> None:
        """Test that digits and alphanumeric tokens are handled."""
        assert tokenize("test123 42 hello") == ["test123", "42", "hello"]


class TestRemoveStopwords:
    """Test cases for the remove_stopwords function."""

    def test_filters_stopwords_from_token_list(self) -> None:
        """Test that stopwords are filtered from tokens."""
        assert (
            remove_stopwords(["hello", "und", "world"], {"und"})
            == ["hello", "world"]
        )

    def test_returns_all_tokens_when_no_stopwords_match(self) -> None:
        """Test that all tokens are returned when no stopwords match."""
        assert (
            remove_stopwords(["hello", "world"], {"xyz"})
            == ["hello", "world"]
        )

    def test_returns_empty_array_when_all_tokens_are_stopwords(self) -> None:
        """Test that empty list is returned when all tokens are stopwords."""
        assert remove_stopwords(["und", "der"], {"und", "der"}) == []

    def test_works_with_empty_token_array(self) -> None:
        """Test that empty token array returns empty list."""
        assert remove_stopwords([], {"und"}) == []


class TestLoadStopwordSet:
    """Test cases for the load_stopword_set function."""

    def test_returns_a_set_for_de(self) -> None:
        """Test that 'de' language returns a Set."""
        result = load_stopword_set("de")
        assert isinstance(result, set), "must return a Set instance"
        assert len(result) > 0, "DE set must not be empty"

    def test_de_set_includes_both_de_and_en_stopwords(self) -> None:
        """Test that DE set includes both DE and EN stopwords."""
        result = load_stopword_set("de")
        assert "und" in result, 'DE set must contain "und" (German stopword)'
        assert (
            "the" in result
        ), 'DE set must contain "the" (English stopword, merged for de)'

    def test_en_set_includes_en_stopwords_not_de_only(self) -> None:
        """Test that EN set includes EN but not DE-only stopwords."""
        result = load_stopword_set("en")
        assert "the" in result, 'EN set must contain "the"'
        assert "und" not in result, 'EN set must not contain "und" (DE-only stopword)'

    def test_returns_empty_set_for_unknown_language(self) -> None:
        """Test that unknown language returns empty Set."""
        result = load_stopword_set("xx")
        assert isinstance(result, set), "must return a Set instance"
        assert len(result) == 0, "unknown language must yield empty Set"


class TestDeterminism:
    """Test cases for determinism across function calls."""

    def test_tokenize_produces_identical_output_on_repeated_calls(self) -> None:
        """Test that tokenize is deterministic across repeated calls."""
        input_text = "Aerzte für Übergewicht und Ernährung"
        results = ["|".join(tokenize(input_text)) for _ in range(50)]
        unique = set(results)
        assert len(unique) == 1, "tokenize must be deterministic across 50 calls"

    def test_load_stopword_set_returns_same_contents_on_repeated_calls(self) -> None:
        """Test that load_stopword_set returns same contents on repeated calls."""
        s1 = load_stopword_set("de")
        s2 = load_stopword_set("de")
        assert s1 == s2, "Set contents must be identical across calls"
