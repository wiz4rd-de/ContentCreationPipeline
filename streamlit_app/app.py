"""Streamlit entry point for the SEO Content Pipeline UI.

Launch with::

    uv run streamlit run streamlit_app/app.py

Renders navigation via :func:`st.navigation`. When required credentials are
missing from ``api.env``, only the Settings page is shown; otherwise the full
nav is available. Concrete stage pages (01–08) are still stubs — they will be
filled in by subsequent Phase 2/3 tickets (#199 and later).
"""

from __future__ import annotations

from typing import Callable

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


def _placeholder(title: str, description: str) -> Callable[[], None]:
    def render() -> None:
        st.title(title)
        st.info(f"{description}\n\nComing soon.")

    return render


_STUB_PAGES = [
    ("pipeline/keywords", "02 Keywords", "Keyword research stage."),
    ("pipeline/serp", "03 SERP", "SERP fetching stage."),
    ("pipeline/extract", "04 Extract", "Content extraction stage."),
    ("pipeline/analysis", "05 Analysis", "Competitor analysis stage."),
    ("pipeline/briefing", "06 Briefing", "Content briefing stage."),
    ("pipeline/draft", "07 Draft", "Drafting stage."),
]


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

    stub_pages = [
        st.Page(
            _placeholder(title, description),
            title=title,
            url_path=url_path,
        )
        for url_path, title, description in _STUB_PAGES
    ]
    past_runs_page = st.Page(
        "pages/08_past_runs.py",
        title="08 Past Runs",
        url_path="pipeline/past_runs",
    )
    return {
        "Pipeline": [run_pipeline_page, *stub_pages, past_runs_page],
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
