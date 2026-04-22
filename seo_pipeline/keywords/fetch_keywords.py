"""Fetch keywords from DataForSEO related_keywords, keyword_suggestions,
and keywords_for_keywords endpoints.

Calls all three endpoints concurrently with retry logic, saves raw responses,
then invokes merge_keywords for deterministic post-processing.
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

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

# Async polling constants for keywords_for_keywords endpoint
KFK_POLL_TIMEOUT = 120  # seconds before giving up on async task


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


def extract_task_id(response: dict) -> str:
    """Extract task UUID from a task_post response.

    Args:
        response: parsed JSON from task_post

    Returns:
        The task ID string

    Raises:
        ValueError: if the response is malformed or reports an error
    """
    tasks = response.get("tasks")
    if not tasks:
        raise ValueError("task_post returned no tasks in response")

    task = tasks[0]
    status_code = task.get("status_code")
    if status_code is None:
        raise ValueError("task_post returned no status_code")

    if str(status_code) != "20100":
        msg = task.get("status_message", "unknown error")
        raise ValueError(
            f"task_post failed with status {status_code}: {msg}"
        )

    task_id = task.get("id")
    if task_id is None:
        raise ValueError("task_post returned no task ID")

    return task_id


def is_task_ready(
    response: dict, task_id: str
) -> dict[str, Any] | bool:
    """Check if a specific task ID appears in a tasks_ready response.

    Returns False if the task is not found, or a dict with
    ``{'ready': True}`` if found.
    """
    tasks = response.get("tasks")
    if not tasks:
        return False

    for t in tasks:
        results = t.get("result")
        if not results:
            continue
        for r in results:
            if r.get("id") == task_id:
                return {"ready": True}

    return False


def build_kfk_date_range() -> tuple[str, str]:
    """Build a 12-month lookback date range for the KFK endpoint.

    Returns:
        (date_from, date_to) as YYYY-MM-DD strings.
        date_from is the 1st of the month 12 months ago.
        date_to is today's date.
    """
    today = datetime.now()
    date_to = today.strftime("%Y-%m-%d")
    # 12 months ago: subtract 12 from month, adjust year
    month = today.month - 12
    year = today.year
    while month < 1:
        month += 12
        year -= 1
    date_from = f"{year}-{month:02d}-01"
    return date_from, date_to


def _monotonic_ms() -> float:
    """Return monotonic clock time in milliseconds."""
    return time.monotonic() * 1000


async def fetch_kfk(
    seed_keyword: str,
    *,
    language: str,
    location_code: int,
    base: str,
    auth: str,
    client: httpx.AsyncClient,
    timeout: int = KFK_POLL_TIMEOUT,
) -> dict:
    """Fetch keywords_for_keywords via async task_post/poll/task_get.

    Args:
        seed_keyword: The seed keyword.
        language: Language code (e.g. 'de').
        location_code: DataForSEO location code.
        base: API base URL.
        auth: Base64-encoded auth string.
        client: httpx.AsyncClient to use.
        timeout: Max seconds to wait for async task completion.

    Returns:
        Parsed JSON response from task_get.

    Raises:
        ValueError: On API errors or timeout.
    """
    date_from, date_to = build_kfk_date_range()

    kfk_base = f"{base}/keywords_data/google_ads/keywords_for_keywords"
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
    }

    post_body = [{
        "keywords": [seed_keyword],
        "language_code": language,
        "location_code": location_code,
        "date_from": date_from,
        "date_to": date_to,
    }]

    # Step 1: Post task
    logger.info(
        'Posting keywords_for_keywords task for "%s" '
        "(location=%d, lang=%s, %s to %s)...",
        seed_keyword, location_code, language, date_from, date_to,
    )

    post_resp = await client.post(
        f"{kfk_base}/task_post",
        headers=headers,
        json=post_body,
    )
    post_resp.raise_for_status()
    post_data = post_resp.json()

    task_id = extract_task_id(post_data)
    logger.info("KFK task created: %s", task_id)

    # Step 2: Poll tasks_ready with exponential backoff
    timeout_ms = timeout * 1000
    start_time = _monotonic_ms()
    attempt = 0

    while True:
        elapsed = _monotonic_ms() - start_time
        if elapsed >= timeout_ms:
            raise ValueError(
                f"KFK task {task_id} timed out after {timeout} seconds"
            )

        delay = calculate_backoff(attempt)
        logger.info(
            "KFK: waiting %.1fs before poll attempt %d...",
            delay, attempt + 1,
        )
        await asyncio.sleep(delay)

        ready_resp = await client.get(
            f"{kfk_base}/tasks_ready",
            headers={"Authorization": f"Basic {auth}"},
        )
        ready_resp.raise_for_status()
        ready_data = ready_resp.json()

        result = is_task_ready(ready_data, task_id)
        if result is not False:
            break

        attempt += 1

    # Step 3: Retrieve results
    logger.info("KFK task %s is ready. Retrieving results...", task_id)

    get_resp = await client.get(
        f"{kfk_base}/task_get/{task_id}",
        headers={"Authorization": f"Basic {auth}"},
    )
    get_resp.raise_for_status()
    get_data = get_resp.json()

    get_task = (get_data.get("tasks") or [None])[0]
    if get_task is None:
        raise ValueError("KFK task_get returned no tasks in response")

    status_code = get_task.get("status_code")
    if str(status_code) != "20000":
        msg = get_task.get("status_message", "unknown error")
        raise ValueError(
            f"KFK task_get failed with status {status_code}: {msg}"
        )

    return get_data


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

    Calls related_keywords, keyword_suggestions, and keywords_for_keywords
    endpoints concurrently. The first two are synchronous live calls; the
    third uses async task_post/poll/task_get. Saves raw JSON responses to
    outdir, then invokes merge_keywords for deterministic post-processing.

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
        'Fetching keywords for "%s" (market=%s, lang=%s, limit=%d)...',
        seed_keyword, market, language, limit,
    )

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)

    kfk_response: dict | None = None

    try:
        # Wrap KFK in a coroutine that catches errors for graceful degradation
        async def _kfk_with_fallback() -> dict | None:
            try:
                return await fetch_kfk(
                    seed_keyword,
                    language=language,
                    location_code=location_code,
                    base=base,
                    auth=auth,
                    client=client,
                )
            except Exception as exc:
                logger.warning(
                    "keywords_for_keywords failed (non-fatal): %s", exc,
                )
                return None

        # Call all three endpoints concurrently
        related_response, suggestions_response, kfk_response = (
            await asyncio.gather(
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
                _kfk_with_fallback(),
            )
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

    # Save KFK raw response if available
    if kfk_response is not None:
        kfk_path = out / "keywords-for-keywords-raw.json"
        kfk_path.write_text(
            json.dumps(kfk_response, indent=2), encoding="utf-8"
        )
        logger.info("Saved: %s", kfk_path)

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
            kfk_raw=kfk_response,
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
