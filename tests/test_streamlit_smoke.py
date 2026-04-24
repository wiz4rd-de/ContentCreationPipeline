"""Smoke test: launch the Streamlit app and hit /_stcore/health.

This test verifies that ``streamlit_app/app.py`` actually boots end-to-end
under the ``ui`` extra. We spawn ``streamlit run`` as a subprocess on a
random free port, poll Streamlit's built-in health endpoint until it
returns ``ok``, and confirm the root page responds. The subprocess is
always torn down in a ``finally`` block.

Only stdlib dependencies are used (``subprocess``, ``socket``,
``urllib.request``). If ``streamlit`` isn't installed the test is
skipped via :func:`pytest.importorskip`.
"""

from __future__ import annotations

import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
APP_PATH = REPO_ROOT / "streamlit_app" / "app.py"

# Overall wall-clock budget for the health-check polling loop.
HEALTH_DEADLINE_SECONDS = 30.0
POLL_INTERVAL_SECONDS = 0.5
# Per-request timeout (must be well under the poll interval to avoid
# blowing past the deadline on a single slow connect).
REQUEST_TIMEOUT_SECONDS = 2.0


def _pick_free_port() -> int:
    """Bind to port 0, read the assigned port, close the socket, return it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _poll_health(port: int, deadline: float) -> tuple[int, str]:
    """Poll ``/_stcore/health`` until it returns 200 or we run out of time.

    Returns the final ``(status_code, body)`` tuple. Raises ``TimeoutError``
    if the deadline elapses without a successful response.
    """
    url = f"http://127.0.0.1:{port}/_stcore/health"
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                body = resp.read().decode("utf-8", errors="replace").strip()
                if resp.status == 200 and body == "ok":
                    return resp.status, body
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as exc:
            last_error = exc
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(
        f"Streamlit health endpoint at {url} did not respond within deadline "
        f"(last error: {last_error!r})"
    )


def test_streamlit_app_serves_health_endpoint() -> None:
    """The Streamlit app boots and serves /_stcore/health with body 'ok'."""
    pytest.importorskip("streamlit")

    if not APP_PATH.exists():
        pytest.skip(f"Streamlit app not found at {APP_PATH}")

    port = _pick_free_port()
    cmd = [
        "uv",
        "run",
        "--extra",
        "ui",
        "streamlit",
        "run",
        str(APP_PATH),
        "--server.headless",
        "true",
        "--server.port",
        str(port),
        "--server.address",
        "127.0.0.1",
        "--browser.gatherUsageStats",
        "false",
    ]

    proc = subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        deadline = time.monotonic() + HEALTH_DEADLINE_SECONDS
        try:
            status, body = _poll_health(port, deadline)
        except TimeoutError:
            # Dump captured output to aid debugging before re-raising.
            try:
                proc.terminate()
                out, err = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                out, err = proc.communicate()
            pytest.fail(
                "Streamlit health endpoint never responded.\n"
                f"--- stdout ---\n{out}\n--- stderr ---\n{err}"
            )

        assert status == 200
        assert body == "ok"

        # Also confirm the root page serves (200). Streamlit serves HTML here;
        # we only assert the status code, not the body content.
        root_url = f"http://127.0.0.1:{port}/"
        with urllib.request.urlopen(root_url, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            assert resp.status == 200
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        # Drain any remaining output so no pipe-buffer zombie lingers.
        try:
            if proc.stdout is not None:
                proc.stdout.close()
            if proc.stderr is not None:
                proc.stderr.close()
        except Exception:
            pass
