"""Past-runs browser page.

Lists every ``output/YYYY-MM-DD_<slug>/`` directory produced by a previous
pipeline run, sorted newest-first. For each run we show a row of completion
badges (green / grey dots) for the five tracked artifacts, an expandable
inline preview of the draft (or briefing if no draft exists), per-artifact
download buttons, and a delete-with-confirmation control.

Gate: this page relies on the app-level first-run gate in ``app.py`` to keep
it out of the nav when required API keys are missing. We also re-check the
gate here as defense-in-depth — a deep link to the page should not render
destructive controls the user hasn't earned by completing Settings.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import streamlit as st

from streamlit_app.runs import RunInfo, list_runs
from streamlit_app.settings_io import (
    apply_to_process_env,
    load_api_env,
    missing_required,
)
from streamlit_app.state import ns_key

# Session-state namespace so delete-confirmation flags from this page don't
# collide with other pages.
_NS = "past_runs"

# Per-run artifact filename templates. The slug is substituted at render time.
# Keep the order stable so download buttons always appear in the same
# sequence regardless of which flags are present.
_ARTIFACTS: list[tuple[str, str]] = [
    ("Briefing (Markdown)", "brief-{slug}.md"),
    ("Draft (Markdown)", "draft-{slug}.md"),
    ("Draft (Word)", "draft-{slug}.docx"),
    ("Fact-check report (Markdown)", "fact-check-report.md"),
    ("Fact-check report (JSON)", "fact-check-report.json"),
    ("ToV-check report (Markdown)", "tov-check-report.md"),
    ("ToV-check report (JSON)", "tov-check-report.json"),
]


def _gate_open() -> bool:
    """Return ``True`` if ``api.env`` satisfies all REQUIRED_KEYS."""
    env = load_api_env()
    apply_to_process_env(env)
    return not missing_required(env)


def _render_closed_gate() -> None:
    st.title("Past Runs")
    st.warning(
        "Please configure API keys in **Settings** before browsing past "
        "runs. Required keys are missing from `api.env`."
    )


def _badges(run: RunInfo) -> str:
    """Render the five artifact badges as a single-line markdown string.

    Uses filled/hollow circles so the row works in both light and dark
    themes without custom CSS. Title text on each badge names the artifact
    so hover reveals exactly which flag a dot corresponds to.
    """
    labels = [
        ("brief", run.has_brief),
        ("draft", run.has_draft_md),
        ("docx", run.has_draft_docx),
        ("fact", run.has_fact_check),
        ("tov", run.has_tov_check),
    ]
    parts = []
    for label, present in labels:
        dot = ":green_circle:" if present else ":white_circle:"
        parts.append(f"{dot} {label}")
    return " ".join(parts)


def _render_preview(run: RunInfo) -> None:
    """Render an inline preview — draft markdown if present, else the brief."""
    draft_path = run.path / f"draft-{run.slug}.md"
    brief_path = run.path / f"brief-{run.slug}.md"

    if draft_path.is_file():
        preview_source = draft_path
        st.caption(f"Preview: `{draft_path.name}`")
    elif brief_path.is_file():
        preview_source = brief_path
        st.caption(f"Preview: `{brief_path.name}` (no draft yet)")
    else:
        st.info("No draft or brief available to preview for this run.")
        return

    try:
        body = preview_source.read_text(encoding="utf-8")
    except OSError as exc:
        st.error(f"Could not read `{preview_source.name}`: {exc}")
        return

    st.markdown(body)


def _render_downloads(run: RunInfo) -> None:
    """Render a download button for each artifact that exists on disk."""
    shown = 0
    for label, template in _ARTIFACTS:
        path = run.path / template.format(slug=run.slug)
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError as exc:
            st.error(f"Could not read `{path.name}`: {exc}")
            continue
        st.download_button(
            label=f"Download {label}",
            data=data,
            file_name=path.name,
            # Namespacing the key by run dir + artifact filename keeps
            # buttons unique across expanders rendered on the same page.
            key=f"dl/{run.dirname}/{path.name}",
        )
        shown += 1
    if shown == 0:
        st.info("No downloadable artifacts in this run directory yet.")


def _render_delete(run: RunInfo) -> None:
    """Render a two-click delete gate.

    First click: flips a per-run session-state flag and rerenders,
    revealing a destructive "Confirm delete" button alongside a
    "Cancel" button. Second click on "Confirm delete" calls
    :func:`shutil.rmtree` and clears the flag.
    """
    confirm_key = ns_key(_NS, f"confirm_delete/{run.dirname}")
    armed = bool(st.session_state.get(confirm_key, False))

    if not armed:
        if st.button(
            "Delete run",
            key=f"del/{run.dirname}",
            type="secondary",
            help="Permanently remove this run directory and all its files.",
        ):
            st.session_state[confirm_key] = True
            st.rerun()
        return

    st.warning(
        f"This will permanently delete `{run.path}` and all files inside "
        "it. This cannot be undone."
    )
    col1, col2 = st.columns(2)
    with col1:
        confirmed = st.button(
            "Confirm delete",
            key=f"del-confirm/{run.dirname}",
            type="primary",
        )
    with col2:
        cancelled = st.button(
            "Cancel",
            key=f"del-cancel/{run.dirname}",
        )

    if cancelled:
        st.session_state[confirm_key] = False
        st.rerun()
    if confirmed:
        try:
            shutil.rmtree(run.path)
        except OSError as exc:
            st.error(f"Failed to delete `{run.path}`: {exc}")
            return
        st.session_state[confirm_key] = False
        st.success(f"Deleted `{run.dirname}`.")
        st.rerun()


def _render_run(run: RunInfo) -> None:
    """Render one row of the past-runs list as an expandable section."""
    header = (
        f"**{run.date.isoformat()}**  —  `{run.slug}`  —  {_badges(run)}"
    )
    with st.expander(header, expanded=False):
        st.caption(f"Path: `{run.path}`")
        st.divider()
        _render_preview(run)
        st.divider()
        st.subheader("Downloads")
        _render_downloads(run)
        st.divider()
        st.subheader("Delete")
        _render_delete(run)


def _render_table(runs: list[RunInfo]) -> None:
    """Render a compact summary table above the expandable detail rows."""
    rows = [
        {
            "date": r.date.isoformat(),
            "slug": r.slug,
            "brief": "OK" if r.has_brief else "-",
            "draft_md": "OK" if r.has_draft_md else "-",
            "draft_docx": "OK" if r.has_draft_docx else "-",
            "fact_check": "OK" if r.has_fact_check else "-",
            "tov_check": "OK" if r.has_tov_check else "-",
        }
        for r in runs
    ]
    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
    )


def render() -> None:
    st.title("Past Runs")
    st.caption(
        "Browse previous pipeline runs under `output/`. "
        "Expand a row to preview, download artifacts, or delete the run."
    )

    if not _gate_open():
        _render_closed_gate()
        return

    # Default to ``output/`` under the project CWD; we expose the path as an
    # input so users who placed runs under a non-default --output-dir can
    # still see them without restarting the app.
    default_dir = Path.cwd() / "output"
    dir_text = st.text_input(
        "Runs directory",
        value=str(default_dir),
        help="Directory to scan. Defaults to `output/` under the project root.",
    )
    scan_dir = Path(dir_text.strip() or str(default_dir))

    runs = list_runs(scan_dir)
    if not runs:
        st.info(
            f"No runs found under `{scan_dir}`. Start one from the "
            "**Run Pipeline** page."
        )
        return

    st.write(f"Found **{len(runs)}** run(s).")
    _render_table(runs)
    st.divider()

    for run in runs:
        _render_run(run)


render()
