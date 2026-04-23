"""ToV compliance check: audit a draft against Tone-of-Voice guidelines.

Orchestrates the ToV audit workflow:
1. Load the draft and ToV files
2. Build the prompt with line-numbered draft
3. Call the LLM for structured violation analysis
4. Write JSON and Markdown reports
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from seo_pipeline.llm.client import complete
from seo_pipeline.llm.config import LLMConfig
from seo_pipeline.llm.prompts.tov_check import build_tov_check_prompt
from seo_pipeline.models.analysis import TovCheckOutput

logger = logging.getLogger(__name__)

# Default ToV path relative to project root
_DEFAULT_TOV = "templates/DT_ToV_v3.md"


def _find_tov(tov_path: str | None) -> Path:
    """Resolve the ToV file path.

    If *tov_path* is given, use it directly.  Otherwise fall back to the
    default template relative to the project root (two levels up from
    this module: analysis -> seo_pipeline -> project root).
    """
    if tov_path:
        p = Path(tov_path)
        if not p.exists():
            msg = f"ToV file not found: {tov_path}"
            raise FileNotFoundError(msg)
        return p

    # Walk up from this file to project root
    project_root = Path(__file__).resolve().parent.parent.parent
    default = project_root / _DEFAULT_TOV
    if not default.exists():
        msg = f"Default ToV not found at {default}"
        raise FileNotFoundError(msg)
    return default


def tov_check(
    draft_path: str,
    out_dir: str | None = None,
    llm_config: LLMConfig | None = None,
    tov_path: str | None = None,
) -> TovCheckOutput:
    """Run a ToV compliance audit on a draft.

    Args:
        draft_path: Path to the draft markdown file.
        out_dir: Output directory for reports (defaults to draft's parent).
        llm_config: LLM configuration (loaded from env if None).
        tov_path: Path to ToV file (defaults to templates/DT_ToV_v3.md).

    Returns:
        Structured TovCheckOutput with violations and summary.
    """
    draft = Path(draft_path)
    if not draft.exists():
        msg = f"Draft not found: {draft_path}"
        raise FileNotFoundError(msg)

    out = Path(out_dir) if out_dir else draft.parent
    out.mkdir(parents=True, exist_ok=True)

    tov_file = _find_tov(tov_path)

    logger.info("  reading: %s", draft)
    draft_text = draft.read_text(encoding="utf-8")

    logger.info("  reading: %s", tov_file)
    tov_text = tov_file.read_text(encoding="utf-8")

    if llm_config is None:
        llm_config = LLMConfig.from_env()

    messages = build_tov_check_prompt(tov_text, draft_text)
    result: TovCheckOutput = complete(
        messages,
        config=llm_config,
        response_model=TovCheckOutput,
        label="tov_check",
    )

    # Write JSON report
    json_path = out / "tov-check-report.json"
    json_path.write_text(
        json.dumps(
            result.model_dump(), indent=2, ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    logger.info("  writing: %s", json_path)

    # Write Markdown report
    md_path = out / "tov-check-report.md"
    md_path.write_text(
        _build_markdown_report(result, str(draft)),
        encoding="utf-8",
    )
    logger.info("  writing: %s", md_path)

    return result


def _build_markdown_report(
    output: TovCheckOutput,
    draft_path: str,
) -> str:
    """Build a markdown report from a TovCheckOutput."""
    checked_at = (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
    lines: list[str] = [
        "# ToV Compliance Report",
        "",
        f"**Draft:** {draft_path}",
        f"**Checked at:** {checked_at}",
        f"**Compliant:** {'Yes' if output.compliant else 'No'}",
        "",
        "## Summary",
        "",
        f"- Critical violations: {output.summary.get('critical', 0)}",
        f"- Warnings: {output.summary.get('warning', 0)}",
        "",
    ]

    if output.violations:
        lines.extend([
            "## Violations",
            "",
            "| Line | Rule | Severity | Text | Suggestion |",
            "|------|------|----------|------|------------|",
        ])
        for v in output.violations:
            # Escape pipes in text/suggestion for table rendering
            text = v.text.replace("|", "\\|")
            suggestion = v.suggestion.replace("|", "\\|")
            lines.append(
                f"| {v.line} | {v.rule} | {v.severity}"
                f" | {text} | {suggestion} |"
            )
    else:
        lines.append("No violations found.")

    lines.append("")
    return "\n".join(lines)
