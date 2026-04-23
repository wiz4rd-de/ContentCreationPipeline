"""Tests for the text utility module."""

from seo_pipeline.utils.text import FOREIGN_RE, is_foreign_language


class TestForeignRe:
    """Tests for the FOREIGN_RE compiled regex."""

    def test_allows_basic_latin(self):
        """Basic Latin characters should not match."""
        assert FOREIGN_RE.search("hello world") is None

    def test_allows_extended_latin(self):
        """Extended Latin characters (accented) should not match."""
        assert FOREIGN_RE.search("café résumé naïve") is None

    def test_allows_digits(self):
        """Digits should not match."""
        assert FOREIGN_RE.search("test 2024 keyword") is None

    def test_allows_common_punctuation(self):
        """Common punctuation (.,;:?&) should not match."""
        assert FOREIGN_RE.search("what is SEO? best & top") is None

    def test_detects_cyrillic(self):
        """Cyrillic characters should match."""
        assert FOREIGN_RE.search("москва") is not None

    def test_detects_cjk(self):
        """CJK characters should match."""
        assert FOREIGN_RE.search("東京") is not None

    def test_detects_arabic(self):
        """Arabic characters should match."""
        assert FOREIGN_RE.search("مرحبا") is not None


class TestIsForeignLanguage:
    """Tests for the is_foreign_language function."""

    def test_english_keyword(self):
        """Plain English keyword is not foreign."""
        assert is_foreign_language("best seo tools") is False

    def test_german_keyword_with_umlauts(self):
        """German keywords with umlauts are not foreign (extended Latin)."""
        assert is_foreign_language("Küche") is False
        assert is_foreign_language("Straße") is False

    def test_keyword_with_numbers(self):
        """Keywords with numbers are not foreign."""
        assert is_foreign_language("seo tools 2025") is False

    def test_keyword_with_punctuation(self):
        """Keywords with common punctuation are not foreign."""
        assert is_foreign_language("what is SEO?") is False

    def test_cyrillic_keyword(self):
        """Cyrillic keyword is detected as foreign."""
        assert is_foreign_language("купить телефон") is True

    def test_chinese_keyword(self):
        """Chinese keyword is detected as foreign."""
        assert is_foreign_language("搜索引擎优化") is True

    def test_mixed_latin_and_foreign(self):
        """Mixed Latin + foreign is still detected as foreign."""
        assert is_foreign_language("SEO оптимизация") is True

    def test_empty_string(self):
        """Empty string is not foreign."""
        assert is_foreign_language("") is False

    def test_hyphenated_keyword(self):
        """Hyphenated keywords are not foreign."""
        assert is_foreign_language("long-tail-keyword") is False

    def test_apostrophe_keyword(self):
        """Keywords with apostrophes are not foreign."""
        assert is_foreign_language("it's a test") is False
