"""Resolve ISO 3166-1 alpha-2 country codes to DataForSEO location codes."""

import importlib.resources
import json


def resolve_location(market: str) -> int:
    """
    Resolve an ISO 3166-1 alpha-2 country code to a DataForSEO location code.

    Performs a pure file lookup with no network calls.

    Args:
        market: ISO 3166-1 alpha-2 country code (e.g., 'de', 'us', 'gb')
            Case-insensitive.

    Returns:
        The integer DataForSEO location code

    Raises:
        ValueError: if the market code is unknown
    """
    # Load location codes from data file
    data_path = importlib.resources.files('seo_pipeline').joinpath(
        'data', 'location_codes.json'
    )
    content = data_path.read_text(encoding='utf-8')

    codes = json.loads(content)

    key = market.lower()
    if key not in codes:
        available = ', '.join(sorted(codes.keys()))
        raise ValueError(
            f'Unknown market: "{market}". Available: {available}'
        )

    return codes[key]
