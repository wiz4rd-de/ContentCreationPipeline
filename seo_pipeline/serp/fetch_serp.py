"""Async DataForSEO SERP workflow: task_post, poll tasks_ready, task_get.

Includes caching, exponential backoff, and a live-endpoint fallback.
Uses httpx.AsyncClient for all HTTP calls.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from seo_pipeline.utils.load_api_config import load_env
from seo_pipeline.utils.resolve_location import resolve_location
from seo_pipeline.utils.slugify import slugify

logger = logging.getLogger(__name__)

# --- Default polling parameters ---
INITIAL_DELAY_MS = 5000
BACKOFF_FACTOR = 1.5
MAX_DELAY_MS = 30000


# --- Pure functions ---


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
    ``{'ready': True, 'endpoint_advanced': str|None}`` if found.
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
                return {
                    "ready": True,
                    "endpoint_advanced": r.get("endpoint_advanced"),
                }

    return False


def calculate_backoff(
    attempt: int,
    *,
    initial_delay: float = INITIAL_DELAY_MS,
    factor: float = BACKOFF_FACTOR,
    max_delay: float = MAX_DELAY_MS,
) -> float:
    """Exponential backoff calculator.

    Args:
        attempt: zero-based attempt number
        initial_delay: base delay in milliseconds
        factor: exponential growth factor
        max_delay: ceiling in milliseconds

    Returns:
        Delay in milliseconds.
    """
    return min(initial_delay * (factor ** attempt), max_delay)


def check_cache(
    file_path: str | Path,
    keyword: str | None = None,
    max_age_days: int | None = None,
) -> dict[str, Any]:
    """Check whether a cached serp-raw.json file is valid and usable.

    Returns ``{'hit': True, 'data': dict}`` when usable,
    ``{'hit': False, 'reason': str}`` (and optionally ``'age_days'``)
    otherwise.
    """
    path = Path(file_path)

    if not path.exists():
        return {"hit": False, "reason": "file not found"}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"hit": False, "reason": "invalid JSON"}

    # Validate shape: tasks[0].result[0].items must exist and be non-empty
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or len(tasks) == 0:
        return {"hit": False, "reason": "missing or empty tasks array"}

    result = tasks[0].get("result")
    if not isinstance(result, list) or len(result) == 0:
        return {"hit": False, "reason": "missing or empty result array"}

    items = result[0].get("items")
    if not isinstance(items, list) or len(items) == 0:
        return {"hit": False, "reason": "missing or empty items array"}

    # Keyword mismatch check
    if keyword is not None:
        task_data = tasks[0].get("data") or {}
        cached_keyword = task_data.get("keyword")
        if cached_keyword != keyword:
            return {
                "hit": False,
                "reason": (
                    f'keyword mismatch: cached "{cached_keyword}",'
                    f' requested "{keyword}"'
                ),
            }

    # TTL validation
    if max_age_days is not None:
        raw_timestamp = data.get("_pipeline_fetched_at") or (
            result[0].get("datetime") if result else None
        )

        if raw_timestamp is not None:
            try:
                # Parse ISO or DataForSEO datetime format
                ts = raw_timestamp.replace(" +00:00", "+00:00")
                fetch_date = datetime.fromisoformat(ts)
                if fetch_date.tzinfo is None:
                    fetch_date = fetch_date.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                age_days = (now - fetch_date).total_seconds() / 86400
                if age_days > max_age_days:
                    return {
                        "hit": False,
                        "reason": "expired",
                        "age_days": int(age_days),
                    }
            except (ValueError, TypeError):
                # No parseable timestamp -- treat as valid (backward compat)
                pass

    return {"hit": True, "data": data}


def derive_outdir(keyword: str, base_dir: str | Path) -> str:
    """Derive output directory path from keyword and base directory.

    Uses today's date (YYYY-MM-DD) and slugified keyword.
    """
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    slug = slugify(keyword)
    return str(Path(base_dir) / f"{date_str}_{slug}")


def build_live_url(base: str) -> str:
    """Build the DataForSEO live/advanced endpoint URL."""
    return f"{base}/serp/google/organic/live/advanced"


def should_fallback(elapsed_ms: float, fallback_timeout_sec: float) -> bool:
    """Determine whether elapsed time exceeds the fallback threshold.

    Returns False when fallback_timeout_sec is 0 (disabled).
    """
    if fallback_timeout_sec <= 0:
        return False
    return elapsed_ms >= fallback_timeout_sec * 1000


def adjust_timeout(
    timeout: int, fallback_timeout: int, buffer: int = 30
) -> int:
    """Auto-raise timeout to accommodate fallback.

    Returns the adjusted timeout in seconds.
    """
    if fallback_timeout > 0 and timeout < fallback_timeout + buffer:
        return fallback_timeout + buffer
    return timeout


# --- Main async workflow ---


async def fetch_serp(
    keyword: str,
    market: str,
    language: str,
    *,
    outdir: str | None = None,
    depth: int = 10,
    timeout: int = 120,
    fallback_timeout: int = 300,
    force: bool = False,
    max_age: int = 7,
    env_path: str | None = None,
    base_dir: str | None = None,
    request_timeout: float = 30.0,
) -> dict:
    """Fetch SERP data via the DataForSEO async workflow.

    Workflow:
        1. Check cache (unless ``force=True``)
        2. POST task_post to create an async task
        3. Poll tasks_ready with exponential backoff
        4. GET task_get/advanced to retrieve results
        5. Fall back to live endpoint if polling times out

    Args:
        keyword: search query
        market: ISO 3166-1 alpha-2 country code
        language: ISO language code (e.g. 'de', 'en')
        outdir: output directory (auto-derived if not given)
        depth: number of SERP results to request
        timeout: total workflow timeout in seconds
        fallback_timeout: seconds before switching to live endpoint (0=disabled)
        force: bypass cache when True
        max_age: maximum cache age in days
        env_path: path to api.env file
        base_dir: parent directory for auto-derived outdir
        request_timeout: per-request timeout in seconds

    Returns:
        The raw SERP response dict (also saved to disk).

    Raises:
        ValueError: on API errors, timeouts, or invalid responses
        FileNotFoundError: if api.env is missing
    """
    # Adjust timeout to accommodate fallback
    timeout = adjust_timeout(timeout, fallback_timeout)

    # Auto-derive outdir
    if outdir is None:
        if base_dir is None:
            base_dir = str(
                Path(__file__).parent.parent.parent / "output"
            )
        outdir = derive_outdir(keyword, base_dir)

    # Cache check
    if not force:
        cache_path = Path(outdir) / "serp-raw.json"
        cached = check_cache(cache_path, keyword, max_age)
        if cached["hit"]:
            logger.info("Cache hit: %s", cache_path)
            return cached["data"]
        logger.info("No valid cache (%s), fetching from API...", cached["reason"])

    # Load credentials
    if env_path is None:
        env_path = str(
            Path(__file__).parent.parent.parent / "api.env"
        )
    creds = load_env(env_path)
    auth_header = f"Basic {creds['auth']}"
    api_base = creds["base"]

    # Resolve location
    location_code = resolve_location(market)

    # Ensure output directory exists
    os.makedirs(outdir, exist_ok=True)

    task_post_body = [
        {
            "keyword": keyword,
            "language_code": language,
            "location_code": location_code,
            "depth": depth,
        }
    ]

    headers = {
        "Authorization": auth_header,
        "Content-Type": "application/json; charset=utf-8",
    }

    async with httpx.AsyncClient(timeout=request_timeout) as client:
        # Step 1: Post task
        logger.info(
            'Posting SERP task for "%s" (market=%s, lang=%s, depth=%d)...',
            keyword, market, language, depth,
        )

        post_resp = await client.post(
            f"{api_base}/serp/google/organic/task_post",
            headers=headers,
            json=task_post_body,
        )
        post_resp.raise_for_status()
        post_data = post_resp.json()

        task_id = extract_task_id(post_data)
        logger.info("Task created: %s", task_id)

        # Step 2: Poll tasks_ready with exponential backoff
        timeout_ms = timeout * 1000
        start_time = _monotonic_ms()
        attempt = 0
        task_ready = False

        while not task_ready:
            elapsed = _monotonic_ms() - start_time

            if should_fallback(elapsed, fallback_timeout):
                logger.warning(
                    "Async task %s not ready after %ds. "
                    "Falling back to live endpoint...",
                    task_id, fallback_timeout,
                )
                break

            if elapsed >= timeout_ms:
                raise ValueError(
                    f"Task {task_id} timed out after {timeout} seconds. Status: pending"
                )

            delay = calculate_backoff(attempt)
            logger.info(
                "Waiting %.1fs before poll attempt %d...",
                delay / 1000, attempt + 1,
            )
            await asyncio.sleep(delay / 1000)

            logger.info("Polling for task %s... attempt %d", task_id, attempt + 1)

            ready_resp = await client.get(
                f"{api_base}/serp/google/organic/tasks_ready",
                headers={"Authorization": auth_header},
            )
            ready_resp.raise_for_status()
            ready_data = ready_resp.json()

            result = is_task_ready(ready_data, task_id)
            if result is not False:
                task_ready = True

            attempt += 1

        # Step 3: Retrieve results or fallback
        if not task_ready:
            # Live endpoint fallback
            logger.info("Calling live endpoint as fallback...")
            live_resp = await client.post(
                f"{api_base}/serp/google/organic/live/advanced",
                headers=headers,
                json=task_post_body,
            )
            live_resp.raise_for_status()
            live_data = live_resp.json()

            live_task = (live_data.get("tasks") or [None])[0]
            if live_task is None or live_task.get("status_code") != 20000:
                msg = (
                    live_task.get("status_message")
                    if live_task
                    else "no tasks in response"
                )
                raise ValueError(f"Live endpoint failed: {msg}")

            response_with_ts = {
                "_pipeline_fetched_at": datetime.now(timezone.utc).isoformat(),
                "_pipeline_source": "live_fallback",
                **live_data,
            }
            _save_raw(outdir, response_with_ts)
            return response_with_ts

        # Async task completed -- retrieve results
        logger.info("Task %s is ready. Retrieving results...", task_id)

        get_resp = await client.get(
            f"{api_base}/serp/google/organic/task_get/advanced/{task_id}",
            headers={"Authorization": auth_header},
        )
        get_resp.raise_for_status()
        get_data = get_resp.json()

        get_task = (get_data.get("tasks") or [None])[0]
        if get_task is None:
            raise ValueError("task_get returned no tasks in response")

        status_code = get_task.get("status_code")
        if status_code is None:
            raise ValueError("task_get returned no status_code")

        code_str = str(status_code)
        if code_str == "40401":
            raise ValueError(
                f"Task {task_id} not found (40401). The task may have expired."
            )
        if code_str == "40403":
            raise ValueError(
                f"Task {task_id} results expired (40403). "
                "Results are only available for 3 days."
            )
        if code_str != "20000":
            msg = get_task.get("status_message", "unknown error")
            raise ValueError(
                f"task_get failed with status {status_code}: {msg}"
            )

        response_with_ts = {
            "_pipeline_fetched_at": datetime.now(timezone.utc).isoformat(),
            "_pipeline_source": "async",
            **get_data,
        }
        _save_raw(outdir, response_with_ts)
        return response_with_ts


def _monotonic_ms() -> float:
    """Return monotonic clock time in milliseconds."""
    import time
    return time.monotonic() * 1000


def _save_raw(outdir: str, data: dict) -> None:
    """Write serp-raw.json to the output directory."""
    raw_path = Path(outdir) / "serp-raw.json"
    raw_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info("Saved: %s", raw_path)
