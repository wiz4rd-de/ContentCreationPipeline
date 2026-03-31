"""Fetch keywords from DataForSEO related_keywords and keyword_suggestions endpoints.

Calls both endpoints in parallel with retry logic, saves raw responses,
then invokes merge_keywords for deterministic post-processing.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

import httpx

from seo_pipeline.utils.load_api_config import load_env
from seo_pipeline.utils.resolve_location import resolve_location

logger = logging.getLogger(__name__)

# Backoff constants: 1s initial, 2x factor, 8s max, 3 retries (4 total attempts).
# Smaller than fetch-serp (5s/1.5x/30s) because keywords endpoints are
# synchronous live calls -- failures resolve faster.
RETRY_INITIAL_DELAY = 1.0  # seconds
RETRY_FACTOR = 2
RETRY_MAX_DELAY = 8.0  # seconds
RETRY_MAX_ATTEMPTS = 3  # 3 retries = 4 total attempts
REQUEST_TIMEOUT = 30.0  # seconds


def calculate_backoff(
    attempt: int,
    *,
    initial_delay: float = RETRY_INITIAL_DELAY,
    factor: float = RETRY_FACTOR,
    max_delay: float = RETRY_MAX_DELAY,
) -> float:
    """Calculate exponential backoff delay in seconds.

    Args:
        attempt: Zero-based attempt number (0 = first retry).
        initial_delay: Base delay in seconds.
        factor: Multiplicative factor per attempt.
        max_delay: Upper bound on delay in seconds.

    Returns:
        Delay in seconds, capped at max_delay.
    """
    delay = min(initial_delay * (factor ** attempt), max_delay)
    return delay


async def call_endpoint(
    url: str,
    body: list[dict],
    auth: str,
    label: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Call a DataForSEO endpoint with retry logic and exponential backoff.

    Retries on: network errors, HTTP 5xx, and timeouts.
    Does NOT retry on: HTTP 4xx (permanent client errors).

    Args:
        url: Full URL to POST.
        body: Request body (will be JSON-serialised).
        auth: Basic auth token (base64-encoded user:pass).
        label: Human-readable label for log messages.
        client: Optional httpx.AsyncClient (injectable for testing).

    Returns:
        Parsed JSON response dict.

    Raises:
        httpx.HTTPStatusError: On non-retriable 4xx errors.
        httpx.HTTPError: After exhausting all retries.
    """
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)

    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
    }

    last_error: Exception | None = None
    try:
        for attempt in range(RETRY_MAX_ATTEMPTS + 1):
            if attempt > 0:
                delay = calculate_backoff(attempt - 1)
                logger.info(
                    "Retry %d/%d for %s after %.1fs...",
                    attempt, RETRY_MAX_ATTEMPTS, label, delay,
                )
                await asyncio.sleep(delay)

            try:
                response = await client.post(url, json=body, headers=headers)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                # Network error or timeout -- retriable
                last_error = exc
                if attempt < RETRY_MAX_ATTEMPTS:
                    logger.warning(
                        "Request failed for %s (attempt %d): %s",
                        label, attempt + 1, exc,
                    )
                    continue
                raise

            # HTTP 4xx = permanent client error, do not retry
            if 400 <= response.status_code < 500:
                raise httpx.HTTPStatusError(
                    f"API error {response.status_code}: {response.text}",
                    request=response.request,
                    response=response,
                )

            # HTTP 5xx = transient server error, retry
            if response.status_code >= 500:
                last_error = httpx.HTTPStatusError(
                    f"API error {response.status_code}: {response.text}",
                    request=response.request,
                    response=response,
                )
                if attempt < RETRY_MAX_ATTEMPTS:
                    logger.warning(
                        "Server error for %s (attempt %d): %d",
                        label, attempt + 1, response.status_code,
                    )
                    continue
                raise last_error

            return response.json()

        # Should not reach here, but guard anyway
        if last_error is not None:
            raise last_error
        raise RuntimeError(f"Unexpected state in call_endpoint for {label}")
    finally:
        if owns_client:
            await client.aclose()


