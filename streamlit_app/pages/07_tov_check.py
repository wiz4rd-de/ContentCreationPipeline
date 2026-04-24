"""ToV-check stage page — audit a draft against tone-of-voice guidelines.

Wraps :func:`seo_pipeline.analysis.tov_check.tov_check`. The page picks a
run directory (auto-filling the draft path) or accepts a manual path,
optionally lets the user point to a specific ToV file, and runs the audit.

Output artifacts are ``tov-check-report.md`` and ``tov-check-report.json``
in the draft's parent directory (or a user-supplied output directory).
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from seo_pipeline.analysis.tov_check import tov_check
from seo_pipeline.llm.config import LLMConfig
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
        f"ToV check will use **{provider} / {model}**. "
        "Override in Settings if that's not what you want."
    )


def render() -> None:
    st.title("07 ToV Check")
    st.caption(
        "Audit a draft against Tone-of-Voice guidelines and produce a "
        "compliance report."
    )

    if not gate_open():
        render_closed_gate("07 ToV Check")
        return

    _show_llm_banner()

    run_dir = pick_run_dir(key="tov_check")

    default_draft = ""
    if run_dir is not None:
        slug = resolve_slug(run_dir)
        candidate = run_dir / f"draft-{slug}.md"
        if candidate.is_file():
            default_draft = str(candidate)

    with st.form("tov_check_form"):
        draft_path_str = st.text_input(
            "Draft markdown path",
            value=default_draft,
            help=(
                "Path to draft-<slug>.md. Pre-filled from the selected run "
                "directory when one exists."
            ),
        )
        tov_path_str = st.text_input(
            "ToV file path (optional)",
            help=(
                "Markdown file with tone-of-voice rules. Defaults to "
                "`templates/DT_ToV_v3.md` relative to the project root."
            ),
        )
        out_dir_str = st.text_input(
            "Output directory (optional)",
            help=(
                "Where to write tov-check-report.{md,json}. Defaults to "
                "the draft's parent directory."
            ),
        )

        submitted = st.form_submit_button("Run ToV check")

    if not submitted:
        return

    if not draft_path_str.strip():
        st.error("Draft path is required.")
        return

    draft_path = Path(draft_path_str.strip())
    if not draft_path.is_file():
        st.error(f"Draft file not found: `{draft_path}`")
        return

    tov_arg = tov_path_str.strip() or None
    out_dir_arg = out_dir_str.strip() or None
    out_dir = Path(out_dir_arg) if out_dir_arg else draft_path.parent

    with st.status("Running ToV check...", expanded=True) as status:
        try:
            llm_config = LLMConfig.from_env()
            tov_check(
                str(draft_path),
                out_dir=out_dir_arg,
                llm_config=llm_config,
                tov_path=tov_arg,
            )
            status.update(label="ToV check complete", state="complete")
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))
            status.update(label="ToV check failed", state="error")
            return

    st.divider()
    st.subheader("Artifacts")
    report_md = out_dir / "tov-check-report.md"
    report_json = out_dir / "tov-check-report.json"

    if report_md.is_file():
        with st.expander("Report — `tov-check-report.md`", expanded=True):
            render_artifact_preview(report_md, label="report")
            render_artifact_download(
                report_md,
                label="Download tov-check-report.md",
                key_prefix="tov",
            )

    if report_json.is_file():
        with st.expander(
            "Report JSON — `tov-check-report.json`", expanded=False,
        ):
            render_artifact_preview(
                report_json, label="report json",
                language="json", max_chars=20000,
            )
            render_artifact_download(
                report_json,
                label="Download tov-check-report.json",
                key_prefix="tov",
            )

    if not report_md.is_file() and not report_json.is_file():
        st.warning(
            f"No ToV reports found under `{out_dir}`. Check the logs above."
        )


render()
