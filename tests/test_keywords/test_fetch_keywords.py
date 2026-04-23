"""Tests for fetch_keywords module: pure functions and mocked HTTP calls."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from seo_pipeline.keywords.fetch_keywords import (
    RETRY_FACTOR,
    RETRY_INITIAL_DELAY,
    RETRY_MAX_DELAY,
    build_kfk_date_range,
    calculate_backoff,
    call_endpoint,
    extract_task_id,
    fetch_kfk,
    fetch_keywords,
    is_task_ready,
)

_SLEEP = "seo_pipeline.keywords.fetch_keywords.asyncio.sleep"
_FETCH_KFK = "seo_pipeline.keywords.fetch_keywords.fetch_kfk"


# ---------------------------------------------------------------------------
# calculate_backoff
# ---------------------------------------------------------------------------


class TestCalculateBackoff:
    """Tests for the pure calculate_backoff function."""

    def test_first_retry(self):
        """Attempt 0 returns initial delay."""
        assert calculate_backoff(0) == RETRY_INITIAL_DELAY

    def test_second_retry(self):
        """Attempt 1 doubles the initial delay."""
        assert calculate_backoff(1) == RETRY_INITIAL_DELAY * RETRY_FACTOR

    def test_third_retry(self):
        """Attempt 2 quadruples the initial delay."""
        assert calculate_backoff(2) == RETRY_INITIAL_DELAY * (RETRY_FACTOR ** 2)

    def test_cap_at_max_delay(self):
        """Very high attempt number is capped at max_delay."""
        result = calculate_backoff(100)
        assert result == RETRY_MAX_DELAY

    def test_custom_parameters(self):
        """Custom initial_delay, factor, max_delay are respected."""
        result = calculate_backoff(
            2, initial_delay=0.5, factor=3, max_delay=10.0
        )
        # 0.5 * 3^2 = 4.5
        assert result == 4.5

    def test_custom_parameters_capped(self):
        """Custom params are capped at custom max_delay."""
        result = calculate_backoff(
            10, initial_delay=1.0, factor=2, max_delay=5.0
        )
        assert result == 5.0

    def test_exact_backoff_sequence(self):
        """Verify the exact sequence: 1s, 2s, 4s (matching Node.js)."""
        delays = [calculate_backoff(i) for i in range(3)]
        assert delays == [1.0, 2.0, 4.0]

    def test_zero_attempt(self):
        """Attempt 0 with defaults returns exactly 1.0."""
        assert calculate_backoff(0) == 1.0


# ---------------------------------------------------------------------------
# extract_task_id
# ---------------------------------------------------------------------------


class TestExtractTaskId:
    """Tests for extract_task_id (KFK async pattern)."""

    def test_success(self):
        resp = {
            "tasks": [{"id": "abc-123", "status_code": 20100}]
        }
        assert extract_task_id(resp) == "abc-123"

    def test_error_status(self):
        resp = {
            "tasks": [{
                "id": "abc-123",
                "status_code": 40501,
                "status_message": "bad request",
            }]
        }
        with pytest.raises(ValueError, match="40501"):
            extract_task_id(resp)

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


# ---------------------------------------------------------------------------
# is_task_ready
# ---------------------------------------------------------------------------


class TestIsTaskReady:
    """Tests for is_task_ready (KFK async pattern)."""

    def test_found(self):
        resp = {"tasks": [{"result": [{"id": "abc-123"}]}]}
        result = is_task_ready(resp, "abc-123")
        assert result == {"ready": True}

    def test_not_found(self):
        resp = {"tasks": [{"result": [{"id": "other-id"}]}]}
        assert is_task_ready(resp, "abc-123") is False

    def test_empty_response(self):
        assert is_task_ready({}, "abc") is False

    def test_empty_tasks(self):
        assert is_task_ready({"tasks": []}, "abc") is False

    def test_no_result(self):
        assert is_task_ready({"tasks": [{"result": None}]}, "abc") is False

    def test_empty_result(self):
        assert is_task_ready({"tasks": [{"result": []}]}, "abc") is False


# ---------------------------------------------------------------------------
# build_kfk_date_range
# ---------------------------------------------------------------------------


class TestBuildKfkDateRange:
    """Tests for build_kfk_date_range."""

    def test_returns_12_month_lookback(self):
        with patch(
            "seo_pipeline.keywords.fetch_keywords.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 22)
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            date_from, date_to = build_kfk_date_range()

        assert date_from == "2025-04-01"
        assert date_to == "2026-04-22"

    def test_january_wraps_to_previous_year(self):
        with patch(
            "seo_pipeline.keywords.fetch_keywords.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 15)
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            date_from, date_to = build_kfk_date_range()

        assert date_from == "2025-01-01"
        assert date_to == "2026-01-15"


# ---------------------------------------------------------------------------
# call_endpoint
# ---------------------------------------------------------------------------


def _make_response(
    status_code: int = 200,
    json_data: dict | None = None,
    text: str = "",
) -> httpx.Response:
    """Helper to build a mock httpx.Response."""
    resp = httpx.Response(
        status_code=status_code,
        request=httpx.Request("POST", "https://example.com/api"),
        json=json_data if json_data is not None else {"status": "ok"},
    )
    return resp


class TestCallEndpoint:
    """Tests for call_endpoint with mocked httpx."""

    async def test_success_on_first_attempt(self):
        """Successful 200 response returns parsed JSON."""
        expected = {"tasks": [{"result": [{"keyword": "test"}]}]}
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = httpx.Response(
            200,
            request=httpx.Request("POST", "https://api.example.com"),
            json=expected,
        )

        result = await call_endpoint(
            "https://api.example.com/endpoint",
            [{"keyword": "test"}],
            "dGVzdDp0ZXN0",
            "test_endpoint",
            client=mock_client,
        )

        assert result == expected
        assert mock_client.post.call_count == 1

    async def test_4xx_no_retry(self):
        """HTTP 4xx raises immediately without retrying."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = httpx.Response(
            403,
            request=httpx.Request("POST", "https://api.example.com"),
            text="Forbidden",
        )

        with pytest.raises(httpx.HTTPStatusError, match="403"):
            await call_endpoint(
                "https://api.example.com/endpoint",
                [{"keyword": "test"}],
                "dGVzdDp0ZXN0",
                "test_endpoint",
                client=mock_client,
            )

        # Only one attempt -- no retries on 4xx
        assert mock_client.post.call_count == 1

    async def test_5xx_retries_then_succeeds(self):
        """HTTP 5xx triggers retry; succeeds on second attempt."""
        ok_response = httpx.Response(
            200,
            request=httpx.Request("POST", "https://api.example.com"),
            json={"status": "ok"},
        )
        err_response = httpx.Response(
            503,
            request=httpx.Request("POST", "https://api.example.com"),
            text="Service Unavailable",
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.side_effect = [err_response, ok_response]

        with patch(_SLEEP, new_callable=AsyncMock):
            result = await call_endpoint(
                "https://api.example.com/endpoint",
                [{"keyword": "test"}],
                "dGVzdDp0ZXN0",
                "test_endpoint",
                client=mock_client,
            )

        assert result == {"status": "ok"}
        assert mock_client.post.call_count == 2

    async def test_5xx_exhausts_retries(self):
        """HTTP 5xx exhausts all retries then raises."""
        err_response = httpx.Response(
            500,
            request=httpx.Request("POST", "https://api.example.com"),
            text="Internal Server Error",
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = err_response

        with patch(_SLEEP, new_callable=AsyncMock):
            with pytest.raises(httpx.HTTPStatusError, match="500"):
                await call_endpoint(
                    "https://api.example.com/endpoint",
                    [{"keyword": "test"}],
                    "dGVzdDp0ZXN0",
                    "test_endpoint",
                    client=mock_client,
                )

        # 1 initial + 3 retries = 4 total attempts
        assert mock_client.post.call_count == 4

    async def test_network_error_retries(self):
        """Network errors trigger retries."""
        ok_response = httpx.Response(
            200,
            request=httpx.Request("POST", "https://api.example.com"),
            json={"status": "recovered"},
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.side_effect = [
            httpx.ConnectError("Connection refused"),
            ok_response,
        ]

        with patch(_SLEEP, new_callable=AsyncMock):
            result = await call_endpoint(
                "https://api.example.com/endpoint",
                [{"keyword": "test"}],
                "dGVzdDp0ZXN0",
                "test_endpoint",
                client=mock_client,
            )

        assert result == {"status": "recovered"}
        assert mock_client.post.call_count == 2

    async def test_timeout_retries(self):
        """Timeout errors trigger retries."""
        ok_response = httpx.Response(
            200,
            request=httpx.Request("POST", "https://api.example.com"),
            json={"status": "recovered"},
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.side_effect = [
            httpx.ReadTimeout("Read timed out"),
            ok_response,
        ]

        with patch(_SLEEP, new_callable=AsyncMock):
            result = await call_endpoint(
                "https://api.example.com/endpoint",
                [{"keyword": "test"}],
                "dGVzdDp0ZXN0",
                "test_endpoint",
                client=mock_client,
            )

        assert result == {"status": "recovered"}

    async def test_network_error_exhausts_retries(self):
        """Network errors exhaust retries then raise."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")

        with patch(_SLEEP, new_callable=AsyncMock):
            with pytest.raises(httpx.ConnectError):
                await call_endpoint(
                    "https://api.example.com/endpoint",
                    [{"keyword": "test"}],
                    "dGVzdDp0ZXN0",
                    "test_endpoint",
                    client=mock_client,
                )

        assert mock_client.post.call_count == 4

    async def test_auth_header_sent(self):
        """Verify the Authorization header is set correctly."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = httpx.Response(
            200,
            request=httpx.Request("POST", "https://api.example.com"),
            json={},
        )

        await call_endpoint(
            "https://api.example.com/endpoint",
            [{"keyword": "test"}],
            "bXlfdG9rZW4=",
            "test_endpoint",
            client=mock_client,
        )

        call_kwargs = mock_client.post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert headers["Authorization"] == "Basic bXlfdG9rZW4="
        assert headers["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
# fetch_kfk (async task_post/poll/task_get)
# ---------------------------------------------------------------------------


class TestFetchKfk:
    """Tests for the async keywords_for_keywords fetch."""

    async def test_successful_flow(self):
        """Happy path: task_post -> tasks_ready (found) -> task_get."""
        task_post_resp = {
            "tasks": [{"id": "kfk-task-1", "status_code": 20100}]
        }
        tasks_ready_resp = {
            "tasks": [{"result": [{"id": "kfk-task-1"}]}]
        }
        task_get_resp = {
            "tasks": [{
                "status_code": 20000,
                "result": [{"keyword": "sintra pena palace"}],
            }]
        }

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = httpx.Response(
            200,
            request=httpx.Request("POST", "https://api.example.com/task_post"),
            json=task_post_resp,
        )
        mock_client.get.side_effect = [
            httpx.Response(
                200,
                request=httpx.Request("GET", "https://api.example.com/tasks_ready"),
                json=tasks_ready_resp,
            ),
            httpx.Response(
                200,
                request=httpx.Request("GET", "https://api.example.com/task_get"),
                json=task_get_resp,
            ),
        ]

        with patch(_SLEEP, new_callable=AsyncMock):
            result = await fetch_kfk(
                "sintra",
                language="de",
                location_code=2276,
                base="https://api.example.com",
                auth="dGVzdDp0ZXN0",
                client=mock_client,
                timeout=120,
            )

        assert result == task_get_resp
        # 1 POST for task_post
        assert mock_client.post.call_count == 1
        # 2 GETs: tasks_ready + task_get
        assert mock_client.get.call_count == 2

    async def test_polls_until_ready(self):
        """Task not ready on first poll, ready on second."""
        task_post_resp = {
            "tasks": [{"id": "kfk-task-2", "status_code": 20100}]
        }
        not_ready_resp = {"tasks": [{"result": []}]}
        ready_resp = {
            "tasks": [{"result": [{"id": "kfk-task-2"}]}]
        }
        task_get_resp = {
            "tasks": [{"status_code": 20000, "result": []}]
        }

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = httpx.Response(
            200,
            request=httpx.Request("POST", "https://api.example.com/task_post"),
            json=task_post_resp,
        )
        mock_client.get.side_effect = [
            httpx.Response(
                200,
                request=httpx.Request("GET", "https://api.example.com/tasks_ready"),
                json=not_ready_resp,
            ),
            httpx.Response(
                200,
                request=httpx.Request("GET", "https://api.example.com/tasks_ready"),
                json=ready_resp,
            ),
            httpx.Response(
                200,
                request=httpx.Request("GET", "https://api.example.com/task_get"),
                json=task_get_resp,
            ),
        ]

        with patch(_SLEEP, new_callable=AsyncMock):
            result = await fetch_kfk(
                "sintra",
                language="de",
                location_code=2276,
                base="https://api.example.com",
                auth="dGVzdDp0ZXN0",
                client=mock_client,
                timeout=120,
            )

        assert result == task_get_resp
        # 3 GETs: 2 polls + 1 task_get
        assert mock_client.get.call_count == 3

    async def test_timeout_raises(self):
        """Polling exceeds timeout raises ValueError."""
        task_post_resp = {
            "tasks": [{"id": "kfk-timeout", "status_code": 20100}]
        }
        not_ready_resp = {"tasks": [{"result": []}]}

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = httpx.Response(
            200,
            request=httpx.Request("POST", "https://api.example.com/task_post"),
            json=task_post_resp,
        )
        mock_client.get.return_value = httpx.Response(
            200,
            request=httpx.Request("GET", "https://api.example.com/tasks_ready"),
            json=not_ready_resp,
        )

        # Use timeout=0 so the loop times out immediately after first sleep
        with patch(_SLEEP, new_callable=AsyncMock):
            with patch(
                "seo_pipeline.keywords.fetch_keywords._monotonic_ms",
                side_effect=[0.0, 0.0, 200_000.0],
            ):
                with pytest.raises(ValueError, match="timed out"):
                    await fetch_kfk(
                        "sintra",
                        language="de",
                        location_code=2276,
                        base="https://api.example.com",
                        auth="dGVzdDp0ZXN0",
                        client=mock_client,
                        timeout=120,
                    )

    async def test_task_get_error_raises(self):
        """task_get returning non-20000 status raises ValueError."""
        task_post_resp = {
            "tasks": [{"id": "kfk-err", "status_code": 20100}]
        }
        ready_resp = {
            "tasks": [{"result": [{"id": "kfk-err"}]}]
        }
        task_get_resp = {
            "tasks": [{
                "status_code": 40401,
                "status_message": "Task not found",
            }]
        }

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = httpx.Response(
            200,
            request=httpx.Request("POST", "https://api.example.com/task_post"),
            json=task_post_resp,
        )
        mock_client.get.side_effect = [
            httpx.Response(
                200,
                request=httpx.Request("GET", "https://api.example.com/tasks_ready"),
                json=ready_resp,
            ),
            httpx.Response(
                200,
                request=httpx.Request("GET", "https://api.example.com/task_get"),
                json=task_get_resp,
            ),
        ]

        with patch(_SLEEP, new_callable=AsyncMock):
            with pytest.raises(ValueError, match="40401"):
                await fetch_kfk(
                    "sintra",
                    language="de",
                    location_code=2276,
                    base="https://api.example.com",
                    auth="dGVzdDp0ZXN0",
                    client=mock_client,
                    timeout=120,
                )

    async def test_post_body_format(self):
        """Verify KFK post body uses 'keywords' (array), not 'keyword'."""
        task_post_resp = {
            "tasks": [{"id": "kfk-body", "status_code": 20100}]
        }
        ready_resp = {"tasks": [{"result": [{"id": "kfk-body"}]}]}
        get_resp = {"tasks": [{"status_code": 20000, "result": []}]}

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = httpx.Response(
            200,
            request=httpx.Request("POST", "https://api.example.com/task_post"),
            json=task_post_resp,
        )
        mock_client.get.side_effect = [
            httpx.Response(
                200,
                request=httpx.Request("GET", "https://api.example.com"),
                json=ready_resp,
            ),
            httpx.Response(
                200,
                request=httpx.Request("GET", "https://api.example.com"),
                json=get_resp,
            ),
        ]

        with patch(_SLEEP, new_callable=AsyncMock):
            await fetch_kfk(
                "sintra palace",
                language="de",
                location_code=2276,
                base="https://api.example.com",
                auth="dGVzdDp0ZXN0",
                client=mock_client,
            )

        post_call = mock_client.post.call_args
        body = post_call.kwargs.get("json") or post_call[1].get("json")
        assert body[0]["keywords"] == ["sintra palace"]
        assert "keyword" not in body[0]
        assert body[0]["language_code"] == "de"
        assert body[0]["location_code"] == 2276
        # date_from and date_to should be present
        assert "date_from" in body[0]
        assert "date_to" in body[0]


# ---------------------------------------------------------------------------
# fetch_keywords (integration with mocked HTTP)
# ---------------------------------------------------------------------------


class TestFetchKeywords:
    """Integration tests for fetch_keywords with mocked dependencies."""

    async def test_fetch_keywords_saves_raw_responses(self, tmp_path):
        """Verify raw JSON responses are saved to outdir."""
        env_file = tmp_path / "api.env"
        env_file.write_text(
            "DATAFORSEO_AUTH=dGVzdDp0ZXN0\nDATAFORSEO_BASE=https://api.example.com"
        )

        related_data = {"tasks": [{"result": [{"keyword": "related1"}]}]}
        suggestions_data = {"tasks": [{"result": [{"keyword": "suggestion1"}]}]}

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.side_effect = [
            httpx.Response(
                200,
                request=httpx.Request("POST", "https://api.example.com/related"),
                json=related_data,
            ),
            httpx.Response(
                200,
                request=httpx.Request("POST", "https://api.example.com/suggestions"),
                json=suggestions_data,
            ),
        ]

        outdir = tmp_path / "output"

        # Patch fetch_kfk and merge_keywords to isolate the test
        with (
            patch(_FETCH_KFK, new_callable=AsyncMock, return_value=None) as mock_kfk,
            patch.dict("sys.modules", {"seo_pipeline.keywords.merge_keywords": None}),
        ):
            # Make _kfk_with_fallback return None (fetch_kfk raises, fallback catches)
            mock_kfk.side_effect = ValueError("test skip")
            await fetch_keywords(
                "test keyword",
                market="de",
                language="de",
                outdir=str(outdir),
                env_path=str(env_file),
                limit=10,
                client=mock_client,
            )

        # Verify raw files exist and contain correct data
        related_path = outdir / "keywords-related-raw.json"
        suggestions_path = outdir / "keywords-suggestions-raw.json"

        assert related_path.exists()
        assert suggestions_path.exists()

        assert json.loads(related_path.read_text()) == related_data
        assert json.loads(suggestions_path.read_text()) == suggestions_data

    async def test_fetch_keywords_calls_all_three_endpoints(self, tmp_path):
        """Verify related, suggestions, and KFK endpoints are called."""
        env_file = tmp_path / "api.env"
        env_file.write_text(
            "DATAFORSEO_AUTH=dGVzdDp0ZXN0\nDATAFORSEO_BASE=https://api.example.com"
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = httpx.Response(
            200,
            request=httpx.Request("POST", "https://api.example.com"),
            json={"status": "ok"},
        )

        kfk_data = {"tasks": [{"status_code": 20000, "result": []}]}

        outdir = tmp_path / "output"

        with (
            patch(_FETCH_KFK, new_callable=AsyncMock, return_value=kfk_data),
            patch.dict("sys.modules", {"seo_pipeline.keywords.merge_keywords": None}),
        ):
            await fetch_keywords(
                "test keyword",
                market="de",
                language="de",
                outdir=str(outdir),
                env_path=str(env_file),
                client=mock_client,
            )

        # Two calls for related + suggestions (KFK is patched separately)
        assert mock_client.post.call_count == 2

        urls_called = [call.args[0] for call in mock_client.post.call_args_list]
        assert any("related_keywords" in url for url in urls_called)
        assert any("keyword_suggestions" in url for url in urls_called)

    async def test_fetch_keywords_saves_kfk_raw(self, tmp_path):
        """Verify KFK raw response is saved when available."""
        env_file = tmp_path / "api.env"
        env_file.write_text(
            "DATAFORSEO_AUTH=dGVzdDp0ZXN0\nDATAFORSEO_BASE=https://api.example.com"
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = httpx.Response(
            200,
            request=httpx.Request("POST", "https://api.example.com"),
            json={"status": "ok"},
        )

        kfk_data = {
            "tasks": [{
                "status_code": 20000,
                "result": [{"keyword": "sintra palace"}],
            }]
        }
        outdir = tmp_path / "output"

        with (
            patch(_FETCH_KFK, new_callable=AsyncMock, return_value=kfk_data),
            patch.dict("sys.modules", {"seo_pipeline.keywords.merge_keywords": None}),
        ):
            await fetch_keywords(
                "sintra",
                market="de",
                language="de",
                outdir=str(outdir),
                env_path=str(env_file),
                client=mock_client,
            )

        kfk_path = outdir / "keywords-for-keywords-raw.json"
        assert kfk_path.exists()
        assert json.loads(kfk_path.read_text()) == kfk_data

    async def test_fetch_keywords_kfk_failure_graceful(self, tmp_path):
        """KFK failure does not break the pipeline -- graceful degradation."""
        env_file = tmp_path / "api.env"
        env_file.write_text(
            "DATAFORSEO_AUTH=dGVzdDp0ZXN0\nDATAFORSEO_BASE=https://api.example.com"
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = httpx.Response(
            200,
            request=httpx.Request("POST", "https://api.example.com"),
            json={"status": "ok"},
        )

        outdir = tmp_path / "output"

        with (
            patch(
                _FETCH_KFK,
                new_callable=AsyncMock,
                side_effect=ValueError("API down"),
            ),
            patch.dict("sys.modules", {"seo_pipeline.keywords.merge_keywords": None}),
        ):
            # Should not raise
            result = await fetch_keywords(
                "test",
                market="de",
                language="de",
                outdir=str(outdir),
                env_path=str(env_file),
                client=mock_client,
            )

        assert result == str(outdir / "keywords-expanded.json")
        # KFK raw file should NOT exist
        assert not (outdir / "keywords-for-keywords-raw.json").exists()
        # But the other two should exist
        assert (outdir / "keywords-related-raw.json").exists()
        assert (outdir / "keywords-suggestions-raw.json").exists()

    async def test_fetch_keywords_creates_outdir(self, tmp_path):
        """Verify outdir is created if it doesn't exist."""
        env_file = tmp_path / "api.env"
        env_file.write_text(
            "DATAFORSEO_AUTH=dGVzdDp0ZXN0\nDATAFORSEO_BASE=https://api.example.com"
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = httpx.Response(
            200,
            request=httpx.Request("POST", "https://api.example.com"),
            json={},
        )

        outdir = tmp_path / "nested" / "deep" / "output"
        assert not outdir.exists()

        with (
            patch(_FETCH_KFK, new_callable=AsyncMock, side_effect=ValueError("skip")),
            patch.dict("sys.modules", {"seo_pipeline.keywords.merge_keywords": None}),
        ):
            await fetch_keywords(
                "test keyword",
                market="de",
                language="de",
                outdir=str(outdir),
                env_path=str(env_file),
                client=mock_client,
            )

        assert outdir.exists()

    async def test_fetch_keywords_request_body(self, tmp_path):
        """Verify the request body contains correct fields."""
        env_file = tmp_path / "api.env"
        env_file.write_text(
            "DATAFORSEO_AUTH=dGVzdDp0ZXN0\nDATAFORSEO_BASE=https://api.example.com"
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = httpx.Response(
            200,
            request=httpx.Request("POST", "https://api.example.com"),
            json={},
        )

        outdir = tmp_path / "output"

        with (
            patch(_FETCH_KFK, new_callable=AsyncMock, side_effect=ValueError("skip")),
            patch.dict("sys.modules", {"seo_pipeline.keywords.merge_keywords": None}),
        ):
            await fetch_keywords(
                "seo tools",
                market="de",
                language="de",
                outdir=str(outdir),
                env_path=str(env_file),
                limit=25,
                client=mock_client,
            )

        # Check the body sent to the first call
        call_kwargs = mock_client.post.call_args_list[0]
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body == [{
            "keyword": "seo tools",
            "language_code": "de",
            "location_code": 2276,  # Germany
            "limit": 25,
        }]

    async def test_fetch_keywords_returns_expanded_path(self, tmp_path):
        """Verify the return value is the expanded file path."""
        env_file = tmp_path / "api.env"
        env_file.write_text(
            "DATAFORSEO_AUTH=dGVzdDp0ZXN0\nDATAFORSEO_BASE=https://api.example.com"
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = httpx.Response(
            200,
            request=httpx.Request("POST", "https://api.example.com"),
            json={},
        )

        outdir = tmp_path / "output"

        with (
            patch(_FETCH_KFK, new_callable=AsyncMock, side_effect=ValueError("skip")),
            patch.dict("sys.modules", {"seo_pipeline.keywords.merge_keywords": None}),
        ):
            result = await fetch_keywords(
                "test",
                market="de",
                language="de",
                outdir=str(outdir),
                env_path=str(env_file),
                client=mock_client,
            )

        assert result == str(outdir / "keywords-expanded.json")
