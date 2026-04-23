"""Shared text-processing utilities for the SEO Pipeline."""

import re

# Foreign-language heuristic: detect non-Latin characters.
# Allows basic Latin, extended Latin, Latin Extended Additional, whitespace,
# hyphens, apostrophes, digits, and common punctuation.
FOREIGN_RE = re.compile(r'[^\x20-\u024F\u1E00-\u1EFF\s\-\'0-9.,;:?&()/""]')


def is_foreign_language(keyword: str) -> bool:
    """Check if keyword contains non-Latin characters.

    Args:
        keyword: Keyword string to check.

    Returns:
        True if keyword contains non-Latin characters.
    """
    return bool(FOREIGN_RE.search(keyword))
