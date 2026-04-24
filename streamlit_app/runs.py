"""Past-runs directory scanner.

Pure helper module — intentionally has **no** Streamlit imports so it can be
unit-tested without the Streamlit runtime.

The pipeline writes each run into ``output/<YYYY-MM-DD>_<slug>/``. This module
scans that directory and returns a :class:`RunInfo` per recognized
subdirectory, with boolean flags indicating which of the five tracked
artifacts exist on disk.

Artifact naming references
--------------------------
* Brief: ``brief-<slug>.md`` (see :mod:`seo_pipeline.analysis.assemble_briefing_md`).
* Draft markdown: ``draft-<slug>.md`` (see :mod:`seo_pipeline.drafting.write_draft`).
* Draft docx: ``draft-<slug>.docx`` (see :func:`seo_pipeline.orchestrator._emit_draft_docx`).
* Fact-check report: ``fact-check-report.md`` (slug-less filename).
* ToV-check report: ``tov-check-report.md`` (slug-less filename).

The slug is derived from the directory name (everything after the first
underscore), which is the same convention used by
:func:`seo_pipeline.orchestrator.run_pipeline_core`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

# ``YYYY-MM-DD_slug`` — anchored so we don't match arbitrary dirs in ``output/``.
_RUN_DIRNAME_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})_(.+)$")


@dataclass(frozen=True)
class RunInfo:
    """Snapshot of a single pipeline run directory.

    Attributes
    ----------
    path:
        Absolute path to the run directory.
    date:
        Calendar date parsed from the directory name prefix.
    slug:
        Keyword slug (everything after ``YYYY-MM-DD_``).
    has_brief:
        Whether ``brief-<slug>.md`` exists.
    has_draft_md:
        Whether ``draft-<slug>.md`` exists.
    has_draft_docx:
        Whether ``draft-<slug>.docx`` exists.
    has_fact_check:
        Whether ``fact-check-report.md`` exists.
    has_tov_check:
        Whether ``tov-check-report.md`` exists.
    """

    path: Path
    date: date
    slug: str
    has_brief: bool
    has_draft_md: bool
    has_draft_docx: bool
    has_fact_check: bool
    has_tov_check: bool

    @property
    def dirname(self) -> str:
        """Return the directory's basename (``YYYY-MM-DD_<slug>``)."""
        return self.path.name

    @property
    def completion_flags(self) -> dict[str, bool]:
        """Return the five ``has_*`` flags as an ordered mapping.

        Convenient for rendering the badge row in the UI without having
        to hard-code the flag list in two places.
        """
        return {
            "brief": self.has_brief,
            "draft_md": self.has_draft_md,
            "draft_docx": self.has_draft_docx,
            "fact_check": self.has_fact_check,
            "tov_check": self.has_tov_check,
        }


def _parse_run_dirname(name: str) -> tuple[date, str] | None:
    """Return ``(date, slug)`` if ``name`` matches the run-dir convention.

    Returns ``None`` for any name that is not ``YYYY-MM-DD_<slug>`` or
    whose date component is not a real calendar date. This deliberately
    excludes ad-hoc directories like ``drafts/`` or backup copies with
    non-matching suffixes.
    """
    match = _RUN_DIRNAME_RE.match(name)
    if not match:
        return None
    year, month, day, slug = match.groups()
    try:
        parsed = date(int(year), int(month), int(day))
    except ValueError:
        return None
    if not slug:
        return None
    return parsed, slug


def _artifact_flags(run_dir: Path, slug: str) -> dict[str, bool]:
    """Check each tracked artifact and return a ``has_*`` flag dict."""
    return {
        "has_brief": (run_dir / f"brief-{slug}.md").is_file(),
        "has_draft_md": (run_dir / f"draft-{slug}.md").is_file(),
        "has_draft_docx": (run_dir / f"draft-{slug}.docx").is_file(),
        "has_fact_check": (run_dir / "fact-check-report.md").is_file(),
        "has_tov_check": (run_dir / "tov-check-report.md").is_file(),
    }


def list_runs(output_dir: Path | None = None) -> list[RunInfo]:
    """Scan ``output_dir`` and return one :class:`RunInfo` per run directory.

    Parameters
    ----------
    output_dir:
        Directory to scan. Defaults to ``Path.cwd() / "output"`` resolved at
        call time (so tests that ``chdir`` work without module reloads). The
        function is tolerant of a missing directory — it just returns an
        empty list.

    Returns
    -------
    list[RunInfo]
        One entry per subdirectory whose name matches
        ``YYYY-MM-DD_<slug>``. Sorted by ``(date descending, slug
        ascending)`` so the UI can render the newest run first without
        extra work; the secondary sort on slug is a deterministic
        tie-breaker for multiple runs on the same date.
    """
    base = output_dir if output_dir is not None else Path.cwd() / "output"
    if not base.is_dir():
        return []

    runs: list[RunInfo] = []
    for entry in base.iterdir():
        if not entry.is_dir():
            continue
        parsed = _parse_run_dirname(entry.name)
        if parsed is None:
            continue
        run_date, slug = parsed
        flags = _artifact_flags(entry, slug)
        runs.append(
            RunInfo(
                path=entry.resolve(),
                date=run_date,
                slug=slug,
                **flags,
            )
        )

    runs.sort(key=lambda r: (r.date, r.slug), reverse=False)
    # Secondary pass: reverse by date only (keeping slug ascending within a
    # date). ``sort(reverse=True)`` on the tuple would also reverse slug.
    runs.sort(key=lambda r: r.date, reverse=True)
    return runs


__all__ = ["RunInfo", "list_runs"]
