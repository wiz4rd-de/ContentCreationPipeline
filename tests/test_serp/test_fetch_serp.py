"""Tests for fetch_serp -- pure functions + async workflow."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from seo_pipeline.serp.fetch_serp import (
    adjust_timeout,
    build_live_url,
    calculate_backoff,
    check_cache,
    derive_outdir,
    extract_task_id,
    fetch_serp,
    is_task_ready,
    should_fallback,
)

FIXTURES_DIR = (
    Path(__file__).parent.parent.parent / "tests" / "fixtures" / "fetch-serp"
)


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


# --- extract_task_id ---


class TestExtractTaskId:
    def test_success(self):
        data = _load_fixture("task-post-success.json")
        assert extract_task_id(data) == "03101504-6886-0139-0000-3d651db5c686"

    def test_error_response(self):
        data = _load_fixture("task-post-error.json")
        with pytest.raises(ValueError, match="task_post failed with status 40501"):
            extract_task_id(data)

    def test_no_tasks(self):
        with pytest.raises(ValueError, match="no tasks"):
            extract_task_id({"tasks": []})

    def test_missing_tasks_key(self):
        with pytest.raises(ValueError, match="no tasks"):
            extract_task_id({})

    def test_no_status_code(self):
        with pytest.raises(ValueError, match="no status_code"):
            extract_task_id({"tasks": [{"id": "abc"}]})

    def test_no_task_id(self):
        with pytest.raises(ValueError, match="no task ID"):
            extract_task_id({"tasks": [{"status_code": 20100}]})


# --- is_task_ready ---


class TestIsTaskReady:
    def test_target_found(self):
        data = _load_fixture("tasks-ready-with-target.json")
        result = is_task_ready(data, "03101504-6886-0139-0000-3d651db5c686")
        assert result["ready"] is True
        assert "advanced" in result["endpoint_advanced"]

    def test_target_not_found(self):
        data = _load_fixture("tasks-ready-without-target.json")
        result = is_task_ready(data, "03101504-6886-0139-0000-3d651db5c686")
        assert result is False

    def test_empty_response(self):
        assert is_task_ready({}, "some-id") is False

    def test_empty_tasks(self):
        assert is_task_ready({"tasks": []}, "some-id") is False

    def test_tasks_with_no_result(self):
        data = {"tasks": [{"result": None}]}
        assert is_task_ready(data, "some-id") is False

    def test_tasks_with_empty_result(self):
        data = {"tasks": [{"result": []}]}
        assert is_task_ready(data, "some-id") is False


# --- calculate_backoff ---


class TestCalculateBackoff:
    def test_attempt_zero(self):
        assert calculate_backoff(0) == 5000.0

    def test_attempt_one(self):
        assert calculate_backoff(1) == 7500.0

    def test_attempt_two(self):
        assert calculate_backoff(2) == 11250.0

    def test_capped_at_max(self):
        # With default max_delay=30000, large attempts should cap
        result = calculate_backoff(20)
        assert result == 30000.0

    def test_custom_params(self):
        result = calculate_backoff(
            2, initial_delay=1000, factor=2.0, max_delay=10000
        )
        assert result == 4000.0

    def test_matches_node_js_formula(self):
        """Verify same formula as JS: min(initial * factor^attempt, max)."""
        opts = {"initial_delay": 5000, "factor": 1.5, "max_delay": 30000}
        expected = [5000, 7500, 11250, 16875, 25312.5, 30000]
        for i, exp in enumerate(expected):
            assert calculate_backoff(i, **opts) == exp


# --- check_cache ---


class TestCheckCache:
    def test_file_not_found(self, tmp_path):
        result = check_cache(tmp_path / "nonexistent.json")
        assert result == {"hit": False, "reason": "file not found"}

    def test_invalid_json(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        result = check_cache(bad)
        assert result == {"hit": False, "reason": "invalid JSON"}

    def test_missing_tasks(self, tmp_path):
        f = tmp_path / "serp.json"
        f.write_text("{}", encoding="utf-8")
        result = check_cache(f)
        assert result["reason"] == "missing or empty tasks array"

    def test_missing_result(self, tmp_path):
        f = tmp_path / "serp.json"
        f.write_text(json.dumps({"tasks": [{}]}), encoding="utf-8")
        result = check_cache(f)
        assert result["reason"] == "missing or empty result array"

    def test_missing_items(self, tmp_path):
        f = tmp_path / "serp.json"
        f.write_text(
            json.dumps({"tasks": [{"result": [{}]}]}), encoding="utf-8"
        )
        result = check_cache(f)
        assert result["reason"] == "missing or empty items array"

    def test_valid_cache_hit(self):
        result = check_cache(
            FIXTURES_DIR / "serp-raw-with-timestamp.json",
            "Urlaub Mallorca",
        )
        assert result["hit"] is True
        assert "tasks" in result["data"]

    def test_keyword_mismatch(self):
        result = check_cache(
            FIXTURES_DIR / "serp-raw-with-timestamp.json",
            "wrong keyword",
        )
        assert result["hit"] is False
        assert "keyword mismatch" in result["reason"]

    def test_expired_cache(self):
        # Fixture has _pipeline_fetched_at = 2026-03-11 which is > 7 days ago
        result = check_cache(
            FIXTURES_DIR / "serp-raw-with-timestamp.json",
            "Urlaub Mallorca",
            max_age_days=7,
        )
        assert result["hit"] is False
        assert result["reason"] == "expired"
        assert "age_days" in result

    def test_cache_within_ttl(self):
        # Use a very large max_age so it's always valid
        result = check_cache(
            FIXTURES_DIR / "serp-raw-with-timestamp.json",
            "Urlaub Mallorca",
            max_age_days=99999,
        )
        assert result["hit"] is True

    def test_no_keyword_check(self):
        """When keyword is None, skip keyword validation."""
        result = check_cache(FIXTURES_DIR / "serp-raw-with-timestamp.json")
        assert result["hit"] is True


# --- derive_outdir ---


class TestDeriveOutdir:
    @patch("seo_pipeline.serp.fetch_serp.datetime")
    def test_basic(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 3, 15)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = derive_outdir("Thailand Urlaub", "/output")
        assert result == "/output/2026-03-15_thailand-urlaub"

    @patch("seo_pipeline.serp.fetch_serp.datetime")
    def test_with_umlauts(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 1, 5)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = derive_outdir("Flüge München", "/out")
        assert result == "/out/2026-01-05_fluege-muenchen"


# --- build_live_url ---


class TestBuildLiveUrl:
    def test_basic(self):
        assert (
            build_live_url("https://api.dataforseo.com/v3")
            == "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
        )


# --- should_fallback ---


class TestShouldFallback:
    def test_disabled(self):
        assert should_fallback(999999, 0) is False

    def test_not_yet(self):
        assert should_fallback(100000, 300) is False

    def test_exceeded(self):
        assert should_fallback(300000, 300) is True

    def test_just_at_threshold(self):
        assert should_fallback(300000, 300) is True

    def test_negative_timeout(self):
        assert should_fallback(1000, -1) is False


# --- adjust_timeout ---


class TestAdjustTimeout:
    def test_already_sufficient(self):
        assert adjust_timeout(400, 300) == 400

    def test_auto_raised(self):
        assert adjust_timeout(120, 300) == 330

    def test_fallback_disabled(self):
        assert adjust_timeout(60, 0) == 60

    def test_custom_buffer(self):
        assert adjust_timeout(120, 300, buffer=60) == 360


# --- fetch_serp async workflow ---


def _mock_response(data: dict) -> MagicMock:
    """Build a mock httpx response returning ``data`` as JSON.

    httpx responses have synchronous .json() and .raise_for_status(),
    so we use MagicMock (not AsyncMock) for these attributes.
    """
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


def _sequenced_client(responses: list[AsyncMock]):
    """Return (mock_client_cm, call_count) for sequential responses."""
    call_count = {"n": 0}

    async def _dispatch(url, **_kw):
        idx = min(call_count["n"], len(responses) - 1)
        call_count["n"] += 1
        return responses[idx]

    client = AsyncMock()
    client.post = AsyncMock(side_effect=_dispatch)
    client.get = AsyncMock(side_effect=_dispatch)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client, call_count


_MOD = "seo_pipeline.serp.fetch_serp"
_SLEEP = f"{_MOD}.asyncio.sleep"
_CLIENT = f"{_MOD}.httpx.AsyncClient"
_CLOCK = f"{_MOD}._monotonic_ms"


class TestFetchSerpAsync:
    """Async workflow with mocked httpx and filesystem."""

    @pytest.fixture
    def api_env(self, tmp_path):
        env_file = tmp_path / "api.env"
        env_file.write_text(
            "DATAFORSEO_AUTH=dGVzdDp0ZXN0\n"
            "DATAFORSEO_BASE=https://api.test.com/v3",
            encoding="utf-8",
        )
        return str(env_file)

    @pytest.fixture
    def outdir(self, tmp_path):
        d = tmp_path / "output"
        d.mkdir()
        return str(d)

    @pytest.mark.asyncio
    async def test_cache_hit_returns_early(
        self, tmp_path, api_env
    ):
        """Valid cache returns data without API calls."""
        out = str(tmp_path / "cached-output")
        Path(out).mkdir()
        fixture = _load_fixture("serp-raw-with-timestamp.json")
        (Path(out) / "serp-raw.json").write_text(
            json.dumps(fixture), encoding="utf-8"
        )

        result = await fetch_serp(
            keyword="Urlaub Mallorca",
            market="de",
            language="de",
            outdir=out,
            env_path=api_env,
            max_age=99999,
        )
        kw = result["tasks"][0]["data"]["keyword"]
        assert kw == "Urlaub Mallorca"

    @pytest.mark.asyncio
    async def test_async_workflow_success(
        self, api_env, outdir
    ):
        """Full async workflow: post -> poll -> get."""
        resps = [
            _mock_response(_load_fixture("task-post-success.json")),
            _mock_response(
                _load_fixture("tasks-ready-with-target.json")
            ),
            _mock_response(
                _load_fixture("task-get-success.json")
            ),
        ]
        client, _ = _sequenced_client(resps)

        with patch(_CLIENT, return_value=client):
            with patch(_SLEEP, new_callable=AsyncMock):
                result = await fetch_serp(
                    keyword="Urlaub Mallorca",
                    market="de",
                    language="de",
                    outdir=outdir,
                    env_path=api_env,
                    force=True,
                )

        assert result["_pipeline_source"] == "async"
        assert "_pipeline_fetched_at" in result
        kw = result["tasks"][0]["data"]["keyword"]
        assert kw == "Urlaub Mallorca"
        assert (Path(outdir) / "serp-raw.json").exists()

    @pytest.mark.asyncio
    async def test_fallback_to_live(self, api_env, outdir):
        """Polling timeout triggers live-endpoint fallback."""
        resps = [
            _mock_response(
                _load_fixture("task-post-success.json")
            ),
            _mock_response(
                _load_fixture("tasks-ready-without-target.json")
            ),
            _mock_response(
                _load_fixture("task-get-success.json")
            ),
        ]
        client, _ = _sequenced_client(resps)

        # Clock: start=0, first check exceeds fallback
        times = iter([0, 0, 400_000])

        with patch(_CLIENT, return_value=client):
            with patch(_SLEEP, new_callable=AsyncMock):
                with patch(_CLOCK, side_effect=times):
                    result = await fetch_serp(
                        keyword="Urlaub Mallorca",
                        market="de",
                        language="de",
                        outdir=outdir,
                        env_path=api_env,
                        force=True,
                        fallback_timeout=1,
                        timeout=60,
                    )

        assert result["_pipeline_source"] == "live_fallback"

    @pytest.mark.asyncio
    async def test_timeout_raises(self, api_env, outdir):
        """Exceeded timeout with no fallback raises ValueError."""
        resps = [
            _mock_response(
                _load_fixture("task-post-success.json")
            ),
            _mock_response(
                _load_fixture("tasks-ready-without-target.json")
            ),
        ]
        client, _ = _sequenced_client(resps)

        times = iter([0, 200_000])

        with patch(_CLIENT, return_value=client):
            with patch(_SLEEP, new_callable=AsyncMock):
                with patch(_CLOCK, side_effect=times):
                    with pytest.raises(
                        ValueError, match="timed out"
                    ):
                        await fetch_serp(
                            keyword="Urlaub Mallorca",
                            market="de",
                            language="de",
                            outdir=outdir,
                            env_path=api_env,
                            force=True,
                            fallback_timeout=0,
                            timeout=60,
                        )
