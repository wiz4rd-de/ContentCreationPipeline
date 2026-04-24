"""Thin helpers around ``st.session_state``.

Keep the Streamlit dependency contained here so other modules can use a small,
typed API (with easier testability via monkeypatching) rather than poking at
``st.session_state`` directly.
"""

from __future__ import annotations

from typing import TypeVar

import streamlit as st

T = TypeVar("T")


def get_or_set(key: str, default: T) -> T:
    """Return ``st.session_state[key]``, initializing it to ``default`` first.

    ``default`` is evaluated eagerly by the caller; callers passing an
    expensive default should guard with a pre-existence check.
    """
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]


def get(key: str, default: T | None = None) -> T | None:
    """Return the value under ``key`` without writing to session state."""
    return st.session_state.get(key, default)


def set_value(key: str, value: T) -> T:
    """Store ``value`` under ``key`` and return it."""
    st.session_state[key] = value
    return value


def ns_key(namespace: str, key: str) -> str:
    """Return a namespaced session-state key (``"namespace/key"``).

    Use this to avoid accidental collisions between pages that happen to pick
    the same short key name.
    """
    return f"{namespace}/{key}"
