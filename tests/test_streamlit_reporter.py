"""Unit tests for :class:`streamlit_app.progress.StreamlitReporter`.

These tests never import Streamlit: the reporter accepts plain objects
implementing a minimal protocol, so we inject lightweight stubs that
record every call. This keeps the tests fast and deterministic while
still exercising all four ``StageStatus`` transitions (``start``,
``complete``, ``error``, ``skip``) and their container-side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from seo_pipeline.orchestrator import STAGE_TOTAL, StageEvent
from streamlit_app.progress import StreamlitReporter


@dataclass
class _StubContainer:
    """Records every ``update(...)`` call verbatim."""

    updates: list[dict[str, Any]] = field(default_factory=list)

    def update(
        self,
        *,
        label: str | None = None,
        state: str | None = None,
        expanded: bool | None = None,
    ) -> None:
        self.updates.append(
            {"label": label, "state": state, "expanded": expanded}
        )


@dataclass
class _StubProgress:
    """Records every ``progress(value, text=...)`` call verbatim."""

    calls: list[tuple[float, str | None]] = field(default_factory=list)

    def progress(self, value: float, text: str | None = None) -> None:
        self.calls.append((value, text))


@dataclass
class _StubWriter:
    """Records every string written to the status body."""

    lines: list[str] = field(default_factory=list)

    def __call__(self, line: str) -> None:
        self.lines.append(line)


def _make_reporter() -> tuple[
    StreamlitReporter, _StubContainer, _StubProgress, _StubWriter,
]:
    container = _StubContainer()
    progress = _StubProgress()
    writer = _StubWriter()
    reporter = StreamlitReporter(
        status=container, progress=progress, write=writer,
    )
    return reporter, container, progress, writer


def _start(index: int, name: str, message: str) -> StageEvent:
    return StageEvent(
        stage_index=index, stage_name=name, status="start", message=message,
    )


def _complete(index: int, name: str, message: str) -> StageEvent:
    return StageEvent(
        stage_index=index, stage_name=name, status="complete", message=message,
    )


def _error(index: int, name: str, message: str) -> StageEvent:
    return StageEvent(
        stage_index=index, stage_name=name, status="error", message=message,
    )


def _skip(index: int, name: str, message: str) -> StageEvent:
    return StageEvent(
        stage_index=index, stage_name=name, status="skip", message=message,
    )


# ---------------------------------------------------------------------------
# status="start" — container label updates with CLI-formatted text.
# ---------------------------------------------------------------------------


class TestStart:
    def test_start_updates_label_with_cli_format(self) -> None:
        reporter, container, progress, writer = _make_reporter()

        reporter(_start(1, "fetch-serp", "Fetching SERP data..."))

        assert container.updates == [
            {
                "label": "Stage 1/11: Fetching SERP data...",
                "state": "running",
                "expanded": None,
            },
        ]
        # No progress advance and no body line on start.
        assert progress.calls == []
        assert writer.lines == []

    def test_start_uses_event_stage_total(self) -> None:
        """The label is built from ``event.stage_total``, so a future
        change to the stage count is reflected without touching the
        reporter."""
        reporter, container, _, _ = _make_reporter()

        event = StageEvent(
            stage_index=3, stage_name="x", status="start",
            message="Doing X...", stage_total=STAGE_TOTAL,
        )
        reporter(event)

        assert container.updates[-1]["label"] == (
            f"Stage 3/{STAGE_TOTAL}: Doing X..."
        )


# ---------------------------------------------------------------------------
# status="complete" — progress advances and a checkmark-style line is written.
# ---------------------------------------------------------------------------


class TestComplete:
    def test_complete_advances_progress_bar_monotonically(self) -> None:
        reporter, _, progress, _ = _make_reporter()

        for idx, name in enumerate(
            [
                "fetch-serp", "process-serp", "extract-pages",
                "fetch-keywords", "process-keywords",
            ],
            start=1,
        ):
            reporter(_complete(idx, name, "msg"))

        # Five completes → 5/11 progressions, each strictly increasing.
        assert len(progress.calls) == 5
        values = [v for v, _ in progress.calls]
        assert values == sorted(values)
        assert values[-1] == 5 / STAGE_TOTAL

    def test_complete_writes_one_line_per_stage(self) -> None:
        reporter, _, _, writer = _make_reporter()

        reporter(_complete(1, "fetch-serp", "ignored"))
        reporter(_complete(2, "process-serp", "ignored"))

        assert writer.lines == [
            "Stage 1/11: fetch-serp done",
            "Stage 2/11: process-serp done",
        ]

    def test_complete_count_exposed_via_property(self) -> None:
        reporter, _, _, _ = _make_reporter()

        reporter(_complete(1, "fetch-serp", "m"))
        reporter(_complete(2, "process-serp", "m"))

        assert reporter.completed_count == 2

    def test_progress_caps_at_one(self) -> None:
        """If the reporter ever sees more completes than STAGE_TOTAL
        (shouldn't happen in production, but guard against it), the
        progress fraction caps at 1.0 so Streamlit doesn't raise."""
        reporter, _, progress, _ = _make_reporter()

        for i in range(STAGE_TOTAL + 3):
            reporter(_complete(i + 1, "fake", "m"))

        assert all(v <= 1.0 for v, _ in progress.calls)
        assert progress.calls[-1][0] == 1.0


# ---------------------------------------------------------------------------
# status="error" — container flips to error state, exception surfaced.
# ---------------------------------------------------------------------------


class TestError:
    def test_error_switches_container_to_error_state(self) -> None:
        reporter, container, _, writer = _make_reporter()

        reporter(_error(5, "process-keywords", "RuntimeError: boom"))

        assert reporter.errored is True
        final_update = container.updates[-1]
        assert final_update["state"] == "error"
        assert final_update["expanded"] is True
        assert "process-keywords" in final_update["label"]
        assert "failed" in final_update["label"].lower()

        # The exception message lands in the container body so the user
        # sees it prominently, not just as a label.
        assert any(
            "process-keywords" in line and "boom" in line
            for line in writer.lines
        ), writer.lines

    def test_finalize_success_is_noop_after_error(self) -> None:
        reporter, container, _, _ = _make_reporter()

        reporter(_error(1, "fetch-serp", "BrokenPipe: x"))
        prior_update_count = len(container.updates)

        reporter.finalize_success()

        # finalize_success must not mask the error state.
        assert len(container.updates) == prior_update_count


# ---------------------------------------------------------------------------
# status="skip" — reporter records a "skipped" line without advancing progress.
# ---------------------------------------------------------------------------


class TestSkip:
    def test_skip_writes_skipped_line_only(self) -> None:
        reporter, container, progress, writer = _make_reporter()

        reporter(_skip(3, "extract-pages", "Nothing to extract"))

        # No container state change, no progress advance.
        assert container.updates == []
        assert progress.calls == []
        # One line announcing the skip.
        assert len(writer.lines) == 1
        assert "skipped" in writer.lines[0].lower()
        assert "extract-pages" in writer.lines[0]


# ---------------------------------------------------------------------------
# finalize_success — switches to state="complete" on happy-path exit.
# ---------------------------------------------------------------------------


class TestFinalizeSuccess:
    def test_finalize_success_sets_complete_state(self) -> None:
        reporter, container, _, _ = _make_reporter()

        reporter.finalize_success(label="All done")

        assert container.updates[-1] == {
            "label": "All done",
            "state": "complete",
            "expanded": None,
        }


# ---------------------------------------------------------------------------
# Full 11-stage happy-path drive — ensures the reporter handles the same
# event shape the orchestrator actually produces, end to end.
# ---------------------------------------------------------------------------


class TestFullSequence:
    def test_full_eleven_stage_sequence(self) -> None:
        reporter, container, progress, writer = _make_reporter()

        stages = [
            (1, "fetch-serp", "Fetching SERP data..."),
            (2, "process-serp", "Processing SERP data..."),
            (3, "extract-pages", "Extracting 0 competitor pages..."),
            (4, "fetch-keywords", "Fetching keywords..."),
            (5, "process-keywords", "Processing keywords..."),
            (6, "filter-keywords", "Filtering keywords..."),
            (7, "analyze-content", "Running content analysis..."),
            (8, "assemble-briefing-data", "Assembling briefing data..."),
            (9, "summarize-briefing", "Summarizing briefing..."),
            (
                10, "llm-generation",
                "LLM stages (fill-qualitative, assemble-briefing-md, "
                "write-draft)...",
            ),
            (11, "fact-check", "Fact-checking draft..."),
        ]

        for idx, name, message in stages:
            reporter(_start(idx, name, message))
            reporter(_complete(idx, name, message))

        reporter.finalize_success()

        # 11 starts + 1 final = 12 label updates on the container.
        assert len(container.updates) == 12
        # 11 progress advances, last one hits exactly 1.0.
        assert len(progress.calls) == 11
        assert progress.calls[-1][0] == 1.0
        # 11 completion lines in the body.
        assert len(writer.lines) == 11
        assert reporter.completed_count == 11
        assert reporter.errored is False
        # Final state is complete.
        assert container.updates[-1]["state"] == "complete"
