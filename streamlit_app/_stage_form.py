"""Shared helpers for individual-stage Streamlit pages.

The six stage pages (``02_keyword_research.py`` through ``07_tov_check.py``)
each render a form that takes a run directory plus stage-specific overrides,
invoke a pipeline stage function directly, and surface the output artifacts
inline with download buttons. This module factors out the patterns those
pages share so each page file stays focused on its stage-specific wiring.

Design notes
------------
* ``pick_run_dir`` renders a selectbox populated from :func:`runs.list_runs`
  plus an optional text input for ad-hoc directories. Newer runs surface
  first (``list_runs`` already sorts newest-first).
* ``render_artifact_preview`` + ``render_artifact_download`` handle the
  read/display/download ceremony for a single artifact file so pages can
  just call one line per artifact.
* ``gate_open`` mirrors the defense-in-depth check in the existing
  ``01_run_pipeline.py`` and ``08_past_runs.py`` pages — the app-level gate
  in ``app.py`` is the primary guard, but deep links to a stage page must
  still show the closed-gate notice rather than the form.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from streamlit_app.runs import RunInfo, list_runs
from streamlit_app.settings_io import (
    apply_to_process_env,
    load_api_env,
    missing_required,
)


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------


def gate_open() -> bool:
    """Return ``True`` if ``api.env`` satisfies all REQUIRED_KEYS.

    Also re-applies the current ``api.env`` to ``os.environ`` so edits
    saved in Settings during the same session take effect immediately.
    """
    env = load_api_env()
    apply_to_process_env(env)
    return not missing_required(env)


def render_closed_gate(title: str) -> None:
    """Render a consistent closed-gate notice for stage pages."""
    st.title(title)
    st.warning(
        "Please configure API keys in **Settings** before running pipeline "
        "stages. Required keys are missing from `api.env`."
    )


# ---------------------------------------------------------------------------
# Run-directory picker
# ---------------------------------------------------------------------------


def _default_output_root() -> Path:
    """Return the project-relative ``output/`` directory."""
    return Path.cwd() / "output"


def pick_run_dir(
    *,
    key: str,
    help_text: str = "Pick a prior run directory to operate on.",
    output_root: Path | None = None,
) -> Path | None:
    """Render a run-directory picker and return the selected path.

    Offers two input modes:

    1. A selectbox populated from :func:`streamlit_app.runs.list_runs`
       (newest-first). Empty when no runs exist yet.
    2. A manual path text input used as a fallback / override. Takes
       precedence over the selectbox when non-empty.

    Returns ``None`` if the user has not made a selection yet (empty
    selectbox **and** empty manual path).
    """
    root = output_root if output_root is not None else _default_output_root()
    runs: list[RunInfo] = list_runs(root)

    col1, col2 = st.columns([2, 1])
    with col1:
        options: list[str] = ["— select —"] + [r.dirname for r in runs]
        choice = st.selectbox(
            "Run directory",
            options=options,
            key=f"{key}/select",
            help=help_text,
        )
    with col2:
        manual = st.text_input(
            "Or custom path",
            key=f"{key}/manual",
            help=(
                "Absolute or project-relative path to a run directory. "
                "Overrides the selector when set."
            ),
        )

    manual_stripped = manual.strip() if isinstance(manual, str) else ""
    if manual_stripped:
        return Path(manual_stripped)

    if choice != "— select —":
        return root / str(choice)

    return None


def resolve_slug(run_dir: Path) -> str:
    """Return the slug embedded in ``run_dir``'s name.

    Mirrors the ``YYYY-MM-DD_<slug>`` convention the orchestrator uses.
    Falls back to the whole directory name when the prefix is missing.
    """
    name = run_dir.name
    if len(name) >= 11 and name[10] == "_":
        return name[11:]
    return name


# ---------------------------------------------------------------------------
# Artifact rendering
# ---------------------------------------------------------------------------


def render_artifact_preview(
    path: Path,
    *,
    label: str | None = None,
    language: str = "markdown",
    max_chars: int = 20000,
) -> None:
    """Render an inline preview of ``path`` (markdown by default).

    Silently no-ops if the file does not exist. JSON files use
    :func:`st.code`; markdown files use :func:`st.markdown`. Large files
    are truncated at ``max_chars`` so the page does not hang on multi-MB
    artifacts.
    """
    if not path.is_file():
        return

    if label:
        st.caption(f"{label}: `{path.name}`")
    else:
        st.caption(f"Preview: `{path.name}`")

    try:
        body = path.read_text(encoding="utf-8")
    except OSError as exc:
        st.error(f"Could not read `{path.name}`: {exc}")
        return

    truncated = len(body) > max_chars
    display = body[:max_chars] + ("\n…" if truncated else "")
    if language == "markdown":
        st.markdown(display)
    else:
        st.code(display, language=language)

    if truncated:
        st.caption(f"(truncated to {max_chars} chars)")


def render_artifact_download(
    path: Path,
    *,
    label: str | None = None,
    key_prefix: str = "dl",
) -> None:
    """Render a download button for ``path`` when it exists.

    Silently no-ops if the file is missing. Uses a namespaced key so
    multiple buttons on the same page do not collide.
    """
    if not path.is_file():
        return
    try:
        data = path.read_bytes()
    except OSError as exc:
        st.error(f"Could not read `{path.name}`: {exc}")
        return
    st.download_button(
        label=label or f"Download {path.name}",
        data=data,
        file_name=path.name,
        key=f"{key_prefix}/{path.name}",
    )


__all__ = [
    "gate_open",
    "pick_run_dir",
    "render_artifact_download",
    "render_artifact_preview",
    "render_closed_gate",
    "resolve_slug",
]
