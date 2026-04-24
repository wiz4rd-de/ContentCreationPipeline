"""Keyword research stage page.

Wraps the deterministic keyword pipeline:
:func:`seo_pipeline.keywords.fetch_keywords.fetch_keywords` ->
:func:`seo_pipeline.keywords.process_keywords.process_keywords` ->
:func:`seo_pipeline.keywords.filter_keywords.filter_keywords`.

The user picks an existing run directory (or types a fresh one) and a seed
keyword; on submit we run as many of the three steps as the on-disk inputs
allow. Each step's artifact is surfaced inline with a download button.

Gate: the app-level first-run gate hides this page from the nav when
``api.env`` is incomplete. We also re-check the gate here as defense in
depth for deep links.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import streamlit as st

from seo_pipeline.keywords.fetch_keywords import fetch_keywords
from seo_pipeline.keywords.filter_keywords import filter_keywords
from seo_pipeline.keywords.process_keywords import process_keywords
from streamlit_app._stage_form import (
    gate_open,
    pick_run_dir,
    render_artifact_download,
    render_artifact_preview,
    render_closed_gate,
)


def _run_fetch(
    *, keyword: str, market: str, language: str, outdir: Path,
) -> None:
    """Invoke the async ``fetch_keywords`` coroutine from a sync page."""
    env_path = str(Path.cwd() / "api.env")
    asyncio.run(
        fetch_keywords(
            keyword,
            market=market,
            language=language,
            outdir=str(outdir),
            env_path=env_path,
        )
    )


def _run_process(run_dir: Path, seed: str) -> Path:
    """Re-run ``process_keywords`` over the cached raw responses."""
    related_path = run_dir / "keywords-related-raw.json"
    suggestions_path = run_dir / "keywords-suggestions-raw.json"
    kfk_path = run_dir / "keywords-for-keywords-raw.json"

    if not related_path.exists() or not suggestions_path.exists():
        raise FileNotFoundError(
            "Missing keywords-related-raw.json or "
            "keywords-suggestions-raw.json in run directory. Fetch first."
        )

    related_raw = json.loads(related_path.read_text(encoding="utf-8"))
    suggestions_raw = json.loads(
        suggestions_path.read_text(encoding="utf-8")
    )
    kfk_raw = (
        json.loads(kfk_path.read_text(encoding="utf-8"))
        if kfk_path.exists()
        else None
    )

    result = process_keywords(
        related_raw, suggestions_raw, seed, kfk_raw=kfk_raw,
    )
    out_path = run_dir / "keywords-processed.json"
    out_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out_path


def _run_filter(run_dir: Path, seed: str) -> Path:
    """Re-run ``filter_keywords`` over the processed keyword + SERP files."""
    processed_path = run_dir / "keywords-processed.json"
    serp_path = run_dir / "serp-processed.json"
    if not processed_path.exists():
        raise FileNotFoundError(
            "keywords-processed.json missing — run 'Process' first."
        )
    if not serp_path.exists():
        raise FileNotFoundError(
            "serp-processed.json missing — run SERP processing on the "
            "Competitor Analysis page first."
        )
    kw_processed = json.loads(processed_path.read_text(encoding="utf-8"))
    serp_processed = json.loads(serp_path.read_text(encoding="utf-8"))

    result = filter_keywords(kw_processed, serp_processed, seed)
    out_path = run_dir / "keywords-filtered.json"
    out_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out_path


def render() -> None:
    st.title("02 Keyword Research")
    st.caption(
        "Fetch, process, and filter keywords for a run. Each step writes "
        "its artifact into the selected run directory."
    )

    if not gate_open():
        render_closed_gate("02 Keyword Research")
        return

    run_dir = pick_run_dir(
        key="kw_research",
        help_text=(
            "Pick an existing run directory, or enter a new path — it will "
            "be created on first fetch."
        ),
    )

    with st.form("kw_research_form"):
        seed = st.text_input(
            "Seed keyword",
            help="Keyword to expand. Required for fetch/process/filter.",
        )
        col1, col2 = st.columns(2)
        with col1:
            market = st.text_input("Market / location", value="de")
        with col2:
            language = st.text_input("Language", value="de")

        st.subheader("Steps to run")
        do_fetch = st.checkbox(
            "Fetch raw keywords (DataForSEO)", value=False,
            help=(
                "Hits the DataForSEO related/suggestions/KFK endpoints. "
                "Skip if the raw files already exist."
            ),
        )
        do_process = st.checkbox(
            "Process (deterministic)", value=True,
        )
        do_filter = st.checkbox(
            "Filter (deterministic)", value=True,
            help="Requires serp-processed.json from the Competitor Analysis page.",
        )

        submitted = st.form_submit_button("Run selected steps")

    if not submitted:
        return

    if run_dir is None:
        st.error("Please select or enter a run directory.")
        return
    if not seed.strip():
        st.error("Seed keyword is required.")
        return

    run_dir.mkdir(parents=True, exist_ok=True)

    # --- Fetch -------------------------------------------------------------
    if do_fetch:
        with st.status("Fetching keywords...", expanded=True) as status:
            try:
                _run_fetch(
                    keyword=seed.strip(),
                    market=market.strip() or "de",
                    language=language.strip() or "de",
                    outdir=run_dir,
                )
                status.update(label="Fetch complete", state="complete")
            except Exception as exc:  # noqa: BLE001 — surface everything
                st.error(str(exc))
                status.update(label="Fetch failed", state="error")
                return

    # --- Process -----------------------------------------------------------
    if do_process:
        try:
            processed_path = _run_process(run_dir, seed.strip())
            st.success(f"Processed: `{processed_path.name}`")
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))
            return

    # --- Filter ------------------------------------------------------------
    if do_filter:
        try:
            filtered_path = _run_filter(run_dir, seed.strip())
            st.success(f"Filtered: `{filtered_path.name}`")
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))
            return

    # --- Artifacts ---------------------------------------------------------
    st.divider()
    st.subheader("Artifacts")
    for filename, label in [
        ("keywords-related-raw.json", "Related (raw)"),
        ("keywords-suggestions-raw.json", "Suggestions (raw)"),
        ("keywords-for-keywords-raw.json", "KFK (raw)"),
        ("keywords-processed.json", "Processed"),
        ("keywords-filtered.json", "Filtered"),
    ]:
        artifact = run_dir / filename
        if not artifact.is_file():
            continue
        with st.expander(f"{label} — `{filename}`", expanded=False):
            render_artifact_preview(
                artifact, label=label, language="json", max_chars=20000,
            )
            render_artifact_download(
                artifact, label=f"Download {filename}", key_prefix="kw",
            )


render()
