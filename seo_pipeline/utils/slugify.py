"""Deterministic slug generation from arbitrary strings.

Replaces German umlauts, lowercases, and normalises to hyphen-separated
alphanumeric tokens.
"""

import re

# Map German umlauts to their ASCII digraph equivalents.
# Replacement must happen before lowercasing to preserve digraph casing.
_UMLAUT_MAP = {
    'ä': 'ae',   # U+00E4
    'ö': 'oe',   # U+00F6
    'ü': 'ue',   # U+00FC
    'Ä': 'Ae',   # U+00C4
    'Ö': 'Oe',   # U+00D6
    'Ü': 'Ue',   # U+00DC
    'ß': 'ss',   # U+00DF
}

_UMLAUT_TABLE = str.maketrans(_UMLAUT_MAP)


def slugify(input_str: str) -> str:
    """Convert a string to a URL-safe slug.

    Umlaut replacement happens before lowercasing so that capitalised umlauts
    produce the correct digraph casing (which lowercase then normalises anyway).

    Args:
        input_str: The input string to convert.

    Returns:
        A URL-safe slug with non-alphanumeric characters replaced by hyphens,
        or an empty string if input is not a string.

    Examples:
        >>> slugify('thailand urlaub')
        'thailand-urlaub'
        >>> slugify('schönste Strände Thailand')
        'schoenste-straende-thailand'
        >>> slugify('Äger Öffnung Übung')
        'aerger-oeffnung-uebung'
    """
    if not isinstance(input_str, str):
        return ''

    s = input_str

    # Replace German umlauts before lowercasing (single-pass via translate table)
    s = s.translate(_UMLAUT_TABLE)

    s = s.lower()

    # Replace any non-alphanumeric character with a hyphen
    s = re.sub(r'[^a-z0-9]+', '-', s)

    # Trim leading/trailing hyphens
    s = re.sub(r'^-+|-+$', '', s)

    return s


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        # Join all arguments as a single input string
        input_text = ' '.join(sys.argv[1:])
        print(slugify(input_text))
    else:
        print('Usage: python -m seo_pipeline.utils.slugify <input>')
