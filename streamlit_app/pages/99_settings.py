"""Settings page: edit ``api.env`` and apply values to the running process."""

from __future__ import annotations

import streamlit as st

from streamlit_app.settings_io import (
    ALL_KEYS,
    OPTIONAL_KEYS,
    REQUIRED_KEYS,
    SECRET_KEYS,
    apply_to_process_env,
    load_api_env,
    missing_required,
    save_api_env,
)


def render() -> None:
    st.title("Settings")
    st.caption(
        "Values are written to ``api.env`` in the project root and applied to the "
        "running process immediately. Restarts pick them up from disk."
    )

    current = load_api_env()
    missing = missing_required(current)

    if missing:
        st.warning(
            "Required keys missing: " + ", ".join(f"`{k}`" for k in missing)
        )
    else:
        st.success("Required keys present.")

    with st.form("settings_form"):
        st.subheader("Required")
        required_inputs: dict[str, str] = {}
        for key in REQUIRED_KEYS:
            required_inputs[key] = st.text_input(
                key,
                value=current.get(key, ""),
                type="password" if key in SECRET_KEYS else "default",
                help=_help_text(key),
            )

        st.subheader("Optional")
        optional_inputs: dict[str, str] = {}
        for key in OPTIONAL_KEYS:
            optional_inputs[key] = st.text_input(
                key,
                value=current.get(key, ""),
                type="password" if key in SECRET_KEYS else "default",
                help=_help_text(key),
            )

        submitted = st.form_submit_button("Save")

    if submitted:
        new_values: dict[str, str] = {}
        for key in ALL_KEYS:
            new_values[key] = (
                required_inputs.get(key, "") or optional_inputs.get(key, "")
            ).strip()
        save_api_env(new_values)
        apply_to_process_env(new_values)
        st.toast("Saved")
        st.rerun()


def _help_text(key: str) -> str:
    return {
        "LLM_PROVIDER": "One of: anthropic, openai, google, openai_compat.",
        "LLM_MODEL": "Model identifier (e.g. claude-sonnet-4-20250514, gpt-4o).",
        "LLM_API_KEY": "API key for the selected provider.",
        "LLM_API_BASE": "Optional base URL override (required for openai_compat).",
        "LLM_TEMPERATURE": "Sampling temperature (default 0.3).",
        "LLM_MAX_TOKENS": "Maximum tokens in the response (default 8192).",
        "DATAFORSEO_AUTH": (
            "Base64 of 'login:password' (echo -n 'login:password' | base64)."
        ),
        "DATAFORSEO_BASE": "Typically https://api.dataforseo.com/v3.",
    }.get(key, "")


render()