async def fetch_keywords(
    seed_keyword: str,
    *,
    market: str,
    language: str,
    outdir: str,
    env_path: str,
    limit: int = 50,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Fetch keywords from DataForSEO and save raw responses.

    Calls related_keywords and keyword_suggestions endpoints in parallel,
    saves raw JSON responses to outdir, then invokes merge_keywords for
    deterministic post-processing.

    Args:
        seed_keyword: The seed keyword to expand.
        market: ISO 3166-1 alpha-2 country code (e.g., 'de', 'us').
        language: Language code (e.g., 'de', 'en').
        outdir: Output directory for raw responses and merged output.
        env_path: Path to api.env credentials file.
        limit: Max results per endpoint (default 50).
        client: Optional httpx.AsyncClient (injectable for testing).

    Returns:
        Path to the merged keywords-expanded.json file.

    Raises:
        ValueError: If market code is unknown.
        FileNotFoundError: If env_path does not exist.
        httpx.HTTPError: On API errors after retries exhausted.
    """
    # Load credentials and resolve location
    config = load_env(env_path)
    auth = config["auth"]
    base = config["base"]
    location_code = resolve_location(market)

    # Ensure output directory exists
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)

    request_body = [{
        "keyword": seed_keyword,
        "language_code": language,
        "location_code": location_code,
        "limit": limit,
    }]

    logger.info(
        'Fetching related keywords for "%s" (market=%s, lang=%s, limit=%d)...',
        seed_keyword, market, language, limit,
    )

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)

    try:
        # Call both endpoints in parallel (each retries independently)
        related_response, suggestions_response = await asyncio.gather(
            call_endpoint(
                f"{base}/dataforseo_labs/google/related_keywords/live",
                request_body,
                auth,
                "related_keywords",
                client=client,
            ),
            call_endpoint(
                f"{base}/dataforseo_labs/google/keyword_suggestions/live",
                request_body,
                auth,
                "keyword_suggestions",
                client=client,
            ),
        )
    finally:
        if owns_client:
            await client.aclose()

    # Save raw responses
    related_path = out / "keywords-related-raw.json"
    suggestions_path = out / "keywords-suggestions-raw.json"

    related_path.write_text(
        json.dumps(related_response, indent=2), encoding="utf-8"
    )
    suggestions_path.write_text(
        json.dumps(suggestions_response, indent=2), encoding="utf-8"
    )

    logger.info("Saved: %s", related_path)
    logger.info("Saved: %s", suggestions_path)

    # Invoke merge_keywords for deterministic post-processing
    expanded_path = out / "keywords-expanded.json"
    try:
        from seo_pipeline.keywords.merge_keywords import merge_keywords

        related_data = json.loads(related_path.read_text(encoding="utf-8"))
        suggestions_data = json.loads(suggestions_path.read_text(encoding="utf-8"))
        merged_output = merge_keywords(
            related_raw=related_data,
            suggestions_raw=suggestions_data,
            seed=seed_keyword,
        )
        text = (
            json.dumps(merged_output, indent=2)
            if isinstance(merged_output, dict)
            else merged_output
        )
        expanded_path.write_text(text, encoding="utf-8")
        logger.info("Saved: %s", expanded_path)
    except ImportError:
        logger.warning(
            "merge_keywords not available yet -- skipping merge step. "
            "Raw responses saved to %s",
            outdir,
        )

    return str(expanded_path)


def main() -> None:
    """CLI entry point matching the Node.js script interface."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Fetch keywords from DataForSEO endpoints"
    )
    parser.add_argument("seed_keyword", help="Seed keyword to expand")
    parser.add_argument("--market", required=True, help="ISO country code")
    parser.add_argument("--language", required=True, help="Language code")
    parser.add_argument("--outdir", required=True, help="Output directory")
    parser.add_argument(
        "--limit", type=int, default=50, help="Max results per endpoint"
    )
    parser.add_argument(
        "--env-path",
        default=str(Path(__file__).resolve().parent.parent.parent / "api.env"),
        help="Path to api.env file",
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, stream=sys.stderr)

    result = asyncio.run(
        fetch_keywords(
            args.seed_keyword,
            market=args.market,
            language=args.language,
            outdir=args.outdir,
            env_path=args.env_path,
            limit=args.limit,
        )
    )
    print(result)


if __name__ == "__main__":
    main()
