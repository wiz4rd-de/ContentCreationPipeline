"""Streamlit progress reporter for :func:`seo_pipeline.orchestrator.run_pipeline_core`.

The orchestrator emits :class:`~seo_pipeline.orchestrator.StageEvent` objects
via its ``on_event`` callback. :class:`StreamlitReporter` adapts that signal
stream to the Streamlit ``st.status`` container API: each stage start updates
the container label, each stage completion advances a progress bar, and an
error surfaces the exception and switches the container to ``state="error"``.

The reporter is intentionally decoupled from module-level ``st`` imports: the
container, progress bar, and write function are injected by the caller. The
production page wires ``st.status(...)`` and its ``.progress()`` / ``.write()``
helpers; unit tests inject a stub that records calls. This keeps the callback
logic pure and deterministic.
"""

from __future__ import annotations

from typing import Any, Callable, Protocol

from seo_pipeline.orchestrator import STAGE_TOTAL, StageEvent


class _StatusContainer(Protocol):
    """Minimal protocol for the ``st.status`` container used by the reporter.

    Matches the subset of the Streamlit API the reporter actually calls.
    """

    def update(
        self,
        *,
        label: str | None = ...,
        state: str | None = ...,
        expanded: bool | None = ...,
    ) -> None: ...


class _ProgressHandle(Protocol):
    """Minimal protocol for the ``st.progress`` bar handle."""

    def progress(self, value: float, text: str | None = ...) -> None: ...


WriteFn = Callable[[str], Any]


class StreamlitReporter:
    """Translate :class:`StageEvent`s into Streamlit container mutations.

    Parameters
    ----------
    status:
        A Streamlit ``st.status`` container (or a test stub implementing
        ``update(label=..., state=...)``).
    progress:
        A Streamlit ``st.progress`` handle (or a stub implementing
        ``progress(value, text=...)``). Advanced once per stage completion.
    write:
        A callable that writes a line to the status container body. In
        production this is ``status.write`` or a lambda around ``st.write``;
        in tests it's a recorder.
    stage_total:
        Total number of stages. Defaults to
        :data:`seo_pipeline.orchestrator.STAGE_TOTAL` so the reporter stays
        aligned with the orchestrator's contract.
    """

    def __init__(
        self,
        status: _StatusContainer,
        progress: _ProgressHandle,
        write: WriteFn,
        stage_total: int = STAGE_TOTAL,
    ) -> None:
        self._status = status
        self._progress = progress
        self._write = write
        self._stage_total = stage_total
        self._completed = 0
        self._errored = False

    # -- public API ----------------------------------------------------------

    def __call__(self, event: StageEvent) -> None:
        """Dispatch on ``event.status``.

        The mapping mirrors the CLI's stderr output so users see the same
        ``"Stage N/11: <message>"`` text in the UI that the CLI prints to
        the terminal.
        """
        if event.status == "start":
            self._on_start(event)
        elif event.status == "complete":
            self._on_complete(event)
        elif event.status == "error":
            self._on_error(event)
        elif event.status == "skip":
            self._on_skip(event)

    # -- handlers ------------------------------------------------------------

    def _on_start(self, event: StageEvent) -> None:
        # Byte-identical to the CLI's "Stage N/11: <message>" label.
        label = (
            f"Stage {event.stage_index}/{event.stage_total}: {event.message}"
        )
        self._status.update(label=label, state="running")

    def _on_complete(self, event: StageEvent) -> None:
        self._completed += 1
        fraction = min(1.0, self._completed / max(1, self._stage_total))
        progress_text = (
            f"Stage {event.stage_index}/{event.stage_total} complete"
        )
        self._progress.progress(fraction, text=progress_text)
        self._write(
            f"Stage {event.stage_index}/{event.stage_total}: "
            f"{event.stage_name} done"
        )

    def _on_error(self, event: StageEvent) -> None:
        self._errored = True
        label = (
            f"Stage {event.stage_index}/{event.stage_total} failed: "
            f"{event.stage_name}"
        )
        self._status.update(label=label, state="error", expanded=True)
        self._write(f"ERROR in {event.stage_name}: {event.message}")

    def _on_skip(self, event: StageEvent) -> None:
        self._write(
            f"Stage {event.stage_index}/{event.stage_total}: "
            f"{event.stage_name} skipped"
        )

    # -- properties for callers ---------------------------------------------

    @property
    def completed_count(self) -> int:
        """Number of ``complete`` events seen so far."""
        return self._completed

    @property
    def errored(self) -> bool:
        """``True`` once at least one ``error`` event has been handled."""
        return self._errored

    def finalize_success(self, label: str = "Pipeline complete") -> None:
        """Switch the container to ``state="complete"`` with a final label.

        Called by the page after ``run_pipeline_core`` returns without
        raising. A no-op if an error event has already flipped the
        container into the error state.
        """
        if self._errored:
            return
        self._status.update(label=label, state="complete")


__all__ = ["StreamlitReporter"]
