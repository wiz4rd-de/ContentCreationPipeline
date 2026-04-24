"""Static signature checks for the individual-stage Streamlit pages.

The stage pages (02–07) import directly from ``seo_pipeline.*`` and invoke
stage functions with keyword arguments. A signature drift in the pipeline
would otherwise only surface when a user clicks the button. These tests
verify the pages' Python source parses, each page file exists, and each
stage function is importable with the call pattern the pages rely on.

We keep these tests cheap: they import modules and call :func:`inspect.signature`
but never fire a live LLM or HTTP call.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

PAGES_DIR = (
    Path(__file__).resolve().parent.parent
    / "streamlit_app"
    / "pages"
)

EXPECTED_PAGES = [
    "02_keyword_research.py",
    "03_competitor_analysis.py",
    "04_briefing.py",
    "05_draft.py",
    "06_fact_check.py",
    "07_tov_check.py",
]


def test_all_six_pages_exist() -> None:
    missing = [name for name in EXPECTED_PAGES if not (PAGES_DIR / name).is_file()]
    assert not missing, f"Missing stage pages: {missing}"


def test_all_pages_parse_as_python() -> None:
    """Each page must be syntactically valid Python so Streamlit can load it."""
    for name in EXPECTED_PAGES:
        path = PAGES_DIR / name
        source = path.read_text(encoding="utf-8")
        # Will raise SyntaxError if the page has a typo.
        ast.parse(source, filename=str(path))


def test_fetch_keywords_accepts_page_kwargs() -> None:
    """Page 02 calls ``fetch_keywords`` with keyword-only args."""
    from seo_pipeline.keywords.fetch_keywords import fetch_keywords

    sig = inspect.signature(fetch_keywords)
    params = sig.parameters
    assert "seed_keyword" in params
    for kwarg in ("market", "language", "outdir", "env_path"):
        assert kwarg in params, f"fetch_keywords missing kwarg {kwarg}"
        assert params[kwarg].kind is inspect.Parameter.KEYWORD_ONLY


def test_process_keywords_accepts_page_kwargs() -> None:
    from seo_pipeline.keywords.process_keywords import process_keywords

    sig = inspect.signature(process_keywords)
    params = sig.parameters
    for name in ("related_raw", "suggestions_raw", "seed"):
        assert name in params
    assert "kfk_raw" in params


def test_filter_keywords_accepts_page_args() -> None:
    from seo_pipeline.keywords.filter_keywords import filter_keywords

    sig = inspect.signature(filter_keywords)
    params = sig.parameters
    for name in ("keywords_data", "serp_data", "seed_keyword"):
        assert name in params


def test_fetch_serp_accepts_page_kwargs() -> None:
    from seo_pipeline.serp.fetch_serp import fetch_serp

    sig = inspect.signature(fetch_serp)
    params = sig.parameters
    assert "keyword" in params
    assert "market" in params
    assert "language" in params
    assert "outdir" in params


def test_process_serp_accepts_page_args() -> None:
    from seo_pipeline.serp.process_serp import process_serp

    sig = inspect.signature(process_serp)
    params = sig.parameters
    # Page calls process_serp(raw, top_n=10)
    assert "top_n" in params or any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()
    )


def test_analyze_functions_accept_page_args() -> None:
    from seo_pipeline.analysis.analyze_content_topics import (
        analyze_content_topics,
    )
    from seo_pipeline.analysis.analyze_page_structure import (
        analyze_page_structure,
    )

    topics_sig = inspect.signature(analyze_content_topics)
    assert "pages_dir" in topics_sig.parameters
    assert "seed" in topics_sig.parameters
    assert "language" in topics_sig.parameters

    structure_sig = inspect.signature(analyze_page_structure)
    assert "pages_dir" in structure_sig.parameters


def test_briefing_functions_accept_page_args() -> None:
    from seo_pipeline.analysis.assemble_briefing_data import (
        assemble_briefing_data,
    )
    from seo_pipeline.analysis.assemble_briefing_md import assemble_briefing_md
    from seo_pipeline.analysis.fill_qualitative import fill_qualitative

    assemble_data_sig = inspect.signature(assemble_briefing_data)
    for kwarg in (
        "market", "language", "user_domain", "business_context",
    ):
        assert kwarg in assemble_data_sig.parameters

    fill_sig = inspect.signature(fill_qualitative)
    assert "dir_path" in fill_sig.parameters

    md_sig = inspect.signature(assemble_briefing_md)
    for name in ("dir_path", "template_path", "tov_path"):
        assert name in md_sig.parameters


def test_write_draft_accepts_page_args() -> None:
    from seo_pipeline.drafting.write_draft import write_draft

    sig = inspect.signature(write_draft)
    for name in ("brief_path", "tov_path", "instructions"):
        assert name in sig.parameters


def test_fact_check_accepts_page_args() -> None:
    from seo_pipeline.analysis.fact_check import fact_check

    sig = inspect.signature(fact_check)
    for name in ("draft_path", "out_dir", "llm_config", "api_config"):
        assert name in sig.parameters


def test_tov_check_accepts_page_args() -> None:
    from seo_pipeline.analysis.tov_check import tov_check

    sig = inspect.signature(tov_check)
    for name in ("draft_path", "out_dir", "llm_config", "tov_path"):
        assert name in sig.parameters


def test_each_page_imports_its_stage_function_directly() -> None:
    """No page may shell out — all stage calls are direct Python imports."""
    forbidden_substrings = ("subprocess", "os.system", "uv run", "seo-pipeline ")

    for name in EXPECTED_PAGES:
        source = (PAGES_DIR / name).read_text(encoding="utf-8")
        for needle in forbidden_substrings:
            assert needle not in source, (
                f"Page {name} appears to shell out (`{needle}` found). "
                "Stage pages must call stage functions directly."
            )


def test_each_page_has_gate_check() -> None:
    """Every stage page must re-check the gate as defense-in-depth."""
    for name in EXPECTED_PAGES:
        source = (PAGES_DIR / name).read_text(encoding="utf-8")
        assert "gate_open" in source, f"Page {name} missing gate_open import/use"
        assert "render_closed_gate" in source, (
            f"Page {name} missing render_closed_gate import/use"
        )
