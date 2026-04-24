"""Briefing stage page — assembly, qualitative fill, and markdown build.

Wraps:
:func:`seo_pipeline.analysis.assemble_briefing_data.assemble_briefing_data`
(deterministic aggregation),
:func:`seo_pipeline.analysis.fill_qualitative.fill_qualitative`
(LLM call) and
:func:`seo_pipeline.analysis.assemble_briefing_md.assemble_briefing_md`
(LLM call that emits the final ``brief-<slug>.md``).

The ``_fill_qualitative`` and ``_assemble_briefing_md`` calls both invoke
the configured LLM; we surface which provider/model will be used so the
user knows what they are about to spend on.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st

from seo_pipeline.analysis.assemble_briefing_data import (
    _normalize_tree,
    assemble_briefing_data,
)
from seo_pipeline.analysis.assemble_briefing_md import assemble_briefing_md
from seo_pipeline.analysis.fill_qualitative import fill_qualitative
from streamlit_app._stage_form import (
    gate_open,
    pick_run_dir,
    render_artifact_download,
    render_artifact_preview,
    render_closed_gate,
    resolve_slug,
)


def _run_assemble_data(
    run_dir: Path,
    *,
    market: str | None,
    language: str | None,
    user_domain: str | None,
    business_context: str | None,
) -> Path:
    briefing = assemble_briefing_data(
        run_dir,
        market=market,
        language=language,
        user_domain=user_domain,
        business_context=business_context,
    )
    briefing_dict = _normalize_tree(briefing)
    out = run_dir / "briefing-data.json"
    out.write_text(
        json.dumps(briefing_dict, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out


def _show_llm_banner() -> None:
    """Show the provider/model the next LLM call will use.

    Reads from ``os.environ`` after ``gate_open`` has re-applied
    ``api.env``. Avoids importing ``LLMConfig`` here — we just want the
    user-facing labels.
    """
    provider = os.environ.get("LLM_PROVIDER") or "(unset)"
    model = os.environ.get("LLM_MODEL") or "(unset)"
    st.info(
        f"LLM calls on this page will use **{provider} / {model}**. "
        "Override in Settings if that's not what you want."
    )


def render() -> None:
    st.title("04 Briefing")
    st.caption(
        "Build the structured briefing data, fill qualitative fields via "
        "LLM, and assemble the final `brief-<slug>.md`."
    )

    if not gate_open():
        render_closed_gate("04 Briefing")
        return

    _show_llm_banner()

    run_dir = pick_run_dir(key="briefing")

    with st.form("briefing_form"):
        st.subheader("Metadata overrides (optional)")
        col1, col2 = st.columns(2)
        with col1:
            market = st.text_input("Market / location", value="de")
        with col2:
            language = st.text_input("Language", value="de")

        user_domain = st.text_input(
            "User domain (optional)",
            help="Domain to exclude from competitor analysis references.",
        )
        business_context = st.text_area(
            "Business context (optional)",
            help="Free-form context passed through to LLM prompts.",
        )

        st.subheader("Template / tone-of-voice (optional)")
        template_path_str = st.text_input(
            "Briefing template path",
            help="Markdown template used by the assembly prompt.",
        )
        tov_path_str = st.text_input(
            "Tone-of-voice path",
            help="Markdown file describing the target tone of voice.",
        )

        st.subheader("Steps to run")
        do_assemble_data = st.checkbox(
            "Assemble briefing data (deterministic)", value=True,
        )
        do_fill_qual = st.checkbox(
            "Fill qualitative fields (LLM)", value=True,
        )
        do_assemble_md = st.checkbox(
            "Assemble brief-<slug>.md (LLM)", value=True,
        )

        submitted = st.form_submit_button("Run selected steps")

    if not submitted:
        return

    if run_dir is None:
        st.error("Please select or enter a run directory.")
        return

    run_dir.mkdir(parents=True, exist_ok=True)
    slug = resolve_slug(run_dir)

    tov_arg = tov_path_str.strip() or None
    template_arg = template_path_str.strip() or None

    # --- Assemble briefing data ------------------------------------------
    if do_assemble_data:
        try:
            out = _run_assemble_data(
                run_dir,
                market=market.strip() or None,
                language=language.strip() or None,
                user_domain=user_domain.strip() or None,
                business_context=business_context.strip() or None,
            )
            st.success(f"Assembled briefing data: `{out.name}`")
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))
            return

    # --- Fill qualitative (LLM) ------------------------------------------
    if do_fill_qual:
        with st.status("Calling LLM for qualitative fields...", expanded=True) as status:
            try:
                fill_qualitative(str(run_dir))
                status.update(
                    label="Qualitative fields filled", state="complete",
                )
            except SystemExit as exc:
                # fill_qualitative uses sys.exit(1) on missing input.
                st.error(
                    f"fill_qualitative exited with code {exc.code}. "
                    "Check briefing-data.json is present."
                )
                status.update(label="Failed", state="error")
                return
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))
                status.update(label="Failed", state="error")
                return

    # --- Assemble briefing md (LLM) --------------------------------------
    if do_assemble_md:
        with st.status("Calling LLM for briefing assembly...", expanded=True) as status:
            try:
                assemble_briefing_md(
                    str(run_dir),
                    template_path=template_arg,
                    tov_path=tov_arg,
                )
                status.update(label="Briefing markdown ready", state="complete")
            except SystemExit as exc:
                st.error(
                    f"assemble_briefing_md exited with code {exc.code}. "
                    "Check that fill_qualitative has been run."
                )
                status.update(label="Failed", state="error")
                return
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))
                status.update(label="Failed", state="error")
                return

    # --- Artifacts --------------------------------------------------------
    st.divider()
    st.subheader("Artifacts")

    briefing_data_path = run_dir / "briefing-data.json"
    if briefing_data_path.is_file():
        with st.expander("Briefing data — `briefing-data.json`", expanded=False):
            render_artifact_preview(
                briefing_data_path,
                label="briefing-data",
                language="json",
                max_chars=20000,
            )
            render_artifact_download(
                briefing_data_path,
                label="Download briefing-data.json",
                key_prefix="brief",
            )

    qualitative_path = run_dir / "qualitative.json"
    if qualitative_path.is_file():
        with st.expander("Qualitative — `qualitative.json`", expanded=False):
            render_artifact_preview(
                qualitative_path,
                label="qualitative",
                language="json",
                max_chars=20000,
            )
            render_artifact_download(
                qualitative_path,
                label="Download qualitative.json",
                key_prefix="brief",
            )

    brief_md = run_dir / f"brief-{slug}.md"
    if brief_md.is_file():
        with st.expander(f"Briefing markdown — `brief-{slug}.md`", expanded=True):
            render_artifact_preview(brief_md, label="brief")
            render_artifact_download(
                brief_md,
                label=f"Download brief-{slug}.md",
                key_prefix="brief",
            )


render()
