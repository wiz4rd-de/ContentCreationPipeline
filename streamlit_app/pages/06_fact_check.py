"""Fact-check stage page — verify claims in a draft against the web.

Wraps :func:`seo_pipeline.analysis.fact_check.fact_check`. The page picks
a run directory (auto-filling the draft path) or accepts a manual path,
loads the LLM + DataForSEO credentials from env, and runs the fact-check.

Output artifacts are ``fact-check-report.md`` and ``fact-check-report.json``
in the draft's parent directory.
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from seo_pipeline.analysis.fact_check import fact_check
from seo_pipeline.llm.config import LLMConfig
from seo_pipeline.utils.load_api_config import load_env
from streamlit_app._stage_form import (
    gate_open,
    pick_run_dir,
    render_artifact_download,
    render_artifact_preview,
    render_closed_gate,
    resolve_slug,
)


def _show_llm_banner() -> None:
    provider = os.environ.get("LLM_PROVIDER") or "(unset)"
    model = os.environ.get("LLM_MODEL") or "(unset)"
    st.info(
        f"Fact-check will use **{provider} / {model}** plus DataForSEO "
        "for web search. Override credentials in Settings."
    )


def render() -> None:
    st.title("06 Fact Check")
    st.caption(
        "Verify factual claims in a draft against web sources and generate "
        "a report."
    )

    if not gate_open():
        render_closed_gate("06 Fact Check")
        return

    _show_llm_banner()

    run_dir = pick_run_dir(key="fact_check")

    default_draft = ""
    if run_dir is not None:
        slug = resolve_slug(run_dir)
        candidate = run_dir / f"draft-{slug}.md"
        if candidate.is_file():
            default_draft = str(candidate)

    with st.form("fact_check_form"):
        draft_path_str = st.text_input(
            "Draft markdown path",
            value=default_draft,
            help=(
                "Path to draft-<slug>.md. Pre-filled from the selected run "
                "directory when one exists."
            ),
        )
        out_dir_str = st.text_input(
            "Output directory (optional)",
            help=(
                "Where to write fact-check-report.{md,json}. Defaults to "
                "the draft's parent directory."
            ),
        )

        submitted = st.form_submit_button("Run fact-check")

    if not submitted:
        return

    if not draft_path_str.strip():
        st.error("Draft path is required.")
        return

    draft_path = Path(draft_path_str.strip())
    if not draft_path.is_file():
        st.error(f"Draft file not found: `{draft_path}`")
        return

    out_dir = (
        Path(out_dir_str.strip()) if out_dir_str.strip() else draft_path.parent
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    with st.status("Running fact-check...", expanded=True) as status:
        try:
            llm_config = LLMConfig.from_env()
            api_config = load_env(str(Path.cwd() / "api.env"))
            fact_check(
                str(draft_path),
                str(out_dir),
                llm_config,
                api_config,
            )
            status.update(label="Fact-check complete", state="complete")
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))
            status.update(label="Fact-check failed", state="error")
            return

    st.divider()
    st.subheader("Artifacts")
    report_md = out_dir / "fact-check-report.md"
    report_json = out_dir / "fact-check-report.json"

    if report_md.is_file():
        with st.expander("Report — `fact-check-report.md`", expanded=True):
            render_artifact_preview(report_md, label="report")
            render_artifact_download(
                report_md,
                label="Download fact-check-report.md",
                key_prefix="fc",
            )

    if report_json.is_file():
        with st.expander(
            "Report JSON — `fact-check-report.json`", expanded=False,
        ):
            render_artifact_preview(
                report_json, label="report json",
                language="json", max_chars=20000,
            )
            render_artifact_download(
                report_json,
                label="Download fact-check-report.json",
                key_prefix="fc",
            )

    if not report_md.is_file() and not report_json.is_file():
        st.warning(
            f"No fact-check reports found under `{out_dir}`. "
            "Check the logs above."
        )


render()
