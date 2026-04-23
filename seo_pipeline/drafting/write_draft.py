"""Content draft generation via LLM.

Reads a briefing markdown file, calls the LLM to produce an article draft,
and saves the result alongside the briefing.

Usage::

    python -m seo_pipeline.drafting.write_draft \
        --brief output/.../brief-keyword.md \
        [--tov path/to/tov.md] \
        [--instructions "use du instead of Sie"]
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

from seo_pipeline.llm.client import complete
from seo_pipeline.llm.prompts.draft import build_draft_prompt

logger = logging.getLogger(__name__)


def _slug_from_brief_path(brief_path: Path) -> str:
    """Extract slug from a briefing filename.

    ``brief-keyword-slug.md`` -> ``keyword-slug``
    """
    name = brief_path.stem  # e.g. "brief-keyword-slug"
    match = re.match(r"^brief-(.+)$", name)
    if not match:
        # Fallback: use the full stem
        return name
    return match.group(1)


def write_draft(
    brief_path: str,
    tov_path: str | None = None,
    instructions: str | None = None,
) -> None:
    """Generate an article draft from a briefing markdown file.

    1. Read briefing markdown from *brief_path*.
    2. Optionally load tone-of-voice from *tov_path*.
    3. Call ``complete()`` with the draft prompt (plain text, no response_model).
    4. Save ``draft-<slug>.md`` in the same directory as the briefing file.
    """
    brief = Path(brief_path)

    if not brief.exists():
        print(f"Error: briefing file not found: {brief_path}", file=sys.stderr)
        sys.exit(1)

    logger.info("  reading: %s", brief)
    briefing_markdown = brief.read_text(encoding="utf-8")

    tone_of_voice = None
    if tov_path:
        p = Path(tov_path)
        if not p.exists():
            print(f"Error: tone-of-voice file not found: {tov_path}", file=sys.stderr)
            sys.exit(1)
        tone_of_voice = p.read_text(encoding="utf-8")
        logger.info("  reading: %s", p)

    messages = build_draft_prompt(
        briefing_markdown, tone_of_voice, instructions,
    )
    draft_content: str = complete(messages=messages, label="write_draft")

    slug = _slug_from_brief_path(brief)
    output_path = brief.parent / f"draft-{slug}.md"
    output_path.write_text(draft_content, encoding="utf-8")
    logger.info("  writing: %s", output_path)

    # Emit a sibling .docx. The .md is the source of truth — any docx
    # failure is logged and swallowed so the pipeline never breaks.
    docx_path = brief.parent / f"draft-{slug}.docx"
    try:
        import pypandoc
    except ImportError:
        logger.warning(
            "  skipping docx: pypandoc not installed (install pypandoc-binary)",
        )
        return

    try:
        pypandoc.convert_file(
            str(output_path), "docx", outputfile=str(docx_path),
        )
        logger.info("  writing: %s", docx_path)
    except Exception as exc:  # noqa: BLE001 — docx failure must not raise
        logger.warning("  docx conversion failed for %s: %s", output_path, exc)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate an article draft from a content briefing.",
    )
    parser.add_argument(
        "--brief", required=True,
        help="Path to the briefing markdown file (brief-<slug>.md).",
    )
    parser.add_argument(
        "--tov", default=None,
        help="Path to a tone-of-voice guidelines file.",
    )
    parser.add_argument(
        "--instructions", default=None,
        help="Special instructions for the draft (e.g. 'use du instead of Sie').",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    args = _build_parser().parse_args(argv)
    write_draft(args.brief, args.tov, args.instructions)


if __name__ == "__main__":
    main()
