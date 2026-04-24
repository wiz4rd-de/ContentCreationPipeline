"""Draft stage page — generate an article draft from a briefing markdown.

Wraps :func:`seo_pipeline.drafting.write_draft.write_draft`. The user picks
a run directory (so we can default the brief path to
``brief-<slug>.md``) or types a full brief path, optionally supplies a
tone-of-voice file, and triggers the LLM call.

Output artifact is ``draft-<slug>.md`` in the brief's parent directory.
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from seo_pipeline.drafting.write_draft import write_draft
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
        f"Draft generation will use **{provider} / {model}**. "
        "Override in Settings if that's not what you want."
    )


def render() -> None:
    st.title("05 Draft")
    st.caption(
        "Generate a full article draft from a briefing markdown file via "
        "the configured LLM."
    )

    if not gate_open():
        render_closed_gate("05 Draft")
        return

    _show_llm_banner()

    run_dir = pick_run_dir(key="draft")

    default_brief = ""
    default_slug = ""
    if run_dir is not None:
        default_slug = resolve_slug(run_dir)
        candidate = run_dir / f"brief-{default_slug}.md"
        if candidate.is_file():
            default_brief = str(candidate)

    with st.form("draft_form"):
        brief_path_str = st.text_input(
            "Briefing markdown path",
            value=default_brief,
            help=(
                "Path to the brief-<slug>.md file. Pre-filled from the "
                "selected run directory when one exists."
            ),
        )
        tov_path_str = st.text_input(
            "Tone-of-voice path (optional)",
            help="Markdown file describing the target tone of voice.",
        )
        instructions = st.text_area(
            "Special instructions (optional)",
            help="e.g. 'use du instead of Sie'.",
        )

        submitted = st.form_submit_button("Generate draft")

    if not submitted:
        return

    if not brief_path_str.strip():
        st.error("Briefing path is required.")
        return

    brief_path = Path(brief_path_str.strip())
    if not brief_path.is_file():
        st.error(f"Briefing file not found: `{brief_path}`")
        return

    tov_arg = tov_path_str.strip() or None
    instructions_arg = instructions.strip() or None

    with st.status("Calling LLM for draft...", expanded=True) as status:
        try:
            write_draft(
                str(brief_path),
                tov_path=tov_arg,
                instructions=instructions_arg,
            )
            status.update(label="Draft complete", state="complete")
        except SystemExit as exc:
            st.error(
                f"write_draft exited with code {exc.code}. "
                "Check the briefing path and tone-of-voice file exist."
            )
            status.update(label="Failed", state="error")
            return
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))
            status.update(label="Failed", state="error")
            return

    # Locate the artifact write_draft produced.
    slug_from_brief = brief_path.stem.removeprefix("brief-") or default_slug
    draft_path = brief_path.parent / f"draft-{slug_from_brief}.md"

    st.divider()
    st.subheader("Artifact")
    if draft_path.is_file():
        st.success(f"Draft written: `{draft_path}`")
        render_artifact_preview(draft_path, label="draft")
        render_artifact_download(
            draft_path,
            label=f"Download draft-{slug_from_brief}.md",
            key_prefix="draft",
        )
    else:
        st.warning(
            f"Expected draft at `{draft_path}` but it was not created."
        )


render()
