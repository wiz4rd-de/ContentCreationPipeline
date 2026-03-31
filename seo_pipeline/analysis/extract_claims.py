"""Deterministic claim extraction from draft markdown files.

Extracts verifiable factual claims using regex/heuristic patterns across
6 categories: heights_distances, prices_costs, dates_years, counts,
geographic, measurements.

Usage:
    python -m seo_pipeline.analysis.extract_claims \
        --draft <path/to/draft.md> [--output path]
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from seo_pipeline.models.analysis import Claim, ClaimsMeta, ClaimsOutput

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# German number: 1.700 or 6.500,5 or plain 604 or 2.469
_NUM = r"(?:\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:,\d+)?)"

_CATEGORIES: list[tuple[str, re.Pattern[str]]] = [
    (
        "heights_distances",
        # e.g. 2.469 Metern, 8 km, 604 Meter, 1.700 Kilometer
        re.compile(
            rf"{_NUM}\s*(?:Metern?|Kilometern?|km|Meter[n]?|Hoehendifferenz|Hoehenmetern?)"
        ),
    ),
    (
        "prices_costs",
        # e.g. 790 NOK, 150 EUR, ab 49 Euro
        re.compile(
            rf"(?:(?:ab|etwa|rund|ca\.?)\s+)?{_NUM}\s*(?:NOK|EUR|Euro|CHF|USD|Kronen)"
        ),
    ),
    (
        "dates_years",
        # e.g. gegruendet 1962, seit 2015, im Jahr 1884
        re.compile(
            r"(?:(?:im\s+Jahr|seit|gegruendet|eroeffnet|gebaut|entstanden)\s+)(\d{4})",
            re.IGNORECASE,
        ),
    ),
    (
        "counts",
        # e.g. ueber 550 Huetten, 28 Nationalparks, rund 500 Routen
        re.compile(
            rf"(?:(?:ueber|rund|etwa|ca\.?|mehr\s+als|insgesamt)\s+)?{_NUM}\s+(?:[A-Z\u00c4\u00d6\u00dc][a-z\u00e4\u00f6\u00fc\u00df]+(?:en|er|e|n|s|parks?)?)"
        ),
    ),
    (
        "geographic",
        # keyword triggers + capitalized proper nouns
        re.compile(
            r"(?:zwischen|noerdlich|suedlich|oestlich|westlich|nordoestlich|nordwestlich|suedoestlich|suedwestlich)"
            r"\s+(?:des\s+|der\s+|dem\s+)?"
            r"(?:[A-Z\u00c4\u00d6\u00dc][a-z\u00e4\u00f6\u00fc\u00df]+)"
            r"(?:\s+(?:und|bis)\s+[A-Z\u00c4\u00d6\u00dc][a-z\u00e4\u00f6\u00fc\u00df]+)*"
        ),
    ),
    (
        "measurements",
        # e.g. 6.500 bis 8.000 Quadratkilometer, Wassertemperaturen um 15 Grad
        re.compile(
            rf"{_NUM}(?:\s+bis\s+{_NUM})?\s*(?:Quadratkilometern?|Grad\s*(?:Celsius|C)?|Liter|Tonnen|Hektar|qm|m\u00b2)"
        ),
    ),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences at . ! ? boundaries.

    Handles German number format (1.700) by not splitting on dots between
    digits.
    """
    sentences: list[str] = []
    current: list[str] = []
    length = len(text)

    for i, ch in enumerate(text):
        current.append(ch)
        if ch in ".?!":
            # Don't split on dots that are part of numbers (digit.digit)
            if ch == "." and i > 0 and i < length - 1:
                prev_ch = text[i - 1]
                next_ch = text[i + 1]
                if prev_ch.isdigit() and next_ch.isdigit():
                    continue
            trimmed = "".join(current).strip()
            if trimmed:
                sentences.append(trimmed)
            current = []

    trailing = "".join(current).strip()
    if trailing:
        sentences.append(trailing)

    return sentences


