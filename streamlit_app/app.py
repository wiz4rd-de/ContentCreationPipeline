"""Streamlit entry point for the SEO Content Pipeline UI.

Launch with::

    uv run streamlit run streamlit_app/app.py

Renders navigation via :func:`st.navigation`. When required credentials are
missing from ``api.env``, only the Settings page is shown; otherwise the full
nav is available: Run Pipeline (end-to-end), individual stage pages
02–07 (keyword research, competitor analysis, briefing, draft, fact-check,
ToV check), and the Past Runs browser.
"""

from __future__ import annotations

import streamlit as st

from streamlit_app.settings_io import (
    apply_to_process_env,
    load_api_env,
    missing_required,
)

st.set_page_config(
    page_title="SEO Content Pipeline",
    layout="wide",
)

# Apply the on-disk api.env to os.environ once per session so pipeline imports
# see the same values the user configured. Reloading api.env on every run lets
# edits made in the Settings page take effect after st.rerun without a process
# restart.
_current_env = load_api_env()
apply_to_process_env(_current_env)


def _build_pages(gate_open: bool) -> dict[str, list]:
    settings_page = st.Page(
        "pages/99_settings.py",
        title="Settings",
        icon=":material/settings:",
        default=not gate_open,
    )

    if not gate_open:
        return {"Setup": [settings_page]}

    run_pipeline_page = st.Page(
        "pages/01_run_pipeline.py",
        title="01 Run Pipeline",
        url_path="pipeline/run",
        default=True,
    )
    keyword_research_page = st.Page(
        "pages/02_keyword_research.py",
        title="02 Keyword Research",
        url_path="pipeline/keywords",
    )
    competitor_analysis_page = st.Page(
        "pages/03_competitor_analysis.py",
        title="03 Competitor Analysis",
        url_path="pipeline/competitors",
    )
    briefing_page = st.Page(
        "pages/04_briefing.py",
        title="04 Briefing",
        url_path="pipeline/briefing",
    )
    draft_page = st.Page(
        "pages/05_draft.py",
        title="05 Draft",
        url_path="pipeline/draft",
    )
    fact_check_page = st.Page(
        "pages/06_fact_check.py",
        title="06 Fact Check",
        url_path="pipeline/fact_check",
    )
    tov_check_page = st.Page(
        "pages/07_tov_check.py",
        title="07 ToV Check",
        url_path="pipeline/tov_check",
    )
    past_runs_page = st.Page(
        "pages/08_past_runs.py",
        title="08 Past Runs",
        url_path="pipeline/past_runs",
    )
    return {
        "Pipeline": [
            run_pipeline_page,
            keyword_research_page,
            competitor_analysis_page,
            briefing_page,
            draft_page,
            fact_check_page,
            tov_check_page,
            past_runs_page,
        ],
        "Setup": [settings_page],
    }


def main() -> None:
    current_env = load_api_env()
    missing = missing_required(current_env)
    gate_open = not missing

    if not gate_open:
        st.sidebar.warning(
            "Complete Settings to unlock the pipeline.\n\nMissing: "
            + ", ".join(missing)
        )

    pages = _build_pages(gate_open)
    nav = st.navigation(pages)
    nav.run()


main()
