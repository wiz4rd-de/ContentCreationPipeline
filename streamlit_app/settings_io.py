"""Read/write helpers for ``api.env`` and live-applying values to ``os.environ``.

The authoritative list of keys comes from
:func:`seo_pipeline.llm.config.LLMConfig.from_env` plus the DataForSEO
credentials used by :mod:`seo_pipeline.utils.load_api_config` and
:mod:`seo_pipeline.utils.preflight`. Do not duplicate a divergent list.
"""

from __future__ import annotations

import os
from pathlib import Path

# Keys strictly required for the pipeline to run.
# Derived from LLMConfig.from_env() (LLM_PROVIDER, LLM_MODEL are non-optional and
# LLM_API_KEY is needed for all non-local providers) + DataForSEO creds used by
# seo_pipeline/utils/load_api_config.py and seo_pipeline/utils/preflight.py.
REQUIRED_KEYS: list[str] = [
    "LLM_PROVIDER",
    "LLM_MODEL",
    "LLM_API_KEY",
    "DATAFORSEO_AUTH",
    "DATAFORSEO_BASE",
]

# Optional keys that LLMConfig.from_env() also consults. Shown in the Settings
# form but not enforced by the first-run gate.
OPTIONAL_KEYS: list[str] = [
    "LLM_API_BASE",
    "LLM_TEMPERATURE",
    "LLM_MAX_TOKENS",
]

# All keys the Settings form manages.
ALL_KEYS: list[str] = REQUIRED_KEYS + OPTIONAL_KEYS

# Keys whose values are secrets and should be masked in the UI.
SECRET_KEYS: frozenset[str] = frozenset({"LLM_API_KEY", "DATAFORSEO_AUTH"})

_DEFAULT_PATH = Path.cwd() / "api.env"


def _default_path() -> Path:
    """Return the default ``api.env`` path.

    Resolved at call time (not import time) so tests that ``chdir`` or pass
    ``tmp_path`` work correctly without module reloads.
    """
    return Path.cwd() / "api.env"


def _strip_quotes(value: str) -> str:
    """Strip a single pair of matching surrounding quotes, if present."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def load_api_env(path: Path | None = None) -> dict[str, str]:
    """Parse ``KEY=VALUE`` lines from ``api.env``.

    Blank lines and ``#``-prefixed comments are skipped. Surrounding quotes
    on values are stripped. Missing files return an empty dict.

    Args:
        path: Path to the env file. Defaults to ``Path.cwd() / "api.env"``.

    Returns:
        Mapping of key to value for every non-comment, non-blank line that
        parses as ``KEY=VALUE``. Later duplicates overwrite earlier ones.
    """
    target = path if path is not None else _default_path()
    if not target.exists():
        return {}

    result: dict[str, str] = {}
    for raw_line in target.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        result[key] = _strip_quotes(value.strip())
    return result


def save_api_env(values: dict[str, str], path: Path | None = None) -> None:
    """Write ``values`` to ``api.env`` atomically.

    Existing comments and line ordering are preserved: each key already
    present in the file (even in a commented-out form like ``# KEY=...``) is
    replaced in place with an uncommented ``KEY=VALUE`` line. Keys not already
    in the file are appended at the end. Keys mapped to empty strings are
    still written so the file records the user's explicit choice.

    The write is atomic: contents go to a temp file in the same directory,
    which is then renamed over the target.
    """
    target = path if path is not None else _default_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    existing_lines: list[str] = []
    if target.exists():
        existing_lines = target.read_text(encoding="utf-8").splitlines()

    remaining = dict(values)
    out_lines: list[str] = []

    for raw_line in existing_lines:
        stripped = raw_line.strip()
        # Detect "KEY=" lines, including "# KEY=" style commented-out entries.
        candidate = stripped.lstrip("#").lstrip()
        if "=" in candidate:
            key = candidate.partition("=")[0].strip()
            if key in remaining:
                out_lines.append(f"{key}={remaining.pop(key)}")
                continue
        out_lines.append(raw_line)

    for key in list(remaining):
        out_lines.append(f"{key}={remaining.pop(key)}")

    content = "\n".join(out_lines)
    if not content.endswith("\n"):
        content += "\n"

    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(target)


def apply_to_process_env(values: dict[str, str]) -> None:
    """Mutate ``os.environ`` so the current process sees ``values`` immediately.

    Empty-string values are removed from the environment rather than set, so
    downstream ``os.getenv`` lookups behave as if the key is unset.
    """
    for key, value in values.items():
        if value == "":
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def missing_required(values: dict[str, str]) -> list[str]:
    """Return the subset of ``REQUIRED_KEYS`` missing or blank in ``values``."""
    return [k for k in REQUIRED_KEYS if not values.get(k, "").strip()]
