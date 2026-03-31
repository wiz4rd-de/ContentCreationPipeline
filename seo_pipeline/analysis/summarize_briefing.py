"""Print a compact plain-text summary of a briefing-data.json file.

Deterministic: same input always produces identical output.

Usage:
    python -m seo_pipeline.analysis.summarize_briefing \
        --file <path/to/briefing-data.json>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_DIVIDER = "\u2500" * 35


def summarize_briefing(file_path: str) -> str:
    """Return a compact text summary of the briefing data at *file_path*."""
    path = Path(file_path)
    if not path.exists():
        print(f"File not found: {path.resolve()}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(path.read_text(encoding="utf-8"))
    return _format_summary(data)


def _format_summary(data: dict[str, Any]) -> str:
    """Build the summary string from parsed briefing data."""
    meta = data.get("meta") or {}
    kw = data.get("keyword_data") or {}
    serp = data.get("serp_data") or {}
    comp = data.get("competitor_analysis") or {}
    faq = data.get("faq_data") or {}

    seed_keyword = meta.get("seed_keyword") or "n/a"
    total_kw_raw = kw.get("total_keywords")
    total_kw = total_kw_raw if total_kw_raw is not None else 0
    filtered_raw = kw.get("filtered_count")
    filtered_kw = filtered_raw if filtered_raw is not None else 0
    clusters = kw.get("clusters")
    cluster_count = len(clusters) if isinstance(clusters, list) else 0
    competitors = serp.get("competitors")
    competitor_count = (
        len(competitors) if isinstance(competitors, list) else 0
    )
    avg_raw = comp.get("avg_word_count")
    avg_words = avg_raw if avg_raw is not None else "n/a"
    questions = faq.get("questions")
    faq_count = len(questions) if isinstance(questions, list) else 0

    # SERP features: list truthy keys
    serp_features = serp.get("serp_features") or {}
    truthy = [k for k, v in serp_features.items() if v]
    serp_line = ", ".join(truthy) if truthy else "none"

    # AIO
    aio = serp.get("aio")
    aio_present = "yes" if aio and aio.get("present") else "no"

    # Modules
    common_mods = comp.get("common_modules")
    common_line = ", ".join(common_mods) if isinstance(common_mods, list) else "n/a"
    rare_mods = comp.get("rare_modules")
    rare_line = ", ".join(rare_mods) if isinstance(rare_mods, list) else "n/a"

    # Removal summary
    removal = kw.get("removal_summary") or {}
    removal_parts = [f"{v} {k}" for k, v in removal.items() if v and v > 0]
    removal_line = ", ".join(removal_parts) if removal_parts else "none"

    return (
        f"Briefing Summary: {seed_keyword}\n"
        f"{_DIVIDER}\n"
        f"Keywords:    {total_kw} total, {filtered_kw} after filtering\n"
        f"Clusters:    {cluster_count}\n"
        f"Competitors: {competitor_count} ({avg_words} avg words)\n"
        f"FAQ:         {faq_count} questions\n"
        f"SERP:        {serp_line}\n"
        f"AIO:         {aio_present}\n"
        f"Modules:     common: {common_line}, rare: {rare_line}\n"
        f"Removals:    {removal_line}"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Print a compact summary of briefing-data.json.",
    )
    parser.add_argument(
        "--file", required=True,
        help="Path to briefing-data.json.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    args = _build_parser().parse_args(argv)
    print(summarize_briefing(args.file))


if __name__ == "__main__":
    main()
