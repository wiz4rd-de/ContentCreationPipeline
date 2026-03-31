"""Tests for fetch_keywords module: pure functions and mocked HTTP calls."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from seo_pipeline.keywords.fetch_keywords import (
    RETRY_FACTOR,
    RETRY_INITIAL_DELAY,
    RETRY_MAX_DELAY,
    calculate_backoff,
    call_endpoint,
    fetch_keywords,
)

_SLEEP = "seo_pipeline.keywords.fetch_keywords.asyncio.sleep"


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

        # Patch merge_keywords import to avoid ImportError
        with patch.dict("sys.modules", {"seo_pipeline.keywords.merge_keywords": None}):
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

    async def test_fetch_keywords_calls_both_endpoints(self, tmp_path):
        """Verify both related and suggestions endpoints are called."""
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

        with patch.dict("sys.modules", {"seo_pipeline.keywords.merge_keywords": None}):
            await fetch_keywords(
                "test keyword",
                market="de",
                language="de",
                outdir=str(outdir),
                env_path=str(env_file),
                client=mock_client,
            )

        # Two calls: one for related_keywords, one for keyword_suggestions
        assert mock_client.post.call_count == 2

        urls_called = [call.args[0] for call in mock_client.post.call_args_list]
        assert any("related_keywords" in url for url in urls_called)
        assert any("keyword_suggestions" in url for url in urls_called)

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

        with patch.dict("sys.modules", {"seo_pipeline.keywords.merge_keywords": None}):
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

        with patch.dict("sys.modules", {"seo_pipeline.keywords.merge_keywords": None}):
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

        with patch.dict("sys.modules", {"seo_pipeline.keywords.merge_keywords": None}):
            result = await fetch_keywords(
                "test",
                market="de",
                language="de",
                outdir=str(outdir),
                env_path=str(env_file),
                client=mock_client,
            )

        assert result == str(outdir / "keywords-expanded.json")
