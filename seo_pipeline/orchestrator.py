"""Pipeline orchestrator.

Runs the 11-stage SEO content pipeline end-to-end and emits a
``StageEvent`` for the start and end of each stage via an ``on_event``
callback. This module is the single source of truth for the pipeline's
stage sequence; both the Typer CLI (``seo_pipeline.cli.main.run_pipeline``)
and the upcoming Streamlit UI consume it via ``run_pipeline_core``.

Design notes
------------
* The 11 stages exactly mirror the ``Stage N/11: ...`` labels the CLI
  has printed historically. Stage message strings are byte-identical to
  the pre-refactor CLI so scripts that grep stderr keep working.
* ``on_event`` is invoked synchronously. No threading, no asyncio
  dispatch — by the time ``run_pipeline_core`` returns, every event has
  already been delivered to the callback.
* Errors from any stage body are surfaced as an ``error`` event for
  that stage, then re-raised unchanged so the caller decides what to
  do.
* Non-stage stderr messages (warnings, the end-of-run "Pipeline
  complete" line, the summarize-briefing body, LLM-not-configured
  fallback instructions) are delivered via a separate optional
  ``on_log`` callback, keeping ``StageEvent`` focused on stage
  lifecycle.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Literal, Optional

StageStatus = Literal["start", "complete", "skip", "error"]

STAGE_TOTAL = 11


@dataclass(frozen=True)
class StageEvent:
    """Signal emitted at the boundaries of each pipeline stage.

    Attributes
    ----------
    stage_index:
        1-based stage position, from 1 to :data:`STAGE_TOTAL`.
    stage_total:
        Total number of stages in the pipeline. Always
        :data:`STAGE_TOTAL` for the current pipeline; exposed on the
        event so consumers do not have to import the constant.
    stage_name:
        Short canonical identifier for the stage (e.g. ``"fetch-serp"``).
        Stable across runs; safe to use as a dict key.
    status:
        Lifecycle marker for this event:

        * ``"start"`` — the stage body is about to run.
        * ``"complete"`` — the stage body finished without raising.
        * ``"skip"`` — the stage was skipped for a non-error reason
          (reserved; the current 11 stages always run).
        * ``"error"`` — the stage body raised. The exception is
          re-raised after the event fires.
    message:
        Human-readable description, byte-identical to the pre-refactor
        CLI ``Stage N/11: ...`` label for ``start`` events (excluding
        the ``Stage N/11: `` prefix, which the CLI wrapper adds).
    payload:
        Free-form dict for stage-specific details (e.g. artifact paths
        written by the stage). Always a dict, never ``None``.
    """

    stage_index: int
    stage_name: str
    status: StageStatus
    message: str
    payload: dict[str, Any] = field(default_factory=dict)
    stage_total: int = STAGE_TOTAL


@dataclass
class PipelineConfig:
    """Input parameters for :func:`run_pipeline_core`.

    Mirrors the Typer ``run_pipeline`` arguments one-for-one, minus
    Typer-only concerns (callbacks, help text).
    """

    keyword: str
    location: str = "de"
    language: str = "de"
    output_dir: Optional[Path] = None
    skip_fetch: bool = False
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    tov: Optional[Path] = None
    template: Optional[Path] = None
    user_domain: Optional[str] = None
    business_context: Optional[str] = None


@dataclass
class PipelineResult:
    """Summary of a completed ``run_pipeline_core`` invocation."""

    output_dir: Path
    slug: str
    llm_configured: bool
    artifacts: dict[str, Any] = field(default_factory=dict)


OnEvent = Callable[[StageEvent], None]
OnLog = Callable[[str], None]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _noop_log(_: str) -> None:  # pragma: no cover — trivial
    return None


@contextmanager
def _stage(
    on_event: OnEvent,
    index: int,
    name: str,
    message: str,
    payload: Optional[dict[str, Any]] = None,
) -> Iterator[dict[str, Any]]:
    """Emit start/complete/error events around a stage body.

    The yielded dict can be mutated by the caller to attach artifact
    paths to the complete event's ``payload``.
    """
    start_payload = dict(payload) if payload else {}
    on_event(
        StageEvent(
            stage_index=index,
            stage_name=name,
            status="start",
            message=message,
            payload=start_payload,
        )
    )
    complete_payload: dict[str, Any] = {}
    try:
        yield complete_payload
    except BaseException as exc:  # noqa: BLE001 — we re-raise
        on_event(
            StageEvent(
                stage_index=index,
                stage_name=name,
                status="error",
                message=f"{type(exc).__name__}: {exc}",
                payload={"exception_type": type(exc).__name__},
            )
        )
        raise
    on_event(
        StageEvent(
            stage_index=index,
            stage_name=name,
            status="complete",
            message=message,
            payload=complete_payload,
        )
    )


def _emit_draft_docx(draft_md_path: Path, on_log: OnLog) -> None:
    """Convert ``draft-<slug>.md`` to a sibling ``draft-<slug>.docx``.

    Mirrors ``seo_pipeline.cli.main._emit_draft_docx`` but routes
    progress/warning text through ``on_log`` instead of a module
    logger. The helper in ``cli/main.py`` remains the source of truth
    for the CLI path (kept there for backwards compatibility with
    existing tests) — this copy exists so the orchestrator has no
    runtime dependency on the CLI module.

    The ``.md`` file is the source of truth. Any docx emission failure
    is logged and swallowed so the pipeline never breaks.
    """
    if not draft_md_path.exists():
        on_log(
            f"  skipping docx: draft markdown not found at {draft_md_path}"
        )
        return

    docx_path = draft_md_path.with_suffix(".docx")

    try:
        import pypandoc
    except ImportError:
        on_log(
            "  skipping docx: pypandoc not installed "
            "(install pypandoc-binary)"
        )
        return

    try:
        pypandoc.convert_file(
            str(draft_md_path), "docx", outputfile=str(docx_path),
        )
        on_log(f"  writing: {docx_path}")
    except Exception as exc:  # noqa: BLE001 — docx failure must not raise
        on_log(f"  docx conversion failed for {draft_md_path}: {exc}")


# ---------------------------------------------------------------------------
# Stage functions — each one is a small adapter around the underlying
# module. They import lazily so ``import seo_pipeline.orchestrator`` stays
# cheap and does not trigger heavy transitive imports (e.g. pandas).
# ---------------------------------------------------------------------------


def _stage_fetch_serp(
    cfg: PipelineConfig, out_dir: Path, on_event: OnEvent,
) -> None:
    if not cfg.skip_fetch:
        msg = "Fetching SERP data..."
    else:
        msg = "Skipping SERP fetch (cached)..."
    with _stage(on_event, 1, "fetch-serp", msg):
        if not cfg.skip_fetch:
            from seo_pipeline.serp.fetch_serp import fetch_serp as _fetch_serp

            asyncio.run(
                _fetch_serp(
                    cfg.keyword, cfg.location, cfg.language,
                    outdir=str(out_dir),
                )
            )
        else:
            serp_raw_path = out_dir / "serp-raw.json"
            if not serp_raw_path.exists():
                raise FileNotFoundError(
                    f"cached serp-raw.json not found at {serp_raw_path}"
                )


def _stage_process_serp(
    out_dir: Path, on_event: OnEvent,
) -> dict[str, Any]:
    with _stage(on_event, 2, "process-serp", "Processing SERP data...") as p:
        from seo_pipeline.serp.process_serp import process_serp as _process_serp

        serp_raw_path = out_dir / "serp-raw.json"
        serp_raw = json.loads(serp_raw_path.read_text(encoding="utf-8"))
        serp_processed = _process_serp(serp_raw, top_n=10)
        serp_processed_path = out_dir / "serp-processed.json"
        serp_processed_path.write_text(
            json.dumps(serp_processed, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        p["serp_processed_path"] = serp_processed_path
        return serp_processed


def _stage_extract_pages(
    cfg: PipelineConfig,
    out_dir: Path,
    pages_dir: Path,
    serp_processed: dict[str, Any],
    on_event: OnEvent,
) -> None:
    competitors = serp_processed.get("competitors", [])
    msg = f"Extracting {len(competitors)} competitor pages..."
    with _stage(on_event, 3, "extract-pages", msg):
        from seo_pipeline.extractor.extract_page import (
            extract_page as _extract_page,
        )

        for comp in competitors:
            comp_url = comp.get("url")
            if not comp_url:
                continue
            domain = comp.get("domain", "unknown")
            page_path = pages_dir / f"{domain}.json"
            if cfg.skip_fetch and page_path.exists():
                continue
            page_data = _extract_page(comp_url)
            page_path.write_text(
                json.dumps(page_data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )


def _stage_fetch_keywords(
    cfg: PipelineConfig, out_dir: Path, on_event: OnEvent,
) -> None:
    if not cfg.skip_fetch:
        msg = "Fetching keywords..."
    else:
        msg = "Skipping keyword fetch (cached)..."
    with _stage(on_event, 4, "fetch-keywords", msg):
        if not cfg.skip_fetch:
            from seo_pipeline.keywords.fetch_keywords import (
                fetch_keywords as _fetch_keywords,
            )

            env_path = str(
                Path(__file__).resolve().parent.parent / "api.env"
            )
            asyncio.run(
                _fetch_keywords(
                    cfg.keyword, market=cfg.location, language=cfg.language,
                    outdir=str(out_dir), env_path=env_path,
                )
            )


def _stage_process_keywords(
    cfg: PipelineConfig, out_dir: Path, on_event: OnEvent, on_log: OnLog,
) -> dict[str, Any]:
    with _stage(on_event, 5, "process-keywords", "Processing keywords..."):
        from seo_pipeline.keywords.process_keywords import (
            process_keywords as _process_keywords,
        )

        related_path = out_dir / "keywords-related-raw.json"
        suggestions_path = out_dir / "keywords-suggestions-raw.json"
        kfk_path = out_dir / "keywords-for-keywords-raw.json"
        if related_path.exists() and suggestions_path.exists():
            related_raw = json.loads(related_path.read_text(encoding="utf-8"))
            suggestions_raw = json.loads(
                suggestions_path.read_text(encoding="utf-8")
            )
            kfk_raw = (
                json.loads(kfk_path.read_text(encoding="utf-8"))
                if kfk_path.exists()
                else None
            )
            kw_processed = _process_keywords(
                related_raw, suggestions_raw, cfg.keyword, kfk_raw=kfk_raw,
            )
            kw_processed_path = out_dir / "keywords-processed.json"
            kw_processed_path.write_text(
                json.dumps(kw_processed, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            return kw_processed

        on_log("Warning: keyword files not found, skipping processing")
        return {"clusters": []}


def _stage_filter_keywords(
    cfg: PipelineConfig,
    out_dir: Path,
    kw_processed: dict[str, Any],
    serp_processed: dict[str, Any],
    on_event: OnEvent,
) -> None:
    with _stage(on_event, 6, "filter-keywords", "Filtering keywords..."):
        from seo_pipeline.keywords.filter_keywords import (
            filter_keywords as _filter_keywords,
        )

        kw_filtered = _filter_keywords(
            kw_processed, serp_processed, cfg.keyword
        )
        kw_filtered_path = out_dir / "keywords-filtered.json"
        kw_filtered_path.write_text(
            json.dumps(kw_filtered, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def _stage_analyze_content(
    cfg: PipelineConfig,
    out_dir: Path,
    pages_dir: Path,
    on_event: OnEvent,
) -> None:
    with _stage(on_event, 7, "analyze-content", "Running content analysis..."):
        from seo_pipeline.analysis.analyze_content_topics import (
            analyze_content_topics as _analyze_content_topics,
        )
        from seo_pipeline.analysis.analyze_page_structure import (
            analyze_page_structure as _analyze_page_structure,
        )

        topics = _analyze_content_topics(
            pages_dir, cfg.keyword, language=cfg.language
        )
        topics_path = out_dir / "content-topics.json"
        topics_path.write_text(
            json.dumps(topics.model_dump(), indent=2, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )

        structure = _analyze_page_structure(pages_dir)
        structure_path = out_dir / "page-structure.json"
        structure_path.write_text(
            json.dumps(structure.model_dump(), indent=2, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )


def _stage_assemble_briefing_data(
    cfg: PipelineConfig, out_dir: Path, on_event: OnEvent,
) -> Path:
    with _stage(
        on_event, 8, "assemble-briefing-data", "Assembling briefing data...",
    ):
        from seo_pipeline.analysis.assemble_briefing_data import (
            _normalize_tree,
        )  # noqa: I001
        from seo_pipeline.analysis.assemble_briefing_data import (
            assemble_briefing_data as _assemble_briefing_data,
        )

        briefing = _assemble_briefing_data(
            out_dir, market=cfg.location, language=cfg.language,
            user_domain=cfg.user_domain,
            business_context=cfg.business_context,
        )
        briefing_dict = _normalize_tree(briefing)
        briefing_path = out_dir / "briefing-data.json"
        briefing_path.write_text(
            json.dumps(briefing_dict, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return briefing_path


def _stage_summarize_briefing(
    briefing_path: Path, on_event: OnEvent, on_log: OnLog,
) -> None:
    with _stage(on_event, 9, "summarize-briefing", "Summarizing briefing..."):
        from seo_pipeline.analysis.summarize_briefing import (
            summarize_briefing as _summarize_briefing,
        )

        summary = _summarize_briefing(str(briefing_path))
        on_log(summary)


def _stage_llm_generation(
    cfg: PipelineConfig,
    out_dir: Path,
    slug: str,
    on_event: OnEvent,
    on_log: OnLog,
) -> bool:
    """Stage 10: qualitative LLM fill + briefing assembly + draft write.

    Returns ``True`` if the LLM chain ran, ``False`` if it was skipped
    due to missing credentials or a missing ``litellm`` install. The
    caller uses this flag to decide whether to run Stage 11.
    """
    msg = (
        "LLM stages "
        "(fill-qualitative, assemble-briefing-md, write-draft)..."
    )
    llm_configured = False
    with _stage(on_event, 10, "llm-generation", msg):
        from seo_pipeline.llm.config import LLMConfig

        try:
            LLMConfig.from_env()
            if importlib.util.find_spec("litellm") is None:
                raise ImportError("litellm is not installed")
            llm_configured = True
        except (ValueError, ImportError):
            llm_configured = False

        if llm_configured:
            from seo_pipeline.analysis.assemble_briefing_md import (
                assemble_briefing_md as _assemble_briefing_md,
            )
            from seo_pipeline.analysis.fill_qualitative import (
                fill_qualitative as _fill_qualitative,
            )
            from seo_pipeline.drafting.write_draft import (
                write_draft as _write_draft,
            )

            _fill_qualitative(str(out_dir))
            _assemble_briefing_md(
                str(out_dir),
                template_path=str(cfg.template) if cfg.template else None,
                tov_path=str(cfg.tov) if cfg.tov else None,
            )
            brief_path = out_dir / f"brief-{slug}.md"
            _write_draft(
                str(brief_path),
                tov_path=str(cfg.tov) if cfg.tov else None,
            )
        else:
            on_log("  LLM not configured — run these stages manually:")
            tov_flag = f" --tov {cfg.tov}" if cfg.tov else ""
            template_flag = (
                f" --template {cfg.template}" if cfg.template else ""
            )
            ud_flag = (
                f" --user-domain {cfg.user_domain}" if cfg.user_domain else ""
            )
            bc_flag = (
                f" --business-context '{cfg.business_context}'"
                if cfg.business_context
                else ""
            )
            on_log(f"  uv run seo-pipeline fill-qualitative --dir {out_dir}")
            on_log(f"  uv run seo-pipeline merge-qualitative --dir {out_dir}")
            on_log(
                f"  uv run seo-pipeline assemble-briefing-md"
                f" --dir {out_dir}{template_flag}{tov_flag}{ud_flag}{bc_flag}"
            )
            on_log(
                f"  uv run seo-pipeline write-draft"
                f" --brief {out_dir}/brief-{slug}.md{tov_flag}"
            )
            on_log(
                f"  uv run seo-pipeline fact-check"
                f" --draft {out_dir}/draft-{slug}.md"
            )

    return llm_configured


def _stage_fact_check(
    out_dir: Path, slug: str, on_event: OnEvent, on_log: OnLog,
) -> None:
    with _stage(on_event, 11, "fact-check", "Fact-checking draft..."):
        from seo_pipeline.analysis.fact_check import (
            fact_check as _fact_check,
        )
        from seo_pipeline.llm.config import LLMConfig
        from seo_pipeline.utils.load_api_config import (
            load_env as _load_env,
        )

        env_path_str = str(
            Path(__file__).resolve().parent.parent / "api.env"
        )
        try:
            api_cfg = _load_env(env_path_str)
            draft_path = out_dir / f"draft-{slug}.md"
            if draft_path.exists():
                _fact_check(
                    str(draft_path),
                    str(out_dir),
                    LLMConfig.from_env(),
                    api_cfg,
                )
            else:
                on_log(
                    "  Warning: draft not found, "
                    "skipping fact-check"
                )
        except Exception as exc:  # noqa: BLE001 — matches pre-refactor CLI
            on_log(
                f"  Warning: fact-check failed ({exc}), "
                "continuing..."
            )

        # Emit a sibling .docx from the (potentially fact-check-modified)
        # draft markdown. Runs whether fact-check succeeded or failed —
        # we want a docx of whatever state the .md ends up in. Any docx
        # failure is logged and swallowed so the pipeline never breaks.
        _emit_draft_docx(out_dir / f"draft-{slug}.md", on_log)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_pipeline_core(
    config: PipelineConfig,
    on_event: OnEvent,
    on_log: Optional[OnLog] = None,
) -> PipelineResult:
    """Run the 11-stage SEO content pipeline end-to-end.

    Parameters
    ----------
    config:
        Immutable bundle of pipeline inputs; see :class:`PipelineConfig`.
    on_event:
        Synchronously invoked for each :class:`StageEvent`. Called at
        least twice per stage — once with ``status="start"`` before the
        stage body runs, once with ``status="complete"`` after it
        succeeds, or ``status="error"`` if it raises.
    on_log:
        Optional callback for non-stage stderr-style messages (warnings,
        the end-of-run summary, the LLM-not-configured fallback
        instructions). Defaults to a no-op.

    Returns
    -------
    PipelineResult
        Summary of the run (output directory, slug, whether LLM stages
        ran).

    Raises
    ------
    Any exception raised by a stage body. The corresponding ``error``
    event is emitted before the exception propagates.
    """
    import os

    from seo_pipeline.utils.slugify import slugify

    log = on_log or _noop_log

    slug = slugify(config.keyword)
    date_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    out_dir = (
        Path(config.output_dir)
        if config.output_dir is not None
        else Path("output") / f"{date_str}_{slug}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    pages_dir = out_dir / "pages"
    pages_dir.mkdir(exist_ok=True)

    if config.llm_provider:
        os.environ["LLM_PROVIDER"] = config.llm_provider
    if config.llm_model:
        os.environ["LLM_MODEL"] = config.llm_model

    # --- Stage 1: Fetch SERP ---
    _stage_fetch_serp(config, out_dir, on_event)

    # --- Stage 2: Process SERP ---
    serp_processed = _stage_process_serp(out_dir, on_event)

    # --- Stage 3: Extract competitor pages ---
    _stage_extract_pages(
        config, out_dir, pages_dir, serp_processed, on_event,
    )

    # --- Stage 4: Fetch keywords ---
    _stage_fetch_keywords(config, out_dir, on_event)

    # --- Stage 5: Process keywords ---
    kw_processed = _stage_process_keywords(config, out_dir, on_event, log)

    # --- Stage 6: Filter keywords ---
    _stage_filter_keywords(
        config, out_dir, kw_processed, serp_processed, on_event,
    )

    # --- Stage 7: Content analysis (topics + structure) ---
    _stage_analyze_content(config, out_dir, pages_dir, on_event)

    # --- Stage 8: Assemble briefing data ---
    briefing_path = _stage_assemble_briefing_data(config, out_dir, on_event)

    # --- Stage 9: Summarize briefing ---
    _stage_summarize_briefing(briefing_path, on_event, log)

    # --- Stage 10: LLM chain (qualitative + briefing md + draft) ---
    llm_configured = _stage_llm_generation(
        config, out_dir, slug, on_event, log,
    )

    # --- Stage 11: Fact-check draft + docx emission ---
    # Stage 11 only runs when the LLM chain produced a draft; otherwise
    # we still emit a start+complete pair so the event sequence is
    # invariant regardless of LLM availability. The no-LLM events
    # carry ``skipped_no_llm=True`` in their payload so CLI consumers
    # that want byte-for-byte pre-refactor stderr can suppress them.
    if llm_configured:
        _stage_fact_check(out_dir, slug, on_event, log)
    else:
        skip_payload = {"skipped_no_llm": True}
        on_event(
            StageEvent(
                stage_index=11,
                stage_name="fact-check",
                status="start",
                message="Fact-checking draft...",
                payload=skip_payload,
            )
        )
        on_event(
            StageEvent(
                stage_index=11,
                stage_name="fact-check",
                status="complete",
                message="Fact-checking draft...",
                payload=skip_payload,
            )
        )

    log(f"\nPipeline complete. Output directory: {out_dir}")

    return PipelineResult(
        output_dir=out_dir,
        slug=slug,
        llm_configured=llm_configured,
    )


__all__ = [
    "STAGE_TOTAL",
    "OnEvent",
    "OnLog",
    "PipelineConfig",
    "PipelineResult",
    "StageEvent",
    "StageStatus",
    "run_pipeline_core",
]
