"""Run Pipeline page — form + live stage progress.

Renders a form mirroring the ``seo-pipeline run`` CLI arguments. On
submit, builds a :class:`~seo_pipeline.orchestrator.PipelineConfig` and
calls :func:`~seo_pipeline.orchestrator.run_pipeline_core` IN-PROCESS,
streaming stage events into an ``st.status`` container via
:class:`~streamlit_app.progress.StreamlitReporter`.

Gate: the page re-checks ``api.env`` at the top and renders a notice
with an early return if the first-run gate is closed. The app shell in
``app.py`` already restricts navigation when the gate is closed, but this
defense-in-depth check ensures a deep link to the page does not render a
form the user cannot actually use.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from seo_pipeline.orchestrator import (
    PipelineConfig,
    run_pipeline_core,
)
from streamlit_app.progress import StreamlitReporter
from streamlit_app.settings_io import (
    apply_to_process_env,
    load_api_env,
    missing_required,
)


# ---------------------------------------------------------------------------
# Gate: bail out early if required API keys aren't configured.
# ---------------------------------------------------------------------------


def _gate_open() -> bool:
    """Return True if all REQUIRED_KEYS are populated in ``api.env``.

    Also applies the current env to ``os.environ`` so edits saved in
    Settings during the same session take effect on the next run
    without a process restart.
    """
    env = load_api_env()
    apply_to_process_env(env)
    return not missing_required(env)


def _render_closed_gate() -> None:
    st.title("Run Pipeline")
    st.warning(
        "Please configure API keys in **Settings** before running the "
        "pipeline. Required keys are missing from `api.env`."
    )


# ---------------------------------------------------------------------------
# Form → PipelineConfig
# ---------------------------------------------------------------------------


def _build_config(form_values: dict[str, object]) -> PipelineConfig:
    """Translate form widget values into a :class:`PipelineConfig`.

    Empty strings in optional fields are coerced to ``None`` so
    downstream stages see the same defaults they would from the CLI.
    """

    def _clean(value: object) -> str | None:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return None

    def _clean_path(value: object) -> Path | None:
        text = _clean(value)
        return Path(text) if text is not None else None

    return PipelineConfig(
        keyword=str(form_values["keyword"]).strip(),
        location=str(form_values["location"]).strip() or "de",
        language=str(form_values["language"]).strip() or "de",
        output_dir=_clean_path(form_values.get("output_dir")),
        skip_fetch=bool(form_values.get("skip_fetch", False)),
        llm_provider=_clean(form_values.get("llm_provider")),
        llm_model=_clean(form_values.get("llm_model")),
        tov=_clean_path(form_values.get("tov")),
        template=_clean_path(form_values.get("template")),
        user_domain=_clean(form_values.get("user_domain")),
        business_context=_clean(form_values.get("business_context")),
    )


# ---------------------------------------------------------------------------
# Artifact discovery — what the pipeline actually produced.
# ---------------------------------------------------------------------------


_ARTIFACT_CANDIDATES: list[tuple[str, str]] = [
    # (label, filename-template — {slug} substituted at call time)
    ("Briefing", "brief-{slug}.md"),
    ("Draft (Markdown)", "draft-{slug}.md"),
    ("Draft (Word)", "draft-{slug}.docx"),
    ("Fact-check report (Markdown)", "fact-check-report.md"),
    ("Fact-check report (JSON)", "fact-check-report.json"),
    ("ToV-check report (Markdown)", "tov-check-report.md"),
    ("ToV-check report (JSON)", "tov-check-report.json"),
]


def _collect_artifacts(out_dir: Path, slug: str) -> list[tuple[str, Path]]:
    """Return the list of artifacts that actually exist on disk."""
    found: list[tuple[str, Path]] = []
    for label, template in _ARTIFACT_CANDIDATES:
        path = out_dir / template.format(slug=slug)
        if path.exists():
            found.append((label, path))
    return found


# ---------------------------------------------------------------------------
# Page body
# ---------------------------------------------------------------------------


def _render_form() -> dict[str, object] | None:
    """Render the run-pipeline form. Returns form values on submit, else None."""
    with st.form("run_pipeline_form"):
        st.subheader("Inputs")
        keyword = st.text_input(
            "Keyword",
            help="Seed keyword for the pipeline (required).",
        )
        col1, col2 = st.columns(2)
        with col1:
            location = st.text_input(
                "Location", value="de",
                help="Market / country code (e.g. de, us, gb).",
            )
        with col2:
            language = st.text_input(
                "Language", value="de",
                help="Language code (e.g. de, en).",
            )

        output_dir = st.text_input(
            "Output directory (optional)",
            help=(
                "Leave blank to use ``output/<YYYY-MM-DD>_<slug>/``. "
                "Relative to the project root."
            ),
        )

        st.subheader("Toggles")
        skip_fetch = st.checkbox(
            "Skip network fetches (use cached data)",
            value=False,
            help=(
                "Reuses cached SERP/keyword data in the output directory. "
                "Only useful when re-running a previous pipeline."
            ),
        )

        with st.expander("Advanced (optional)"):
            llm_provider = st.text_input(
                "LLM provider override",
                help=(
                    "Override LLM_PROVIDER for this run (anthropic, openai, "
                    "google, openai_compat). Falls back to api.env."
                ),
            )
            llm_model = st.text_input(
                "LLM model override",
                help="Override LLM_MODEL for this run.",
            )
            tov = st.text_input(
                "Tone-of-voice file (path)",
                help="Path to a ToV markdown file.",
            )
            template = st.text_input(
                "Briefing template (path)",
                help="Path to a briefing template file.",
            )
            user_domain = st.text_input(
                "User domain",
                help="Domain to exclude from competitor analysis.",
            )
            business_context = st.text_area(
                "Business context",
                help="Free-form context passed to briefing generation.",
            )

        submitted = st.form_submit_button("Run pipeline")

    if not submitted:
        return None

    if not keyword.strip():
        st.error("Keyword is required.")
        return None

    return {
        "keyword": keyword,
        "location": location,
        "language": language,
        "output_dir": output_dir,
        "skip_fetch": skip_fetch,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "tov": tov,
        "template": template,
        "user_domain": user_domain,
        "business_context": business_context,
    }


def _run(config: PipelineConfig) -> None:
    """Execute the pipeline in-process with a live status container."""
    log_lines: list[str] = []

    with st.status("Running pipeline...", expanded=True) as status:
        progress_bar = st.progress(0.0, text="Starting...")
        reporter = StreamlitReporter(
            status=status,
            progress=progress_bar,
            write=st.write,
        )

        def _on_log(line: str) -> None:
            log_lines.append(line)
            st.write(line)

        try:
            result = run_pipeline_core(
                config, on_event=reporter, on_log=_on_log,
            )
        except Exception as exc:  # noqa: BLE001 — surface everything
            # The reporter's error handler already flipped state to
            # "error" when the stage fired its error event; if the
            # exception came from outside a stage body (e.g. input
            # validation), ensure the container still reflects it.
            if not reporter.errored:
                status.update(
                    label=f"Pipeline failed: {type(exc).__name__}",
                    state="error",
                    expanded=True,
                )
            st.exception(exc)
            return

        reporter.finalize_success(
            label=f"Pipeline complete — output: {result.output_dir}"
        )

    # --- Post-run artifact surface ---------------------------------------
    st.success(f"Pipeline complete. Output directory: `{result.output_dir}`")
    if not result.llm_configured:
        st.info(
            "LLM was not configured for this run — the draft and fact-check "
            "stages were skipped. Configure credentials in Settings to run "
            "the full chain."
        )

    artifacts = _collect_artifacts(result.output_dir, result.slug)
    if artifacts:
        st.subheader("Artifacts")
        for label, path in artifacts:
            st.write(f"- **{label}**: `{path}`")
            try:
                data = path.read_bytes()
            except OSError:
                continue
            st.download_button(
                label=f"Download {path.name}",
                data=data,
                file_name=path.name,
                key=f"dl-{path.name}",
            )
    else:
        st.warning(
            "No standard artifacts found in the output directory. "
            "Check the logs above for details."
        )


def render() -> None:
    st.title("Run Pipeline")
    st.caption(
        "End-to-end pipeline run with live stage progress. Uses the values "
        "configured on the Settings page."
    )

    if not _gate_open():
        _render_closed_gate()
        return

    form_values = _render_form()
    if form_values is None:
        return

    config = _build_config(form_values)
    _run(config)


render()
