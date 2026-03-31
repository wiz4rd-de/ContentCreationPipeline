"""Deterministic page structure analyzer.

Detects content modules (FAQ, table, list, video, form, image gallery),
computes per-section word/sentence counts and depth scores,
and produces cross-competitor module frequency analysis.

Usage:
    python -m seo_pipeline.analysis.analyze_page_structure \
        --pages-dir <pages/> [--output path]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from seo_pipeline.models.analysis import (
    CompetitorPageStructure,
    CrossCompetitorAnalysis,
    PageStructure,
    PageStructureSection,
)
from seo_pipeline.utils.math import js_round, normalize_number

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_WORD_COUNT = 200

FAQ_HEADING_RE = re.compile(
    r"\b(faq|fragen|haeufig|frequently\s+asked|h.ufig)\b", re.IGNORECASE
)

BLOCK_HEADING_RE = re.compile(
    r"why have i been blocked|access denied|403 forbidden|please verify"
    r"|checking your browser|just a moment|enable javascript and cookies"
    r"|attention required",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _count_words(text: str) -> int:
    """Count whitespace-separated non-empty tokens."""
    return len(text.split())


def _count_sentences(text: str) -> int:
    """Count sentences by splitting on sentence-ending punctuation.

    Mirrors the Node.js logic: split on [.?!]+ then count non-empty parts.
    """
    parts = re.split(r"[.?!]+", text)
    return sum(1 for s in parts if s.strip())


def _has_numbers(text: str) -> bool:
    """Return True if text contains at least one digit."""
    return bool(re.search(r"\d", text))


def _has_lists(signals: dict[str, Any]) -> bool:
    """Return True if the page has ordered or unordered lists."""
    return signals.get("ordered_lists", 0) > 0 or signals.get("unordered_lists", 0) > 0


def _compute_depth_score(sentence_count: int) -> str:
    """Classify section depth based on sentence count."""
    if sentence_count <= 2:
        return "shallow"
    if sentence_count <= 6:
        return "basic"
    return "detailed"


# ---------------------------------------------------------------------------
# Page quality filter
# ---------------------------------------------------------------------------


def _block_reason(
    main_text: str, heading_texts: list[str]
) -> str | None:
    """Return a reason string if the page should be excluded, else None."""
    if not main_text:
        return "missing main_content_text"
    wc = _count_words(main_text)
    if wc < MIN_WORD_COUNT:
        return f"too few words ({wc} < {MIN_WORD_COUNT})"
    for t in heading_texts:
        if BLOCK_HEADING_RE.search(t):
            return f'block/error heading: "{t}"'
    return None


# ---------------------------------------------------------------------------
# Module detection
# ---------------------------------------------------------------------------


def _detect_modules(
    signals: dict[str, Any], heading_texts: list[str]
) -> list[str]:
    """Detect content modules present on the page.

    Returns an alphabetically sorted list of module names.
    """
    modules: list[str] = []

    has_faq_heading = any(FAQ_HEADING_RE.search(t) for t in heading_texts)
    if has_faq_heading or signals.get("faq_sections", 0) > 0:
        modules.append("faq")

    if signals.get("tables", 0) > 0:
        modules.append("table")
    if signals.get("ordered_lists", 0) > 0 or signals.get("unordered_lists", 0) > 0:
        modules.append("list")
    if signals.get("video_embeds", 0) > 0:
        modules.append("video")
    if signals.get("images_in_content", 0) > 3:
        modules.append("image_gallery")
    if signals.get("forms", 0) > 0:
        modules.append("form")

    modules.sort()
    return modules


# ---------------------------------------------------------------------------
# Section splitting
# ---------------------------------------------------------------------------


def _split_sections(
    main_text: str, headings: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Split main_content_text into sections based on heading positions."""
    if not headings:
        return [{"heading": "", "level": 0, "text": main_text}]

    positions: list[dict[str, Any]] = []
    for h in headings:
        idx = main_text.find(h["text"])
        if idx >= 0:
            positions.append(
                {"heading": h["text"], "level": h["level"], "pos": idx}
            )
    positions.sort(key=lambda p: p["pos"])

    sections: list[dict[str, Any]] = []

    # Intro before first heading
    if positions and positions[0]["pos"] > 0:
        intro = main_text[: positions[0]["pos"]].strip()
        if intro:
            sections.append({"heading": "", "level": 0, "text": intro})

    for i, pos in enumerate(positions):
        start = pos["pos"] + len(pos["heading"])
        end = positions[i + 1]["pos"] if i + 1 < len(positions) else len(main_text)
        sections.append(
            {
                "heading": pos["heading"],
                "level": pos["level"],
                "text": main_text[start:end].strip(),
            }
        )

    return sections


# ---------------------------------------------------------------------------
# Main analysis function
# ---------------------------------------------------------------------------


