"""Assemble final briefing markdown via LLM (SKILL.md step 2.2).

Loads complete briefing-data.json, calls the LLM for briefing assembly,
saves brief-<slug>.md, and updates qualitative.briefing in briefing-data.json.

Usage::

    python -m seo_pipeline.analysis.assemble_briefing_md \
        --dir output/.../ [--template ...] [--tov ...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from seo_pipeline.llm.client import complete
from seo_pipeline.llm.prompts.qualitative import build_briefing_assembly_prompt
from seo_pipeline.models.analysis import BriefingData
from seo_pipeline.utils.slugify import slugify


def assemble_briefing_md(
    dir_path: str,
    template_path: str | None = None,
    tov_path: str | None = None,
) -> None:
    """Generate the briefing markdown and persist it.

    1. Load ``briefing-data.json`` from *dir_path*.
    2. Optionally load template and tone-of-voice files.
    3. Call ``complete()`` with the briefing assembly prompt (plain text).
    4. Save ``brief-<slug>.md`` in *dir_path*.
    5. Update ``qualitative.briefing`` in ``briefing-data.json``.
    """
    directory = Path(dir_path)
    briefing_path = directory / "briefing-data.json"

    if not briefing_path.exists():
        print(f"Error: briefing-data.json not found in {dir_path}", file=sys.stderr)
        sys.exit(1)

    raw_briefing = json.loads(briefing_path.read_text(encoding="utf-8"))
    briefing_data = BriefingData.model_validate(raw_briefing)

    # Verify all 5 qualitative fields are populated
    qual = briefing_data.qualitative
    missing = []
    for field_name in (
        "entity_clusters", "geo_audit", "content_format_recommendation",
        "unique_angles", "aio_strategy",
    ):
        if getattr(qual, field_name) is None:
            missing.append(field_name)
    if missing:
        print(
            f"Error: qualitative fields not populated: {', '.join(missing)}. "
            "Run fill_qualitative first.",
            file=sys.stderr,
        )
        sys.exit(1)

    template = None
    if template_path:
        template = Path(template_path).read_text(encoding="utf-8")

    tone_of_voice = None
    if tov_path:
        tone_of_voice = Path(tov_path).read_text(encoding="utf-8")

    messages = build_briefing_assembly_prompt(briefing_data, template, tone_of_voice)
    markdown: str = complete(messages=messages)

    slug = slugify(briefing_data.meta.seed_keyword)
    md_path = directory / f"brief-{slug}.md"
    md_path.write_text(markdown, encoding="utf-8")
    print(f"assemble-briefing-md: wrote {md_path}")

    # Update qualitative.briefing in briefing-data.json with a summary reference
    raw_briefing["qualitative"]["briefing"] = f"brief-{slug}.md"
    briefing_path.write_text(
        json.dumps(raw_briefing, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("assemble-briefing-md: updated qualitative.briefing in briefing-data.json")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Assemble final briefing markdown via LLM.",
    )
    parser.add_argument(
        "--dir", required=True,
        help="Output directory containing briefing-data.json.",
    )
    parser.add_argument(
        "--template", default=None,
        help="Path to a content template file.",
    )
    parser.add_argument(
        "--tov", default=None,
        help="Path to a tone-of-voice guidelines file.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    args = _build_parser().parse_args(argv)
    assemble_briefing_md(args.dir, args.template, args.tov)


if __name__ == "__main__":
    main()
