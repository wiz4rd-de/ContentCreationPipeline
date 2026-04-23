"""Deterministic qualitative merge.

Patches qualitative.json fields into briefing-data.json.
Only overwrites fields that are non-null in qualitative.json.
Same inputs always produce byte-identical output.

Usage:
    python -m seo_pipeline.analysis.merge_qualitative --dir <output/YYYY-MM-DD_slug/>
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def merge_qualitative(dir_path: str) -> None:
    """Merge non-null qualitative fields into briefing-data.json.

    Reads ``qualitative.json`` and ``briefing-data.json`` from *dir_path*,
    patches non-null top-level keys from ``qualitative.json`` into the
    ``qualitative`` section of ``briefing-data.json``, and writes it back.
    """
    directory = Path(dir_path)
    briefing_path = directory / "briefing-data.json"
    qualitative_path = directory / "qualitative.json"

    if not briefing_path.exists():
        print(f"Error: briefing-data.json not found in {dir_path}", file=sys.stderr)
        sys.exit(1)

    if not qualitative_path.exists():
        print(f"Error: qualitative.json not found in {dir_path}", file=sys.stderr)
        sys.exit(1)

    briefing = json.loads(briefing_path.read_text(encoding="utf-8"))
    qualitative = json.loads(qualitative_path.read_text(encoding="utf-8"))

    # Merge non-null qualitative fields into briefing's qualitative section.
    merged = {**briefing}
    merged["qualitative"] = {**briefing.get("qualitative", {})}

    patched = 0
    for key, value in qualitative.items():
        if value is not None:
            merged["qualitative"][key] = value
            patched += 1

    logger.info(
        "Merge qualitative: patched %d field(s) into briefing-data.json",
        patched,
    )

    output = json.dumps(merged, indent=2, ensure_ascii=False) + "\n"
    briefing_path.write_text(output, encoding="utf-8")
    print(f"merge-qualitative: patched {patched} field(s) into briefing-data.json")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Merge qualitative.json fields into briefing-data.json.",
    )
    parser.add_argument(
        "--dir", required=True,
        help="Output directory containing briefing-data.json and qualitative.json.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    args = _build_parser().parse_args(argv)
    merge_qualitative(args.dir)


if __name__ == "__main__":
    main()
