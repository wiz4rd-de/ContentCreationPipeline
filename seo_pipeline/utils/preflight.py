"""Pre-flight validation for pipeline runs.

Checks credentials, api.env, and dependencies before any pipeline script runs.
"""

import re
import sys
from pathlib import Path
from typing import NamedTuple


class CheckResult(NamedTuple):
    """Result of a single pre-flight check."""

    ok: bool
    message: str


def check_api_env(project_root: str) -> CheckResult:
    """Check that api.env exists and is readable at the given project root.

    Args:
        project_root: Absolute path to the project root directory.

    Returns:
        A CheckResult indicating success or failure.
    """
    env_path = Path(project_root) / "api.env"
    if env_path.exists():
        return CheckResult(ok=True, message="api.env exists")
    return CheckResult(
        ok=False,
        message="api.env not found. Copy the template: cp api.env.example api.env",
    )


def parse_env_content(content: str) -> dict[str, str]:
    """Parse the raw content of an api.env file into a key/value map.

    Skips empty lines and comment lines.

    Args:
        content: Raw file content.

    Returns:
        A dictionary mapping env variable names to their values.
    """
    env = {}
    for line in content.split("\n"):
        trimmed = line.strip()
        # Skip empty lines and comments
        if not trimmed or trimmed.startswith("#"):
            continue
        # Split on first = only
        eq_idx = trimmed.find("=")
        if eq_idx == -1:
            continue
        key = trimmed[:eq_idx]
        value = trimmed[eq_idx + 1 :]
        env[key] = value
    return env


def check_auth(env: dict[str, str]) -> CheckResult:
    """Check that DATAFORSEO_AUTH is present and non-empty in the parsed env map.

    Args:
        env: Parsed env key/value map.

    Returns:
        A CheckResult indicating success or failure.
    """
    value = env.get("DATAFORSEO_AUTH")
    if value and value != "":
        return CheckResult(ok=True, message="DATAFORSEO_AUTH is set")
    return CheckResult(
        ok=False,
        message=(
            "DATAFORSEO_AUTH is not set in api.env. "
            "See api.env.example for the format."
        ),
    )


def check_base64(value: str) -> bool:
    """Check that a value looks like valid base64.

    Uses a regex to catch common mistakes like leaving the placeholder or pasting
    raw login:password.

    Args:
        value: The value to validate.

    Returns:
        True if the value looks like valid base64, False otherwise.
    """
    if not isinstance(value, str) or value == "":
        return False
    return bool(re.match(r"^[A-Za-z0-9+/]+=*$", value))


def check_auth_format(env: dict[str, str]) -> CheckResult:
    """Check that DATAFORSEO_AUTH in the parsed env map appears to be valid base64.

    Args:
        env: Parsed env key/value map.

    Returns:
        A CheckResult indicating success or failure.
    """
    value = env.get("DATAFORSEO_AUTH")
    if check_base64(value or ""):
        return CheckResult(ok=True, message="DATAFORSEO_AUTH is valid base64 format")
    return CheckResult(
        ok=False,
        message=(
            "DATAFORSEO_AUTH does not look like valid base64. "
            "Generate it with: echo -n 'login:password' | base64"
        ),
    )


def check_base(env: dict[str, str]) -> CheckResult:
    """Check that DATAFORSEO_BASE is present and non-empty in the parsed env map.

    Args:
        env: Parsed env key/value map.

    Returns:
        A CheckResult indicating success or failure.
    """
    value = env.get("DATAFORSEO_BASE")
    if value and value != "":
        return CheckResult(ok=True, message="DATAFORSEO_BASE is set")
    return CheckResult(
        ok=False,
        message="DATAFORSEO_BASE is not set in api.env. Expected: https://api.dataforseo.com/v3",
    )


def run_preflight(project_root: str) -> bool:
    """Run all pre-flight checks and report results to stderr.

    Continues checking even after a failure to report all problems at once.

    Args:
        project_root: Absolute path to the project root.

    Returns:
        True if all checks passed, False if any failed.
    """
    all_passed = True

    def report(result: CheckResult) -> None:
        """Report a check result to stderr."""
        nonlocal all_passed
        prefix = "[OK]" if result.ok else "[FAIL]"
        sys.stderr.write(f"{prefix} {result.message}\n")
        if not result.ok:
            all_passed = False

    # Check 1: api.env exists
    api_env_result = check_api_env(project_root)
    report(api_env_result)

    if api_env_result.ok:
        # Only parse env content if file exists — otherwise checks 2-4 are meaningless
        env_path = Path(project_root) / "api.env"
        content = env_path.read_text(encoding="utf-8")
        env = parse_env_content(content)

        # Check 2: DATAFORSEO_AUTH is set
        auth_result = check_auth(env)
        report(auth_result)

        # Check 3: DATAFORSEO_AUTH appears to be valid base64
        # Run regardless of check 2 so all failures are reported at once
        report(check_auth_format(env))

        # Check 4: DATAFORSEO_BASE is set
        report(check_base(env))

    return all_passed


if __name__ == "__main__":
    # Calculate project root: this file is at seo_pipeline/utils/preflight.py
    # So project root is 3 levels up
    this_file = Path(__file__)
    project_root = str(this_file.parent.parent.parent)

    passed = run_preflight(project_root)
    if passed:
        sys.stderr.write("All pre-flight checks passed.\n")
        sys.exit(0)
    else:
        sys.exit(1)
