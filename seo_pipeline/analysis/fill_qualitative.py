"""Fill qualitative analysis fields via LLM (SKILL.md step 2.1).

Loads briefing-data.json, calls the LLM for the 5 qualitative fields,
writes qualitative.json, and merges into briefing-data.json.

Usage:
    python -m seo_pipeline.analysis.fill_qualitative --dir output/2026-03-31_keyword/
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from seo_pipeline.analysis.merge_qualitative import merge_qualitative
from seo_pipeline.llm.client import complete
from seo_pipeline.llm.prompts.qualitative import build_qualitative_prompt
from seo_pipeline.models.analysis import BriefingData
from seo_pipeline.models.llm_responses import QualitativeResponse

logger = logging.getLogger(__name__)


def fill_qualitative(dir_path: str) -> None:
    """Run qualitative analysis and persist results.

    1. Load ``briefing-data.json`` from *dir_path*.
    2. Call ``complete()`` with the qualitative prompt and ``QualitativeResponse``.
    3. Write ``qualitative.json`` to *dir_path*.
    4. Call ``merge_qualitative()`` to patch into ``briefing-data.json``.
    """
    directory = Path(dir_path)
    briefing_path = directory / "briefing-data.json"

    if not briefing_path.exists():
        print(f"Error: briefing-data.json not found in {dir_path}", file=sys.stderr)
        sys.exit(1)

    logger.info("Loading briefing data from %s", briefing_path)
    briefing_data = BriefingData.model_validate(
        json.loads(briefing_path.read_text(encoding="utf-8")),
    )

    messages = build_qualitative_prompt(briefing_data)
    logger.info("LLM call start: qualitative analysis")
    result: QualitativeResponse = complete(
        messages=messages, response_model=QualitativeResponse,
    )
    logger.info("LLM call complete: qualitative analysis")

    qualitative_dict = result.model_dump(mode="json")
    qualitative_path = directory / "qualitative.json"
    qualitative_path.write_text(
        json.dumps(qualitative_dict, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info("Wrote %s", qualitative_path)

    merge_qualitative(dir_path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fill qualitative analysis fields via LLM.",
    )
    parser.add_argument(
        "--dir", required=True,
        help="Output directory containing briefing-data.json.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    args = _build_parser().parse_args(argv)
    fill_qualitative(args.dir)


if __name__ == "__main__":
    main()