def _find_skip_ranges(lines: list[str]) -> list[tuple[int, int]]:
    """Find line ranges for meta tables to skip.

    Meta table starts with '| Feld | Wert |' header and ends with '---'.
    """
    ranges: list[tuple[int, int]] = []
    in_meta_table = False
    meta_start = -1

    for i, line in enumerate(lines):
        trimmed = line.strip()
        if trimmed.startswith("|") and "Feld" in trimmed and "Wert" in trimmed:
            in_meta_table = True
            meta_start = i
        if in_meta_table and re.match(r"^-{3,}$", trimmed):
            ranges.append((meta_start, i))
            in_meta_table = False

    # If table never closed, skip to end
    if in_meta_table:
        ranges.append((meta_start, len(lines) - 1))

    return ranges


def _is_in_skip_range(line_idx: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= line_idx <= end for start, end in ranges)


def _is_editorial_marker(line: str) -> bool:
    """Check if line is an editorial marker (HTML comments or blockquote markers)."""
    trimmed = line.strip()
    if re.match(r"^<!--", trimmed) and "-->" in trimmed:
        return True
    if re.match(r"^>\s*\*\*\[", trimmed):
        return True
    return False


def _extract_section(line: str) -> str | None:
    """Extract section heading from ## or ### lines."""
    m = re.match(r"^#{2,3}\s+(.+)", line)
    return m.group(1).strip() if m else None


def _find_sentence(text: str, match_str: str, match_index: int) -> str:
    """Find the sentence containing a match at a given position."""
    window_start = max(0, match_index - 300)
    window_end = min(len(text), match_index + len(match_str) + 300)
    window = text[window_start:window_end]
    relative_idx = match_index - window_start

    sentences = _split_sentences(window)
    pos = 0
    for sentence in sentences:
        sentence_start = window.index(sentence, pos)
        sentence_end = sentence_start + len(sentence)
        if relative_idx >= sentence_start and relative_idx < sentence_end:
            return sentence
        pos = sentence_end

    # Fallback: return the full line trimmed
    return text.strip()


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------


def extract_claims(draft_path: str | Path) -> ClaimsOutput:
    """Extract factual claims from a draft markdown file.

    Args:
        draft_path: Path to the draft markdown file.

    Returns:
        ClaimsOutput with metadata and list of extracted claims.
    """
    draft_text = Path(draft_path).read_text(encoding="utf-8")
    lines = draft_text.split("\n")
    skip_ranges = _find_skip_ranges(lines)

    raw_claims: list[dict] = []
    current_section: str | None = None

    for line_idx, line in enumerate(lines):
        # Track current section
        section_match = _extract_section(line)
        if section_match:
            current_section = section_match

        # Skip meta table lines
        if _is_in_skip_range(line_idx, skip_ranges):
            continue

        # Skip editorial markers
        if _is_editorial_marker(line):
            continue

        # Skip heading lines themselves
        if re.match(r"^#{1,6}\s+", line):
            continue

        # Skip empty lines
        if line.strip() == "":
            continue

        # Run each category pattern against this line
        for cat_name, pattern in _CATEGORIES:
            for m in pattern.finditer(line):
                value = m.group(0)
                sentence = _find_sentence(line, value, m.start())
                raw_claims.append(
                    {
                        "category": cat_name,
                        "value": value,
                        "sentence": sentence,
                        "line": line_idx + 1,  # 1-based
                        "char_index": m.start(),
                        "section": current_section,
                    }
                )

    # Sort by line number, then by character position for determinism
    raw_claims.sort(key=lambda c: (c["line"], c["char_index"]))

    # Assign sequential IDs
    claims = [
        Claim(
            id=f"c{i + 1:03d}",
            category=c["category"],
            value=c["value"],
            sentence=c["sentence"],
            line=c["line"],
            section=c["section"],
        )
        for i, c in enumerate(raw_claims)
    ]

    return ClaimsOutput(
        meta=ClaimsMeta(
            draft=str(draft_path),
            extracted_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            total_claims=len(claims),
        ),
        claims=claims,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract factual claims from draft markdown."
    )
    parser.add_argument(
        "--draft", required=True, help="Path to the draft markdown file."
    )
    parser.add_argument("--output", default=None, help="Write JSON to this file.")
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    args = _build_parser().parse_args(argv)
    result = extract_claims(args.draft)
    output_json = result.model_dump_json(indent=2)

    if args.output:
        Path(args.output).write_text(output_json + "\n", encoding="utf-8")
    else:
        sys.stdout.write(output_json + "\n")


if __name__ == "__main__":
    main()
