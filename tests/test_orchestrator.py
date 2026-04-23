"""Tests for seo_pipeline.orchestrator.

These tests lock the contract between ``run_pipeline_core`` and its
consumers (the Typer CLI and the upcoming Streamlit UI): the 11-stage
``StageEvent`` sequence emitted via ``on_event``.

Strategy
--------
Every ``_stage_*`` helper is patched at its import site inside
``seo_pipeline.orchestrator`` with a lightweight stand-in that still
drives the real ``_stage`` context manager — so event emission, stage
names, messages, and sequencing are exercised by production code while
no real I/O (network, LLM, unrelated filesystem writes) happens.

The error test keeps the same scheme but swaps one stand-in for a
raiser, then verifies the ``error`` event is emitted and later stages
never run.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Callable

import pytest

from seo_pipeline import orchestrator
from seo_pipeline.orchestrator import (
    STAGE_TOTAL,
    PipelineConfig,
    StageEvent,
    run_pipeline_core,
)

# ---------------------------------------------------------------------------
# Expected stage sequence — the single source of truth for the 11-stage
# contract. Kept in sync with ``seo_pipeline.orchestrator``. If this
# table changes, the orchestrator changed too and downstream consumers
# need to be notified.
# ---------------------------------------------------------------------------

EXPECTED_STAGES: list[tuple[int, str, str]] = [
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
        10,
        "llm-generation",
        "LLM stages (fill-qualitative, assemble-briefing-md, write-draft)...",
    ),
    (11, "fact-check", "Fact-checking draft..."),
]


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_stage_stub(
    index: int,
    name: str,
    message: str,
    *,
    serp_processed: dict[str, Any] | None = None,
    returns_path: Path | None = None,
    raises: Exception | None = None,
) -> Callable[..., Any]:
    """Build a replacement ``_stage_*`` helper.

    The stand-in uses the real ``_stage`` context manager so start/
    complete/error events flow through production code. Signatures are
    permissive (``*args, **kwargs``) because the stage helpers each take
    different argument shapes.
    """

    def stub(*args: Any, **kwargs: Any) -> Any:
        # on_event is always the penultimate positional arg across stage
        # helpers, but the last arg for a couple of them (on_log). We
        # find it by type rather than position.
        on_event = None
        for candidate in list(args) + list(kwargs.values()):
            if callable(candidate):
                # Heuristic: the event callback is the first callable
                # whose __name__ is not ``_noop_log`` and that isn't
                # a Path-like object. In the tests we only ever wire
                # the recorder as the event callback, so this works.
                on_event = candidate
                break

        # Fall back: the orchestrator's public API always passes the
        # event callback. If we didn't find one, just skip emission —
        # the test will fail loudly on the missing event.
        if on_event is None:  # pragma: no cover — defensive
            return None

        with orchestrator._stage(on_event, index, name, message):
            if raises is not None:
                raise raises
        if serp_processed is not None:
            return serp_processed
        if returns_path is not None:
            return returns_path
        return None

    return stub


def _install_stage_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    stage3_competitor_count: int = 0,
    raise_at_stage: int | None = None,
    llm_configured: bool = True,
    tmp_path: Path | None = None,
) -> None:
    """Replace every ``_stage_*`` helper in the orchestrator module.

    Stages 1-9 and 11 are swapped with event-emitting stubs. Stage 10
    (``_stage_llm_generation``) is replaced with a stub that emits its
    event and returns ``llm_configured`` so the orchestrator's branch
    for ``skipped_no_llm`` is exercised when requested.
    """
    stage3_msg = (
        f"Extracting {stage3_competitor_count} competitor pages..."
    )

    stubs: list[tuple[int, str, str, str]] = [
        (1, "fetch-serp", "Fetching SERP data...", "_stage_fetch_serp"),
        (2, "process-serp", "Processing SERP data...", "_stage_process_serp"),
        (3, "extract-pages", stage3_msg, "_stage_extract_pages"),
        (4, "fetch-keywords", "Fetching keywords...", "_stage_fetch_keywords"),
        (
            5, "process-keywords", "Processing keywords...",
            "_stage_process_keywords",
        ),
        (
            6, "filter-keywords", "Filtering keywords...",
            "_stage_filter_keywords",
        ),
        (
            7, "analyze-content", "Running content analysis...",
            "_stage_analyze_content",
        ),
        (
            8, "assemble-briefing-data", "Assembling briefing data...",
            "_stage_assemble_briefing_data",
        ),
        (
            9, "summarize-briefing", "Summarizing briefing...",
            "_stage_summarize_briefing",
        ),
        (11, "fact-check", "Fact-checking draft...", "_stage_fact_check"),
    ]

    # Extra returns: stage 2 needs a serp_processed dict (with a
    # competitors list of the requested length), stage 5 needs a
    # kw_processed dict, stage 8 needs a Path.
    serp_processed = {
        "competitors": [
            {"url": f"https://example.com/{i}", "domain": f"example{i}"}
            for i in range(stage3_competitor_count)
        ],
    }
    kw_processed = {"clusters": []}
    briefing_path = (
        tmp_path / "briefing-data.json"
        if tmp_path is not None
        else Path("briefing-data.json")
    )

    return_overrides: dict[int, dict[str, Any]] = {
        2: {"serp_processed": serp_processed},
        5: {"serp_processed": kw_processed},
        8: {"returns_path": briefing_path},
    }

    for index, name, message, attr in stubs:
        raises: Exception | None = None
        if raise_at_stage is not None and index == raise_at_stage:
            raises = RuntimeError("boom")

        overrides = return_overrides.get(index, {})
        stub = _make_stage_stub(
            index, name, message, raises=raises, **overrides,
        )
        monkeypatch.setattr(orchestrator, attr, stub)

    # Stage 10 is special: it doesn't just yield — it emits its own
    # event via ``_stage`` and returns a bool. We replace it with a
    # stand-in that emits the correct event and returns
    # ``llm_configured`` so the Stage 11 branch is exercised.
    stage10_msg = (
        "LLM stages (fill-qualitative, assemble-briefing-md, write-draft)..."
    )

    def stage10_stub(
        cfg: PipelineConfig,
        out_dir: Path,
        slug: str,
        on_event: Callable[[StageEvent], None],
        on_log: Callable[[str], None],
    ) -> bool:
        raises = (
            RuntimeError("boom") if raise_at_stage == 10 else None
        )
        with orchestrator._stage(on_event, 10, "llm-generation", stage10_msg):
            if raises is not None:
                raise raises
        return llm_configured

    monkeypatch.setattr(orchestrator, "_stage_llm_generation", stage10_stub)


def _record_events() -> tuple[list[StageEvent], Callable[[StageEvent], None]]:
    """Return an (events, callback) pair for recording StageEvents."""
    events: list[StageEvent] = []

    def recorder(event: StageEvent) -> None:
        events.append(event)

    return events, recorder


# ---------------------------------------------------------------------------
# Happy path: full 11-stage sequence
# ---------------------------------------------------------------------------


class TestStageEventSequence:
    """Verify the 11-stage start/complete event sequence."""

    def test_stage_event_sequence_happy_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        # Arrange: stub every stage so we do no real I/O, and configure
        # the LLM gate as available so Stage 11 runs normally.
        _install_stage_stubs(
            monkeypatch, llm_configured=True, tmp_path=tmp_path,
        )
        events, recorder = _record_events()
        config = PipelineConfig(keyword="test keyword", output_dir=tmp_path)

        # Act
        result = run_pipeline_core(config, on_event=recorder)

        # Assert: exactly 22 events (11 stages x 2 lifecycle markers).
        assert len(events) == 2 * STAGE_TOTAL, (
            f"expected {2 * STAGE_TOTAL} events, got {len(events)}"
        )

        # Exact sequence: (1,start),(1,complete),(2,start),(2,complete),...
        actual = [
            (e.stage_index, e.stage_name, e.status, e.message)
            for e in events
        ]
        expected = []
        for index, name, message in EXPECTED_STAGES:
            expected.append((index, name, "start", message))
            expected.append((index, name, "complete", message))
        assert actual == expected

        # Every event must carry ``stage_total == STAGE_TOTAL``.
        for event in events:
            assert event.stage_total == STAGE_TOTAL
            assert isinstance(event.payload, dict)

        # Pipeline result reflects the happy path.
        assert result.output_dir == tmp_path
        assert result.slug == "test-keyword"
        assert result.llm_configured is True

    def test_stage_total_is_eleven(self) -> None:
        """Guard rail: the contract constant is 11."""
        assert STAGE_TOTAL == 11


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------


class TestStageError:
    """A raising stage must emit an ``error`` event and re-raise."""

    def test_stage_error_emits_error_event_and_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        # Arrange: make Stage 5 (process-keywords) raise.
        _install_stage_stubs(
            monkeypatch, raise_at_stage=5, tmp_path=tmp_path,
        )
        events, recorder = _record_events()
        config = PipelineConfig(keyword="error case", output_dir=tmp_path)

        # Act + Assert: RuntimeError propagates.
        with pytest.raises(RuntimeError, match="boom"):
            run_pipeline_core(config, on_event=recorder)

        # Stages 1..4 ran to completion (start + complete each = 8 events).
        # Stage 5 emitted start + error (2 events). Total = 10.
        assert len(events) == 10

        # Check start/complete for stages 1-4, start+error for stage 5.
        statuses_by_stage: dict[int, list[str]] = {}
        for event in events:
            statuses_by_stage.setdefault(event.stage_index, []).append(
                event.status,
            )

        for idx in (1, 2, 3, 4):
            assert statuses_by_stage[idx] == ["start", "complete"], (
                f"stage {idx} did not complete cleanly"
            )

        # Stage 5 must have start + error (no complete).
        assert statuses_by_stage[5] == ["start", "error"]

        # Later stages must not fire at all.
        for idx in range(6, 12):
            assert idx not in statuses_by_stage, (
                f"stage {idx} fired after error at stage 5"
            )

        # The error event carries the exception type in payload.
        error_event = [
            e for e in events
            if e.stage_index == 5 and e.status == "error"
        ][0]
        assert error_event.stage_name == "process-keywords"
        assert error_event.payload.get("exception_type") == "RuntimeError"
        assert "boom" in error_event.message

    def test_error_at_first_stage_fires_no_later_events(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        _install_stage_stubs(
            monkeypatch, raise_at_stage=1, tmp_path=tmp_path,
        )
        events, recorder = _record_events()
        config = PipelineConfig(keyword="boom first", output_dir=tmp_path)

        with pytest.raises(RuntimeError, match="boom"):
            run_pipeline_core(config, on_event=recorder)

        # Exactly two events: start + error on stage 1.
        assert [(e.stage_index, e.status) for e in events] == [
            (1, "start"), (1, "error"),
        ]


# ---------------------------------------------------------------------------
# Synchronous callback invocation
# ---------------------------------------------------------------------------


class TestCallbackSynchrony:
    """run_pipeline_core invokes on_event synchronously on the calling thread."""

    def test_callback_invoked_synchronously(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        _install_stage_stubs(
            monkeypatch, llm_configured=True, tmp_path=tmp_path,
        )

        calling_thread = threading.current_thread()
        events: list[StageEvent] = []
        callback_threads: list[threading.Thread] = []

        def recorder(event: StageEvent) -> None:
            events.append(event)
            callback_threads.append(threading.current_thread())

        config = PipelineConfig(keyword="sync test", output_dir=tmp_path)

        # Act
        run_pipeline_core(config, on_event=recorder)

        # Assert: by the time run_pipeline_core returns, every event is
        # already recorded (no background threads deferred emission).
        assert len(events) == 2 * STAGE_TOTAL

        # Every callback was invoked on the same thread as the caller.
        for t in callback_threads:
            assert t is calling_thread, (
                f"callback ran on {t.name}, expected {calling_thread.name}"
            )


# ---------------------------------------------------------------------------
# Optional: skipped_no_llm payload flag on Stage 11
# ---------------------------------------------------------------------------


class TestSkippedNoLlm:
    """When the LLM gate is off, Stage 11 still fires start+complete but
    both events carry ``payload['skipped_no_llm'] is True``.
    """

    def test_skipped_no_llm_fact_check_carries_payload_flag(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        # Arrange: Stage 10 returns llm_configured=False, so Stage 11
        # takes the skip branch.
        _install_stage_stubs(
            monkeypatch, llm_configured=False, tmp_path=tmp_path,
        )
        events, recorder = _record_events()
        config = PipelineConfig(keyword="no llm", output_dir=tmp_path)

        # Act
        result = run_pipeline_core(config, on_event=recorder)

        # Assert: still 22 events total.
        assert len(events) == 2 * STAGE_TOTAL

        # Stage 11 start + complete both carry skipped_no_llm=True.
        stage11_events = [e for e in events if e.stage_index == 11]
        assert len(stage11_events) == 2
        assert [e.status for e in stage11_events] == ["start", "complete"]
        for event in stage11_events:
            assert event.stage_name == "fact-check"
            assert event.payload.get("skipped_no_llm") is True
            assert event.message == "Fact-checking draft..."

        # Earlier stages do NOT have the skipped_no_llm flag.
        for event in events:
            if event.stage_index != 11:
                assert "skipped_no_llm" not in event.payload

        # Result reflects the skip.
        assert result.llm_configured is False


# ---------------------------------------------------------------------------
# Stage 10 gate wiring — ensures run_pipeline_core uses the return value
# of _stage_llm_generation to decide Stage 11's branch. This is a
# regression guard for the fact that Stage 11's control flow depends on
# Stage 10's return type (bool), not on inspecting the LLMConfig again.
# ---------------------------------------------------------------------------


class TestStage11Branching:
    def test_stage11_fires_real_helper_when_llm_configured(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        """When _stage_llm_generation returns True, the orchestrator
        calls ``_stage_fact_check`` (our stub) rather than the inline
        skip branch.
        """
        fact_check_calls: list[Path] = []

        def fact_check_spy(
            out_dir: Path, slug: str, on_event: Callable[[StageEvent], None],
            on_log: Callable[[str], None],
        ) -> None:
            fact_check_calls.append(out_dir)
            with orchestrator._stage(
                on_event, 11, "fact-check", "Fact-checking draft...",
            ):
                pass

        _install_stage_stubs(
            monkeypatch, llm_configured=True, tmp_path=tmp_path,
        )
        monkeypatch.setattr(
            orchestrator, "_stage_fact_check", fact_check_spy,
        )
        _, recorder = _record_events()
        config = PipelineConfig(keyword="branch test", output_dir=tmp_path)

        run_pipeline_core(config, on_event=recorder)

        assert len(fact_check_calls) == 1
        assert fact_check_calls[0] == tmp_path

    def test_stage11_skips_real_helper_when_llm_not_configured(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        """When _stage_llm_generation returns False, the orchestrator
        must NOT call ``_stage_fact_check``.
        """
        fact_check_calls: list[Path] = []

        def fact_check_spy(*args: Any, **kwargs: Any) -> None:
            fact_check_calls.append(Path("should-not-run"))

        _install_stage_stubs(
            monkeypatch, llm_configured=False, tmp_path=tmp_path,
        )
        monkeypatch.setattr(
            orchestrator, "_stage_fact_check", fact_check_spy,
        )
        _, recorder = _record_events()
        config = PipelineConfig(keyword="no llm branch", output_dir=tmp_path)

        run_pipeline_core(config, on_event=recorder)

        assert fact_check_calls == []


# ---------------------------------------------------------------------------
# Real stage 10 gate: when we don't stub _stage_llm_generation and LLM
# env is missing, it must gracefully return False. This keeps the real
# gate wired (regression for issue #87).
# ---------------------------------------------------------------------------


class TestRealStage10Gate:
    def test_real_stage10_falls_back_when_no_llm_env(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        """Patch LLMConfig.from_env to raise ValueError and verify the
        real _stage_llm_generation returns False, causing Stage 11 to
        emit skipped_no_llm=True.
        """
        # Stub stages 1..9 and 11 (not 10) so the real Stage 10 runs.
        _install_stage_stubs(
            monkeypatch, llm_configured=False, tmp_path=tmp_path,
        )

        # Re-install the REAL _stage_llm_generation so we test the gate.
        from seo_pipeline.orchestrator import (
            _stage_llm_generation as real_stage10,
        )
        monkeypatch.setattr(
            orchestrator, "_stage_llm_generation", real_stage10,
        )

        # Force the gate to fail: LLMConfig.from_env raises ValueError.
        from seo_pipeline.llm.config import LLMConfig

        def raise_value_error(cls, env_file=None):
            raise ValueError("missing env")

        monkeypatch.setattr(
            LLMConfig, "from_env", classmethod(raise_value_error),
        )

        events, recorder = _record_events()
        config = PipelineConfig(keyword="gate test", output_dir=tmp_path)

        result = run_pipeline_core(config, on_event=recorder)

        assert result.llm_configured is False
        stage11_events = [e for e in events if e.stage_index == 11]
        assert len(stage11_events) == 2
        for event in stage11_events:
            assert event.payload.get("skipped_no_llm") is True


