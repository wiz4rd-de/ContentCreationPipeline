"""Typer CLI for the SEO content pipeline.

Each subcommand wraps the corresponding pipeline module, preserving
the same argument interface as the existing argparse CLIs.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    name="seo-pipeline",
    help="SEO content creation pipeline CLI.",
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo("seo-pipeline 0.1.0")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """SEO content creation pipeline."""


# ---------------------------------------------------------------------------
# SERP subcommands
# ---------------------------------------------------------------------------


@app.command()
def fetch_serp(
    keyword: str = typer.Argument(..., help="Search keyword"),
    market: str = typer.Option("de", help="ISO country code"),
    language: str = typer.Option("de", help="Language code"),
    outdir: Optional[str] = typer.Option(None, help="Output directory"),
    depth: int = typer.Option(10, help="Number of SERP results to request"),
    timeout: int = typer.Option(120, help="Total workflow timeout in seconds"),
    force: bool = typer.Option(False, help="Bypass cache"),
    max_age: int = typer.Option(7, help="Maximum cache age in days"),
) -> None:
    """Fetch SERP data via the DataForSEO async workflow."""
    from seo_pipeline.serp.fetch_serp import fetch_serp as _fetch_serp

    result = asyncio.run(
        _fetch_serp(
            keyword, market, language,
            outdir=outdir, depth=depth, timeout=timeout,
            force=force, max_age=max_age,
        )
    )
    typer.echo(json.dumps(result, indent=2, ensure_ascii=False))


@app.command()
def process_serp(
    input_file: Optional[Path] = typer.Argument(
        None, help="Path to raw SERP JSON file",
    ),
    top: int = typer.Option(10, help="Number of top competitors (default: 10)"),
    output: Optional[Path] = typer.Option(None, help="Path to write output JSON"),
) -> None:
    """Extract structured data from raw DataForSEO SERP JSON."""
    from seo_pipeline.serp.process_serp import process_serp as _process_serp

    if input_file:
        raw = json.loads(input_file.read_text(encoding="utf-8"))
    else:
        raw = json.load(sys.stdin)

    result = _process_serp(raw, top_n=top)
    output_json = json.dumps(result, indent=2, ensure_ascii=False) + "\n"

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(output_json, encoding="utf-8")
        typer.echo(f"Wrote {output}", err=True)
    else:
        typer.echo(output_json, nl=False)


@app.command()
def assemble_competitors(
    serp_file: str = typer.Argument(..., help="Path to processed SERP JSON file"),
    pages_dir: str = typer.Argument(
        ..., help="Directory containing extracted page JSON files",
    ),
    date: Optional[str] = typer.Option(
        None, help="Analysis date (YYYY-MM-DD, default: today)",
    ),
    output: Optional[Path] = typer.Option(None, help="Path to write output JSON"),
) -> None:
    """Assemble competitor data skeleton from SERP + page extractor outputs."""
    from seo_pipeline.serp.assemble_competitors import (
        assemble_competitors as _assemble_competitors,
    )

    serp = json.loads(Path(serp_file).read_text(encoding="utf-8"))
    result = _assemble_competitors(serp, pages_dir, date=date)

    output_json = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(output_json, encoding="utf-8")
        typer.echo(f"Wrote {output}", err=True)
    else:
        typer.echo(output_json, nl=False)


# ---------------------------------------------------------------------------
# Extractor subcommands
# ---------------------------------------------------------------------------


@app.command()
def extract_page(
    url: Optional[str] = typer.Argument(None, help="URL to extract"),
    output: Optional[Path] = typer.Option(None, help="Path to write output JSON"),
) -> None:
    """Fetch a URL and extract structured page metadata."""
    from seo_pipeline.extractor.extract_page import extract_page as _extract_page

    if not url:
        typer.echo("Error: url is required", err=True)
        raise typer.Exit(code=1)

    result = _extract_page(url)
    output_json = json.dumps(result, indent=2, ensure_ascii=False) + "\n"

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(output_json, encoding="utf-8")
        typer.echo(f"Wrote {output}", err=True)
    else:
        typer.echo(output_json, nl=False)


# ---------------------------------------------------------------------------
# Keywords subcommands
# ---------------------------------------------------------------------------


@app.command()
def fetch_keywords(
    seed_keyword: str = typer.Argument(..., help="Seed keyword to expand"),
    market: str = typer.Option(..., help="ISO country code"),
    language: str = typer.Option(..., help="Language code"),
    outdir: str = typer.Option(..., help="Output directory"),
    limit: int = typer.Option(50, help="Max results per endpoint"),
) -> None:
    """Fetch keywords from DataForSEO endpoints."""
    from seo_pipeline.keywords.fetch_keywords import (
        fetch_keywords as _fetch_keywords,
    )

    env_path = str(Path(__file__).resolve().parent.parent.parent / "api.env")
    result = asyncio.run(
        _fetch_keywords(
            seed_keyword, market=market, language=language,
            outdir=outdir, env_path=env_path, limit=limit,
        )
    )
    typer.echo(result)


@app.command()
def extract_keywords(
    input_file: Path = typer.Argument(
        ..., help="Path to raw DataForSEO API response JSON",
    ),
    include_difficulty: bool = typer.Option(
        False, "--include-difficulty", help="Include keyword difficulty",
    ),
    output: Optional[Path] = typer.Option(None, help="Path to write output JSON"),
) -> None:
    """Extract keyword records from a DataForSEO Labs API response."""
    from seo_pipeline.keywords.extract_keywords import (
        extract_keywords as _extract_keywords,
    )

    raw = json.loads(input_file.read_text(encoding="utf-8"))
    result = _extract_keywords(raw, include_difficulty=include_difficulty)
    output_json = json.dumps(result, indent=2, ensure_ascii=False) + "\n"

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(output_json, encoding="utf-8")
        typer.echo(f"Wrote {output}", err=True)
    else:
        typer.echo(output_json, nl=False)


@app.command()
def merge_keywords(
    related: str = typer.Option(
        ..., help="Path to related_keywords raw JSON file",
    ),
    suggestions: str = typer.Option(
        ..., help="Path to keyword_suggestions raw JSON file",
    ),
    seed: str = typer.Option(..., help="Seed keyword to ensure inclusion"),
) -> None:
    """Merge and deduplicate keywords from DataForSEO API responses."""
    from seo_pipeline.keywords.merge_keywords import (
        merge_keywords as _merge_keywords,
    )

    related_raw = json.loads(Path(related).read_text(encoding="utf-8"))
    suggestions_raw = json.loads(Path(suggestions).read_text(encoding="utf-8"))
    result = _merge_keywords(related_raw, suggestions_raw, seed)
    typer.echo(json.dumps(result, indent=2, ensure_ascii=False))


@app.command()
def process_keywords(
    related: str = typer.Option(
        ..., help="Path to related_keywords raw JSON file",
    ),
    suggestions: str = typer.Option(
        ..., help="Path to keyword_suggestions raw JSON file",
    ),
    seed: str = typer.Option(..., help="Seed keyword"),
    volume: Optional[str] = typer.Option(
        None, help="Path to volume raw JSON file (optional)",
    ),
    brands: Optional[str] = typer.Option(
        None, help="Comma-separated brand list (optional)",
    ),
    output: Optional[Path] = typer.Option(
        None, help="Output file path (default: stdout)",
    ),
) -> None:
    """Process keywords with intent, Jaccard clustering, and scoring."""
    from seo_pipeline.keywords.process_keywords import (
        process_keywords as _process_keywords,
    )

    related_raw = json.loads(Path(related).read_text(encoding="utf-8"))
    suggestions_raw = json.loads(Path(suggestions).read_text(encoding="utf-8"))

    volume_raw = None
    if volume:
        volume_raw = json.loads(Path(volume).read_text(encoding="utf-8"))

    brands_list = None
    if brands:
        brands_list = [b.strip() for b in brands.split(",") if b.strip()]

    result = _process_keywords(
        related_raw, suggestions_raw, seed,
        volume_raw=volume_raw, brands=brands_list,
    )
    output_json = json.dumps(result, indent=2, ensure_ascii=False) + "\n"

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(output_json, encoding="utf-8")
        typer.echo(f"Wrote {output}", err=True)
    else:
        typer.echo(output_json, nl=False)


@app.command()
def filter_keywords(
    keywords: str = typer.Option(
        ..., help="Path to processed keywords JSON",
    ),
    serp: str = typer.Option(..., help="Path to processed SERP JSON"),
    seed: str = typer.Option(..., help="Seed keyword"),
    blocklist: Optional[str] = typer.Option(
        None, help="Path to custom blocklist JSON",
    ),
    brands: Optional[str] = typer.Option(
        None, help="Comma-separated brand list",
    ),
    output: Optional[Path] = typer.Option(
        None, help="Output file path (default: stdout)",
    ),
) -> None:
    """Filter keywords by blocklist, brand, and foreign-language criteria."""
    from seo_pipeline.keywords.filter_keywords import (
        filter_keywords as _filter_keywords,
    )

    keywords_data = json.loads(Path(keywords).read_text(encoding="utf-8"))
    serp_data = json.loads(Path(serp).read_text(encoding="utf-8"))

    result = _filter_keywords(
        keywords_data, serp_data, seed,
        blocklist_path=blocklist, brands=brands,
    )
    output_json = json.dumps(result, indent=2, ensure_ascii=False) + "\n"

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(output_json, encoding="utf-8")
        typer.echo(f"Wrote {output}", err=True)
    else:
        typer.echo(output_json, nl=False)


@app.command()
def prepare_strategist_data(
    serp: str = typer.Option(..., help="Path to processed SERP JSON"),
    keywords: str = typer.Option(..., help="Path to processed keywords JSON"),
    seed: str = typer.Option(..., help="Seed keyword"),
    competitor_kws: Optional[str] = typer.Option(
        None, "--competitor-kws", help="Path to competitor keywords JSON",
    ),
    output: Optional[Path] = typer.Option(
        None, help="Output file path (default: stdout)",
    ),
) -> None:
    """Prepare consolidated data for content strategist LLM."""
    from seo_pipeline.keywords.prepare_strategist_data import (
        prepare_strategist_data as _prepare_strategist_data,
    )

    serp_data = json.loads(Path(serp).read_text(encoding="utf-8"))
    keywords_data = json.loads(Path(keywords).read_text(encoding="utf-8"))

    comp_kws = None
    if competitor_kws:
        comp_kws = json.loads(Path(competitor_kws).read_text(encoding="utf-8"))

    result = _prepare_strategist_data(
        keywords_data, serp_data, seed, competitor_kws_data=comp_kws,
    )
    output_json = json.dumps(result, indent=2, ensure_ascii=False) + "\n"

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(output_json, encoding="utf-8")
        typer.echo(f"Wrote {output}", err=True)
    else:
        typer.echo(output_json, nl=False)


# ---------------------------------------------------------------------------
# Analysis subcommands
# ---------------------------------------------------------------------------


@app.command()
def analyze_content_topics(
    pages_dir: Path = typer.Option(
        ..., help="Directory with page JSON files",
    ),
    seed: str = typer.Option(..., help="Seed keyword to exclude"),
    language: str = typer.Option("de", help="Language code (default: de)"),
    output: Optional[Path] = typer.Option(
        None, help="Output file path (default: stdout)",
    ),
) -> None:
    """Analyze content topics from competitor pages."""
    from seo_pipeline.analysis.analyze_content_topics import (
        analyze_content_topics as _analyze_content_topics,
    )

    result = _analyze_content_topics(pages_dir, seed, language=language)
    output_json = json.dumps(
        result.model_dump(), indent=2, ensure_ascii=False,
    ) + "\n"

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(output_json, encoding="utf-8")
        typer.echo(f"Wrote {output}", err=True)
    else:
        typer.echo(output_json, nl=False)


@app.command()
def analyze_page_structure(
    pages_dir: Path = typer.Option(
        ..., help="Directory with page JSON files",
    ),
    output: Optional[Path] = typer.Option(
        None, help="Output file path (default: stdout)",
    ),
) -> None:
    """Analyze page structure from competitor pages."""
    from seo_pipeline.analysis.analyze_page_structure import (
        analyze_page_structure as _analyze_page_structure,
    )

    result = _analyze_page_structure(pages_dir)
    output_json = json.dumps(
        result.model_dump(), indent=2, ensure_ascii=False,
    ) + "\n"

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(output_json, encoding="utf-8")
        typer.echo(f"Wrote {output}", err=True)
    else:
        typer.echo(output_json, nl=False)


@app.command()
def compute_entity_prominence(
    entities: Path = typer.Option(
        ..., help="Path to entity clusters JSON file",
    ),
    pages_dir: Path = typer.Option(
        ..., help="Directory with page JSON files",
    ),
    output: Optional[Path] = typer.Option(
        None, help="Output file path (default: stdout)",
    ),
) -> None:
    """Compute entity prominence from synonym matches."""
    from seo_pipeline.analysis.compute_entity_prominence import (
        compute_entity_prominence as _compute_entity_prominence,
    )

    result = _compute_entity_prominence(entities, pages_dir)
    output_json = json.dumps(
        result.model_dump(), indent=2, ensure_ascii=False,
    ) + "\n"

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(output_json, encoding="utf-8")
        typer.echo(f"Wrote {output}", err=True)
    else:
        typer.echo(output_json, nl=False)


@app.command()
def extract_claims(
    draft: str = typer.Option(..., help="Path to the draft markdown file"),
    output: Optional[Path] = typer.Option(
        None, help="Write JSON to this file",
    ),
) -> None:
    """Extract factual claims from draft markdown."""
    from seo_pipeline.analysis.extract_claims import (
        extract_claims as _extract_claims,
    )

    result = _extract_claims(draft)
    output_json = json.dumps(
        result.model_dump(), indent=2, ensure_ascii=False,
    ) + "\n"

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(output_json, encoding="utf-8")
        typer.echo(f"Wrote {output}", err=True)
    else:
        typer.echo(output_json, nl=False)


@app.command()
def fact_check(
    draft: str = typer.Option(
        ..., help="Path to the draft markdown file",
    ),
    dir: Optional[Path] = typer.Option(
        None, help="Output directory (defaults to draft's parent)",
    ),
) -> None:
    """Run full fact-check pipeline on a draft."""
    from seo_pipeline.analysis.fact_check import (
        fact_check as _fact_check,
    )
    from seo_pipeline.llm.config import LLMConfig
    from seo_pipeline.utils.load_api_config import load_env as _load_env

    out_dir = dir or Path(draft).parent
    env_path = str(
        Path(__file__).resolve().parent.parent.parent / "api.env"
    )
    api_cfg = _load_env(env_path)
    llm_cfg = LLMConfig.from_env()
    result = _fact_check(
        str(draft), str(out_dir), llm_cfg, api_cfg,
    )
    output_json = (
        json.dumps(
            result.model_dump(), indent=2, ensure_ascii=False,
        )
        + "\n"
    )
    typer.echo(output_json, nl=False)


@app.command()
def score_draft_wdfidf(
    draft: Path = typer.Option(..., help="Path to draft text file"),
    pages_dir: Path = typer.Option(
        ..., help="Directory with competitor page JSON files",
    ),
    language: str = typer.Option("de", help="Language code (default: de)"),
    threshold: float = typer.Option(
        0.1, help="Delta threshold for signal assignment (default: 0.1)",
    ),
    output: Optional[Path] = typer.Option(
        None, help="Output file path (default: stdout)",
    ),
) -> None:
    """Score a draft against competitor pages using WDF*IDF."""
    from seo_pipeline.analysis.score_draft_wdfidf import (
        score_draft_wdfidf as _score_draft_wdfidf,
    )

    result = _score_draft_wdfidf(draft, pages_dir, language=language,
                                  threshold=threshold)
    output_json = json.dumps(
        result.model_dump(), indent=2, ensure_ascii=False,
    ) + "\n"

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(output_json, encoding="utf-8")
        typer.echo(f"Wrote {output}", err=True)
    else:
        typer.echo(output_json, nl=False)


@app.command()
def assemble_briefing_data(
    dir: Path = typer.Option(..., help="Output directory with analysis JSON files"),
    market: Optional[str] = typer.Option(None, help="Market identifier"),
    language: Optional[str] = typer.Option(None, help="Language code"),
    user_domain: Optional[str] = typer.Option(None, help="User domain"),
    business_context: Optional[str] = typer.Option(None, help="Business context"),
    output: Optional[Path] = typer.Option(
        None, help="Output file path (default: <dir>/briefing-data.json)",
    ),
) -> None:
    """Assemble briefing data from pipeline outputs."""
    from seo_pipeline.analysis.assemble_briefing_data import (
        _normalize_tree,
    )  # noqa: I001
    from seo_pipeline.analysis.assemble_briefing_data import (
        assemble_briefing_data as _assemble_briefing_data,
    )

    result = _assemble_briefing_data(
        dir, market=market, language=language,
        user_domain=user_domain, business_context=business_context,
    )
    output_dict = _normalize_tree(result)
    output_json = json.dumps(output_dict, indent=2, ensure_ascii=False) + "\n"

    output_path = output or (dir / "briefing-data.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output_json, encoding="utf-8")
    typer.echo("Wrote briefing-data.json", err=True)


@app.command()
def merge_qualitative(
    dir: str = typer.Option(..., help="Output directory with briefing-data.json"),
) -> None:
    """Merge qualitative.json fields into briefing-data.json."""
    from seo_pipeline.analysis.merge_qualitative import (
        merge_qualitative as _merge_qualitative,
    )

    _merge_qualitative(dir)


@app.command()
def summarize_briefing(
    file: str = typer.Option(..., help="Path to briefing-data.json"),
) -> None:
    """Print a compact summary of briefing-data.json."""
    from seo_pipeline.analysis.summarize_briefing import (
        summarize_briefing as _summarize_briefing,
    )

    summary = _summarize_briefing(file)
    typer.echo(summary)


@app.command()
def fill_qualitative(
    dir: str = typer.Option(..., help="Output directory with briefing-data.json"),
) -> None:
    """Fill qualitative analysis fields via LLM."""
    from seo_pipeline.analysis.fill_qualitative import (
        fill_qualitative as _fill_qualitative,
    )

    _fill_qualitative(dir)


@app.command()
def assemble_briefing_md(
    dir: str = typer.Option(..., help="Output directory with briefing-data.json"),
    template: Optional[str] = typer.Option(
        None, help="Path to a content template file",
    ),
    tov: Optional[str] = typer.Option(
        None, help="Path to a tone-of-voice guidelines file",
    ),
) -> None:
    """Assemble final briefing markdown via LLM."""
    from seo_pipeline.analysis.assemble_briefing_md import (
        assemble_briefing_md as _assemble_briefing_md,
    )

    _assemble_briefing_md(dir, template_path=template, tov_path=tov)


# ---------------------------------------------------------------------------
# Drafting subcommands
# ---------------------------------------------------------------------------


@app.command()
def write_draft(
    brief: str = typer.Option(
        ..., help="Path to the briefing markdown file",
    ),
    tov: Optional[str] = typer.Option(
        None, help="Path to a tone-of-voice guidelines file",
    ),
    instructions: Optional[str] = typer.Option(
        None, help="Special instructions for the draft",
    ),
) -> None:
    """Generate an article draft from a content briefing."""
    from seo_pipeline.drafting.write_draft import write_draft as _write_draft

    _write_draft(brief, tov_path=tov, instructions=instructions)


# ---------------------------------------------------------------------------
# run-pipeline orchestrator
# ---------------------------------------------------------------------------


@app.command()
def run_pipeline(
    keyword: str = typer.Argument(..., help="Seed keyword"),
    location: str = typer.Option(
        "de", help="Market key (e.g. de, us, gb) — passed to resolve_location()",
    ),
    language: str = typer.Option("de", help="Language code"),
    output_dir: Optional[Path] = typer.Option(
        None, help="Output directory (default: ./output/<slug>/)",
    ),
    skip_fetch: bool = typer.Option(
        False, help="Skip network calls and use cached data",
    ),
    llm_provider: Optional[str] = typer.Option(
        None, help="LLM provider (e.g. anthropic)",
    ),
    llm_model: Optional[str] = typer.Option(
        None, help="LLM model name",
    ),
    tov: Optional[Path] = typer.Option(
        None,
        help="Path to tone-of-voice file (passed to briefing-md and write-draft)",
        exists=True, file_okay=True, dir_okay=False,
    ),
    template: Optional[Path] = typer.Option(
        None, help="Path to briefing template file (passed to assemble-briefing-md)",
        exists=True, file_okay=True, dir_okay=False,
    ),
) -> None:
    """Run the full SEO content pipeline end-to-end for a keyword."""
    import os
    from datetime import datetime, timezone

    from seo_pipeline.utils.slugify import slugify

    slug = slugify(keyword)
    date_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    out_dir = output_dir or Path("output") / f"{date_str}_{slug}"
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pages_dir = out_dir / "pages"
    pages_dir.mkdir(exist_ok=True)

    # Set LLM env vars if provided
    if llm_provider:
        os.environ["LLM_PROVIDER"] = llm_provider
    if llm_model:
        os.environ["LLM_MODEL"] = llm_model

    _log = lambda msg: typer.echo(msg, err=True)  # noqa: E731

    # --- Stage 1: Fetch SERP ---
    from seo_pipeline.serp.fetch_serp import fetch_serp as _fetch_serp

    if not skip_fetch:
        _log("Stage 1/11: Fetching SERP data...")
        asyncio.run(
            _fetch_serp(
                keyword, location, language,
                outdir=str(out_dir),
            )
        )
    else:
        _log("Stage 1/11: Skipping SERP fetch (cached)...")
        serp_raw_path = out_dir / "serp-raw.json"
        if not serp_raw_path.exists():
            typer.echo(f"Error: cached serp-raw.json not found at {serp_raw_path}",
                       err=True)
            raise typer.Exit(code=1)

    # --- Stage 2: Process SERP ---
    from seo_pipeline.serp.process_serp import process_serp as _process_serp

    _log("Stage 2/11: Processing SERP data...")
    serp_raw_path = out_dir / "serp-raw.json"
    serp_raw = json.loads(serp_raw_path.read_text(encoding="utf-8"))
    serp_processed = _process_serp(serp_raw, top_n=10)
    serp_processed_path = out_dir / "serp-processed.json"
    serp_processed_path.write_text(
        json.dumps(serp_processed, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # --- Stage 3: Extract pages ---
    from seo_pipeline.extractor.extract_page import extract_page as _extract_page

    competitors = serp_processed.get("competitors", [])
    _log(f"Stage 3/11: Extracting {len(competitors)} competitor pages...")
    for comp in competitors:
        comp_url = comp.get("url")
        if not comp_url:
            continue
        domain = comp.get("domain", "unknown")
        page_path = pages_dir / f"{domain}.json"
        if skip_fetch and page_path.exists():
            continue
        page_data = _extract_page(comp_url)
        page_path.write_text(
            json.dumps(page_data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    # --- Stage 4: Fetch & process keywords ---
    from seo_pipeline.keywords.fetch_keywords import (
        fetch_keywords as _fetch_keywords,
    )

    if not skip_fetch:
        _log("Stage 4/11: Fetching keywords...")
        env_path = str(Path(__file__).resolve().parent.parent.parent / "api.env")
        asyncio.run(
            _fetch_keywords(
                keyword, market=location, language=language,
                outdir=str(out_dir), env_path=env_path,
            )
        )
    else:
        _log("Stage 4/11: Skipping keyword fetch (cached)...")

    # --- Stage 5: Process keywords ---
    from seo_pipeline.keywords.process_keywords import (
        process_keywords as _process_keywords,
    )

    _log("Stage 5/11: Processing keywords...")
    related_path = out_dir / "keywords-related-raw.json"
    suggestions_path = out_dir / "keywords-suggestions-raw.json"
    if related_path.exists() and suggestions_path.exists():
        related_raw = json.loads(related_path.read_text(encoding="utf-8"))
        suggestions_raw = json.loads(suggestions_path.read_text(encoding="utf-8"))
        kw_processed = _process_keywords(related_raw, suggestions_raw, keyword)
        kw_processed_path = out_dir / "keywords-processed.json"
        kw_processed_path.write_text(
            json.dumps(kw_processed, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    else:
        _log("Warning: keyword files not found, skipping processing")
        kw_processed = {"clusters": []}

    # --- Stage 6: Filter keywords ---
    from seo_pipeline.keywords.filter_keywords import (
        filter_keywords as _filter_keywords,
    )

    _log("Stage 6/11: Filtering keywords...")
    kw_filtered = _filter_keywords(kw_processed, serp_processed, keyword)
    kw_filtered_path = out_dir / "keywords-filtered.json"
    kw_filtered_path.write_text(
        json.dumps(kw_filtered, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # --- Stage 7: Analysis ---
    from seo_pipeline.analysis.analyze_content_topics import (
        analyze_content_topics as _analyze_content_topics,
    )
    from seo_pipeline.analysis.analyze_page_structure import (
        analyze_page_structure as _analyze_page_structure,
    )

    _log("Stage 7/11: Running content analysis...")
    topics = _analyze_content_topics(pages_dir, keyword, language=language)
    topics_path = out_dir / "content-topics.json"
    topics_path.write_text(
        json.dumps(topics.model_dump(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    structure = _analyze_page_structure(pages_dir)
    structure_path = out_dir / "page-structure.json"
    structure_path.write_text(
        json.dumps(structure.model_dump(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # --- Stage 8: Assemble briefing data ---
    from seo_pipeline.analysis.assemble_briefing_data import (
        _normalize_tree,
    )  # noqa: I001
    from seo_pipeline.analysis.assemble_briefing_data import (
        assemble_briefing_data as _assemble_briefing_data,
    )

    _log("Stage 8/11: Assembling briefing data...")
    briefing = _assemble_briefing_data(
        out_dir, market=location, language=language,
    )
    briefing_dict = _normalize_tree(briefing)
    briefing_path = out_dir / "briefing-data.json"
    briefing_path.write_text(
        json.dumps(briefing_dict, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # --- Stage 9: Summarize briefing ---
    from seo_pipeline.analysis.summarize_briefing import (
        summarize_briefing as _summarize_briefing,
    )

    _log("Stage 9/11: Summarizing briefing...")
    summary = _summarize_briefing(str(briefing_path))
    _log(summary)

    # --- Stage 10: LLM stages (qualitative + briefing md + draft) ---
    _log(
        "Stage 10/11: LLM stages "
        "(fill-qualitative, assemble-briefing-md, write-draft)..."
    )

    from seo_pipeline.llm.config import LLMConfig

    try:
        LLMConfig.from_env()
        llm_configured = True
    except ValueError:
        llm_configured = False

    if llm_configured:
        from seo_pipeline.analysis.assemble_briefing_md import (
            assemble_briefing_md as _assemble_briefing_md,
        )
        from seo_pipeline.analysis.fill_qualitative import (
            fill_qualitative as _fill_qualitative,
        )
        from seo_pipeline.analysis.merge_qualitative import (
            merge_qualitative as _merge_qualitative,
        )
        from seo_pipeline.drafting.write_draft import write_draft as _write_draft

        _fill_qualitative(str(out_dir))
        _merge_qualitative(str(out_dir))
        _assemble_briefing_md(
            str(out_dir),
            template_path=str(template) if template else None,
            tov_path=str(tov) if tov else None,
        )
        brief_path = out_dir / f"brief-{slug}.md"
        _write_draft(
            str(brief_path),
            tov_path=str(tov) if tov else None,
        )

        # --- Stage 11: Fact-check draft ---
        _log("Stage 11/11: Fact-checking draft...")
        from seo_pipeline.analysis.fact_check import (
            fact_check as _fact_check,
        )
        from seo_pipeline.utils.load_api_config import (
            load_env as _load_env,
        )

        env_path_str = str(
            Path(__file__).resolve().parent.parent.parent / "api.env"
        )
        try:
            api_cfg = _load_env(env_path_str)
            draft_path = out_dir / f"draft-{slug}.md"
            if draft_path.exists():
                _fact_check(
                    str(draft_path),
                    str(out_dir),
                    LLMConfig.from_env(),
                    api_cfg,
                )
            else:
                _log(
                    "  Warning: draft not found, "
                    "skipping fact-check"
                )
        except Exception as exc:
            _log(
                f"  Warning: fact-check failed ({exc}), "
                "continuing..."
            )
    else:
        _log("  LLM not configured — run these stages manually:")
        tov_flag = f" --tov {tov}" if tov else ""
        template_flag = f" --template {template}" if template else ""
        _log(f"  uv run seo-pipeline fill-qualitative --dir {out_dir}")
        _log(f"  uv run seo-pipeline merge-qualitative --dir {out_dir}")
        _log(
            f"  uv run seo-pipeline assemble-briefing-md"
            f" --dir {out_dir}{template_flag}{tov_flag}"
        )
        _log(
            f"  uv run seo-pipeline write-draft"
            f" --brief {out_dir}/brief-{slug}.md{tov_flag}"
        )
        _log(
            f"  uv run seo-pipeline fact-check"
            f" --draft {out_dir}/draft-{slug}.md"
        )

    _log(f"\nPipeline complete. Output directory: {out_dir}")