def analyze_page_structure(pages_dir: Path) -> PageStructure:
    """Analyze page structure from competitor pages.

    Args:
        pages_dir: Directory containing extracted page JSON files.

    Returns:
        PageStructure model with per-competitor structure and cross-competitor
        module frequency analysis.
    """
    page_files = sorted(p for p in pages_dir.iterdir() if p.suffix == ".json")

    empty_cross = CrossCompetitorAnalysis(
        common_modules=[],
        rare_modules=[],
        module_frequency={},
        avg_word_count=0,
        avg_sections=0,
    )

    if not page_files:
        return PageStructure(competitors=[], cross_competitor=empty_cross)

    print(
        f"Analyzing page structure for {len(page_files)} competitors...",
        file=sys.stderr,
    )

    competitors: list[CompetitorPageStructure] = []

    for f in page_files:
        raw = json.loads(f.read_text(encoding="utf-8"))
        main_text: str = raw.get("main_content_text", "")
        headings: list[dict[str, Any]] = raw.get("headings", [])
        signals: dict[str, Any] = raw.get("html_signals", {
            "faq_sections": 0,
            "tables": 0,
            "ordered_lists": 0,
            "unordered_lists": 0,
            "video_embeds": 0,
            "forms": 0,
            "images_in_content": 0,
        })

        heading_texts = [h["text"] for h in headings]
        detected_modules = _detect_modules(signals, heading_texts)

        raw_sections = _split_sections(main_text, headings)
        sections = [
            PageStructureSection(
                heading=s["heading"],
                level=s["level"],
                word_count=_count_words(s["text"]),
                sentence_count=_count_sentences(s["text"]),
                has_numbers=_has_numbers(s["text"]),
                has_lists=_has_lists(signals),
                depth_score=_compute_depth_score(_count_sentences(s["text"])),
            )
            for s in raw_sections
        ]

        # Extract domain from URL
        domain = ""
        try:
            domain = urlparse(raw.get("url", "")).hostname or ""
        except Exception:
            pass

        # Quality filter: skip blocked/error/thin pages
        reason = _block_reason(main_text, heading_texts)
        if reason is not None:
            print(
                f"Skipping {domain or f.name}: {reason}",
                file=sys.stderr,
            )
            continue

        competitors.append(
            CompetitorPageStructure(
                url=raw.get("url", ""),
                domain=domain,
                total_word_count=_count_words(main_text),
                section_count=len(sections),
                detected_modules=detected_modules,
                sections=sections,
            )
        )

    # --- Cross-competitor analysis ---
    total_competitors = len(competitors)

    if total_competitors == 0:
        return PageStructure(competitors=[], cross_competitor=empty_cross)

    module_counts: Counter[str] = Counter()
    for comp in competitors:
        for mod in comp.detected_modules:
            module_counts[mod] += 1

    # Sort keys alphabetically for deterministic output
    sorted_keys = sorted(module_counts.keys())
    module_frequency = {k: module_counts[k] for k in sorted_keys}

    common_threshold = total_competitors * 0.7
    rare_threshold = total_competitors * 0.2

    common_modules = sorted(
        k for k in sorted_keys if module_counts[k] >= common_threshold
    )
    rare_modules = sorted(
        k for k in sorted_keys if module_counts[k] <= rare_threshold
    )

    total_word_count = sum(c.total_word_count for c in competitors)
    total_sections = sum(c.section_count for c in competitors)

    avg_word_count = js_round(total_word_count / total_competitors)
    avg_sections = js_round(total_sections / total_competitors)

    cross_competitor = CrossCompetitorAnalysis(
        common_modules=common_modules,
        rare_modules=rare_modules,
        module_frequency=module_frequency,
        avg_word_count=avg_word_count,
        avg_sections=avg_sections,
    )

    return PageStructure(competitors=competitors, cross_competitor=cross_competitor)


# ---------------------------------------------------------------------------
# Serialization helper
# ---------------------------------------------------------------------------


def _normalize_tree(obj: Any) -> Any:
    """Recursively apply normalize_number to all numeric values."""
    if isinstance(obj, dict):
        return {k: _normalize_tree(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_tree(v) for v in obj]
    if isinstance(obj, float):
        return normalize_number(obj)
    return obj


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze page structure from competitor pages."
    )
    parser.add_argument(
        "--pages-dir",
        required=True,
        type=Path,
        help="Directory with page JSON files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file path (default: stdout).",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    args = _build_parser().parse_args(argv)
    result = analyze_page_structure(args.pages_dir)
    output_dict = _normalize_tree(result.model_dump())
    output_json = json.dumps(output_dict, indent=2, ensure_ascii=False)

    if args.output:
        args.output.write_text(output_json, encoding="utf-8")
    else:
        sys.stdout.write(output_json + "\n")


if __name__ == "__main__":
    main()
