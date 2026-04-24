"""Competitor analysis stage page.

Wraps SERP fetch/process, per-competitor page extraction, and the two
content-analysis steps:
:func:`seo_pipeline.serp.fetch_serp.fetch_serp` ->
:func:`seo_pipeline.serp.process_serp.process_serp` ->
:func:`seo_pipeline.extractor.extract_page.extract_page` (per URL) ->
:func:`seo_pipeline.analysis.analyze_content_topics.analyze_content_topics` +
:func:`seo_pipeline.analysis.analyze_page_structure.analyze_page_structure`.

The page writes artifacts into the selected run directory using the same
filenames the orchestrator writes, so a completed run here is
interchangeable with a run done end-to-end from the pipeline page.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import streamlit as st

from seo_pipeline.analysis.analyze_content_topics import analyze_content_topics
from seo_pipeline.analysis.analyze_page_structure import analyze_page_structure
from seo_pipeline.extractor.extract_page import extract_page
from seo_pipeline.serp.fetch_serp import fetch_serp
from seo_pipeline.serp.process_serp import process_serp
from streamlit_app._stage_form import (
    gate_open,
    pick_run_dir,
    render_artifact_download,
    render_artifact_preview,
    render_closed_gate,
)


def _run_fetch_serp(
    *, keyword: str, market: str, language: str, outdir: Path,
) -> None:
    asyncio.run(
        fetch_serp(keyword, market, language, outdir=str(outdir)),
    )


def _run_process_serp(run_dir: Path) -> tuple[Path, dict]:
    raw_path = run_dir / "serp-raw.json"
    if not raw_path.exists():
        raise FileNotFoundError(
            "serp-raw.json missing — fetch SERP first."
        )
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    processed = process_serp(raw, top_n=10)
    out = run_dir / "serp-processed.json"
    out.write_text(
        json.dumps(processed, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out, processed


def _run_extract_pages(run_dir: Path, serp_processed: dict) -> int:
    """Download each competitor page and save it under ``pages/``.

    Returns the number of pages written. Pages with existing files are
    left untouched — useful when re-running after a transient extractor
    failure.
    """
    pages_dir = run_dir / "pages"
    pages_dir.mkdir(exist_ok=True)
    competitors = serp_processed.get("competitors", [])
    written = 0
    for comp in competitors:
        url = comp.get("url")
        if not url:
            continue
        domain = comp.get("domain", "unknown")
        page_path = pages_dir / f"{domain}.json"
        if page_path.exists():
            continue
        page_data = extract_page(url)
        page_path.write_text(
            json.dumps(page_data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        written += 1
    return written


def _run_analyze(run_dir: Path, *, seed: str, language: str) -> list[Path]:
    """Run both content-topics and page-structure analyses."""
    pages_dir = run_dir / "pages"
    if not pages_dir.is_dir():
        raise FileNotFoundError(
            "pages/ directory missing — extract competitor pages first."
        )

    topics = analyze_content_topics(pages_dir, seed, language=language)
    topics_path = run_dir / "content-topics.json"
    topics_path.write_text(
        json.dumps(topics.model_dump(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    structure = analyze_page_structure(pages_dir)
    structure_path = run_dir / "page-structure.json"
    structure_path.write_text(
        json.dumps(structure.model_dump(), indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    return [topics_path, structure_path]


def render() -> None:
    st.title("03 Competitor Analysis")
    st.caption(
        "Fetch SERP data, extract the top competitor pages, and run "
        "content/structure analysis into a run directory."
    )

    if not gate_open():
        render_closed_gate("03 Competitor Analysis")
        return

    run_dir = pick_run_dir(
        key="competitor",
        help_text=(
            "Pick an existing run directory, or enter a new path — it will "
            "be created on first fetch."
        ),
    )

    with st.form("competitor_form"):
        seed = st.text_input("Seed keyword")
        col1, col2 = st.columns(2)
        with col1:
            market = st.text_input("Market / location", value="de")
        with col2:
            language = st.text_input("Language", value="de")

        st.subheader("Steps to run")
        do_fetch = st.checkbox("Fetch SERP (DataForSEO)", value=False)
        do_process = st.checkbox("Process SERP (deterministic)", value=True)
        do_extract = st.checkbox(
            "Extract competitor pages (HTTP)", value=True,
            help="Skips pages already present in pages/ subdirectory.",
        )
        do_analyze = st.checkbox(
            "Analyze content topics + page structure", value=True,
        )

        submitted = st.form_submit_button("Run selected steps")

    if not submitted:
        return

    if run_dir is None:
        st.error("Please select or enter a run directory.")
        return
    if not seed.strip() and (do_fetch or do_analyze):
        st.error("Seed keyword is required for fetch and analysis steps.")
        return

    run_dir.mkdir(parents=True, exist_ok=True)

    # --- Fetch SERP --------------------------------------------------------
    if do_fetch:
        with st.status("Fetching SERP...", expanded=True) as status:
            try:
                _run_fetch_serp(
                    keyword=seed.strip(),
                    market=market.strip() or "de",
                    language=language.strip() or "de",
                    outdir=run_dir,
                )
                status.update(label="Fetch SERP complete", state="complete")
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))
                status.update(label="Fetch SERP failed", state="error")
                return

    # --- Process SERP ------------------------------------------------------
    serp_processed: dict | None = None
    if do_process:
        try:
            out, serp_processed = _run_process_serp(run_dir)
            st.success(f"Processed SERP: `{out.name}`")
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))
            return

    # --- Extract pages -----------------------------------------------------
    if do_extract:
        try:
            if serp_processed is None:
                serp_processed_path = run_dir / "serp-processed.json"
                if not serp_processed_path.exists():
                    raise FileNotFoundError(
                        "serp-processed.json missing — run 'Process SERP' first."
                    )
                serp_processed = json.loads(
                    serp_processed_path.read_text(encoding="utf-8")
                )
            with st.status(
                "Extracting competitor pages...", expanded=True,
            ) as status:
                written = _run_extract_pages(run_dir, serp_processed)
                status.update(
                    label=f"Extracted {written} new page(s)",
                    state="complete",
                )
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))
            return

    # --- Analyze -----------------------------------------------------------
    if do_analyze:
        try:
            paths = _run_analyze(
                run_dir,
                seed=seed.strip(),
                language=language.strip() or "de",
            )
            names = ", ".join(f"`{p.name}`" for p in paths)
            st.success(f"Analysis complete: {names}")
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))
            return

    # --- Artifacts ---------------------------------------------------------
    st.divider()
    st.subheader("Artifacts")
    for filename, label in [
        ("serp-raw.json", "SERP (raw)"),
        ("serp-processed.json", "SERP (processed)"),
        ("content-topics.json", "Content topics"),
        ("page-structure.json", "Page structure"),
    ]:
        artifact = run_dir / filename
        if not artifact.is_file():
            continue
        with st.expander(f"{label} — `{filename}`", expanded=False):
            render_artifact_preview(
                artifact, label=label, language="json", max_chars=20000,
            )
            render_artifact_download(
                artifact, label=f"Download {filename}", key_prefix="comp",
            )

    pages_dir = run_dir / "pages"
    if pages_dir.is_dir():
        page_files = sorted(p for p in pages_dir.iterdir() if p.suffix == ".json")
        if page_files:
            with st.expander(
                f"Competitor pages ({len(page_files)} files)", expanded=False,
            ):
                for p in page_files:
                    st.write(f"- `pages/{p.name}`")


render()
