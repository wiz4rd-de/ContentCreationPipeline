"""Shared tokenizer module.

Provides pure, deterministic tokenization and stopword-removal utilities
used by analysis and keyword extraction.
"""

import json
import re
from importlib import resources


def tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation (keeping letters including umlauts and digits),
    split on whitespace, and filter single-character tokens.

    Args:
        text: The input text to tokenize.

    Returns:
        A list of tokens with length > 1.
    """
    cleaned = text.lower()
    # Replace non-alphanumeric characters (keeping umlauts and extended Latin)
    # with spaces
    cleaned = re.sub(
        r'[^a-z0-9\u00e4\u00f6\u00fc\u00df\u00e0-\u00ff]+', ' ', cleaned
    )
    cleaned = cleaned.strip()
    if not cleaned:
        return []
    return [w for w in cleaned.split() if len(w) > 1]


def remove_stopwords(tokens: list[str], stopword_set: set[str]) -> list[str]:
    """Filter tokens not present in the given stopword set.

    Pure function — takes an explicit Set rather than closing over module state.

    Args:
        tokens: List of tokens to filter.
        stopword_set: Set of stopwords to remove.

    Returns:
        List of tokens not in the stopword set.
    """
    return [t for t in tokens if t not in stopword_set]


def load_stopword_set(language: str) -> set[str]:
    """Load stopwords.json and return a combined set.

    For language 'de', combines both 'de' and 'en' arrays.
    For other languages, returns only that language's set.

    Args:
        language: The language code ('de', 'en', etc.).

    Returns:
        A set of stopwords for the given language.
    """
    stopwords_path = resources.files('seo_pipeline').joinpath(
        'data/stopwords.json'
    )
    data = json.loads(stopwords_path.read_text(encoding='utf-8'))

    words = data.get(language, []).copy()
    if language == 'de':
        words.extend(data.get('en', []))

    return set(words)
