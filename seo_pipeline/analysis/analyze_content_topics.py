"""Deterministic content topic analyzer.

Extracts n-gram term frequencies with IDF boosting, computes section weight
analysis, and clusters similar headings using Jaccard overlap.

Usage:
    python -m seo_pipeline.analysis.analyze_content_topics \
        --pages-dir <pages/> --seed <keyword> [--language de] [--output path]
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import Counter, defaultdict
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from seo_pipeline.models.analysis import (
    ContentFormatSignals,
    ContentTopics,
    EntityCandidate,
    ProofKeyword,
    SectionWeight,
)
from seo_pipeline.utils.math import js_round, normalize_number
from seo_pipeline.utils.tokenizer import load_stopword_set, remove_stopwords, tokenize

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IDF_MIDPOINT = 10.0
MIN_WORD_COUNT = 200
BLOCK_HEADING_RE = re.compile(
    r"why have i been blocked|access denied|403 forbidden|please verify"
    r"|checking your browser|just a moment|enable javascript and cookies"
    r"|attention required",
    re.IGNORECASE,
)
FAQ_HEADING_RE = re.compile(
    r"\b(faq|fragen|haeufig|frequently\s+asked|h.ufig)\b", re.IGNORECASE
)

# Regex for heading normalization: keep lowercase letters, German umlauts,
# extended Latin, and whitespace.
_HEADING_NORM_RE = re.compile(r"[^a-z\u00e4\u00f6\u00fc\u00df\u00e0-\u00ff\s]+")


# ---------------------------------------------------------------------------
# IDF helpers
# ---------------------------------------------------------------------------


def _load_idf_table(language: str) -> dict[str, float] | None:
    """Load the IDF reference corpus for the given language."""
    if language != "de":
        return None
    try:
        idf_path = resources.files("seo_pipeline").joinpath("data/idf_de.json")
        raw = json.loads(idf_path.read_text(encoding="utf-8"))
        return raw.get("idf") or None
    except Exception:
        return None


def _idf_boost(term: str, idf_table: dict[str, float] | None) -> float:
    """Return the IDF boost multiplier for a term.

    Terms absent from the table get a neutral 1.0.
    """
    if idf_table is None:
        return 1.0
    val = idf_table.get(term)
    if val is None:
        return 1.0
    return js_round(val / IDF_MIDPOINT * 1000) / 1000


# ---------------------------------------------------------------------------
# Page quality filter
# ---------------------------------------------------------------------------


def _count_words_raw(text: str) -> int:
    """Count whitespace-separated tokens in raw text."""
    return len(text.split())


def _is_blocked_page(
    main_text: str, headings: list[dict[str, Any]]
) -> str | None:
    """Return a reason string if the page should be excluded, else None."""
    if not main_text:
        return "missing main_content_text"
    wc = _count_words_raw(main_text)
    if wc < MIN_WORD_COUNT:
        return f"too few words ({wc} < {MIN_WORD_COUNT})"
    for h in headings:
        if BLOCK_HEADING_RE.search(h.get("text", "")):
            return f'block/error heading: "{h["text"]}"'
    return None


# ---------------------------------------------------------------------------
# N-gram extraction
# ---------------------------------------------------------------------------


def _extract_ngrams(tokens: list[str], n: int) -> list[str]:
    """Extract contiguous n-grams from a token list."""
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def _is_all_stopwords(ngram: str, stopword_set: set[str]) -> bool:
    """Return True if every word in the n-gram is a stopword."""
    return all(w in stopword_set for w in ngram.split())


def _extract_page_terms(
    main_text: str, stopword_set: set[str]
) -> Counter[str]:
    """Extract term frequency counts from a single page's text.

    Unigrams: stopwords removed.
    Bigrams/trigrams: keep stopwords within phrases, but filter n-grams
    that are entirely stopwords.
    """
    all_tokens = tokenize(main_text)
    filtered = remove_stopwords(all_tokens, stopword_set)

    terms: list[str] = _extract_ngrams(filtered, 1)
    for n in (2, 3):
        terms.extend(
            ng
            for ng in _extract_ngrams(all_tokens, n)
            if not _is_all_stopwords(ng, stopword_set)
        )
    return Counter(terms)


# ---------------------------------------------------------------------------
# Section splitting and heading normalization
# ---------------------------------------------------------------------------


def _normalize_heading(text: str) -> str:
    """Lowercase, strip numbers and punctuation, collapse whitespace."""
    normalized = text.lower()
    normalized = _HEADING_NORM_RE.sub("", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _jaccard_similarity(a: str, b: str) -> float:
    """Jaccard similarity on word sets of two strings."""
    set_a = set(a.split()) if a.strip() else set()
    set_b = set(b.split()) if b.strip() else set()
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


def _count_words(text: str) -> int:
    """Count whitespace-separated non-empty tokens."""
    return len(text.split())


def _split_sections(
    main_text: str, headings: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Split main_content_text into sections by heading positions."""
    if not headings:
        return [{"heading": "", "level": 0, "text": main_text}]

    positions: list[dict[str, Any]] = []
    for h in headings:
        idx = main_text.find(h["text"])
        if idx >= 0:
            positions.append(
                {"heading": h["text"], "level": h["level"], "pos": idx}
            )
    positions.sort(key=lambda p: p["pos"])

    sections: list[dict[str, Any]] = []

    # Intro before first heading
    if positions and positions[0]["pos"] > 0:
        intro = main_text[: positions[0]["pos"]].strip()
        if intro:
            sections.append({"heading": "", "level": 0, "text": intro})

    for i, pos in enumerate(positions):
        start = pos["pos"] + len(pos["heading"])
        end = positions[i + 1]["pos"] if i + 1 < len(positions) else len(main_text)
        sections.append(
            {
                "heading": pos["heading"],
                "level": pos["level"],
                "text": main_text[start:end].strip(),
            }
        )

    return sections


# ---------------------------------------------------------------------------
# Main analysis function
# ---------------------------------------------------------------------------


def analyze_content_topics(
    pages_dir: Path,
    seed: str,
    language: str = "de",
) -> ContentTopics:
    """Analyze content topics from competitor pages.

    Args:
        pages_dir: Directory containing extracted page JSON files.
        seed: The seed keyword to exclude from proof keywords.
        language: Language code for stopwords and IDF table.

    Returns:
        ContentTopics model with proof keywords, entity candidates,
        section weights, and content format signals.
    """
    stopword_set = load_stopword_set(language)
    idf_table = _load_idf_table(language)

    # Load page files (sorted for determinism)
    page_files = sorted(p for p in pages_dir.iterdir() if p.suffix == ".json")
    logger.info("Content topics: found %d page files in %s", len(page_files), pages_dir)

    if not page_files:
        return ContentTopics(
            proof_keywords=[],
            entity_candidates=[],
            section_weights=[],
            content_format_signals=ContentFormatSignals(
                pages_with_numbered_lists=0,
                pages_with_faq=0,
                pages_with_tables=0,
                avg_h2_count=0,
                dominant_pattern=None,
            ),
        )

    # Load and filter pages
    pages: list[dict[str, Any]] = []
    for f in page_files:
        raw = json.loads(f.read_text(encoding="utf-8"))
        domain = ""
        try:
            domain = urlparse(raw.get("url", "")).hostname or ""
        except Exception:
            pass
        page = {
            "file": f.name,
            "url": raw.get("url", ""),
            "domain": domain,
            "main_text": raw.get("main_content_text", ""),
            "headings": raw.get("headings", []),
            "signals": raw.get("html_signals", {}),
        }
        reason = _is_blocked_page(page["main_text"], page["headings"])
        if reason is not None:
            print(
                f"Skipping {page['domain'] or page['file']}: {reason}",
                file=sys.stderr,
            )
            continue
        pages.append(page)

    total_pages = len(pages)
    logger.info(
        "Content topics: %d pages passed quality filter (of %d)",
        total_pages,
        len(page_files),
    )

    # --- N-gram extraction and document frequency ---
    df_map: Counter[str] = Counter()
    tf_sum_map: Counter[str] = Counter()
    term_pages_map: defaultdict[str, list[str]] = defaultdict(list)

    for page in pages:
        term_counts = _extract_page_terms(page["main_text"], stopword_set)
        for term, count in term_counts.items():
            df_map[term] += 1
            tf_sum_map[term] += count
            term_pages_map[term].append(page["domain"])

    # --- Proof keywords ---
    seed_lower = seed.lower()
    proof_candidates: list[dict[str, Any]] = []

    for term, df in df_map.items():
        if df < 2 or term == seed_lower:
            continue
        avg_tf = js_round(tf_sum_map[term] / df * 10) / 10
        boost = _idf_boost(term, idf_table)
        idf_score = js_round(df * boost * 1000) / 1000
        proof_candidates.append(
            {
                "term": term,
                "document_frequency": df,
                "total_pages": total_pages,
                "avg_tf": normalize_number(avg_tf),
                "idf_boost": normalize_number(boost),
                "idf_score": normalize_number(idf_score),
            }
        )

    # Sort: idf_score desc, avg_tf desc, term asc
    proof_candidates.sort(key=lambda x: (-x["idf_score"], -x["avg_tf"], x["term"]))
    proof_keywords = [
        ProofKeyword(**p) for p in proof_candidates[:50]
    ]

    # --- Entity candidates ---
    entity_candidates_raw: list[dict[str, Any]] = []

    for term, df in df_map.items():
        if df < 2 or term == seed_lower:
            continue
        if " " in term:
            continue
        if len(term) < 3:
            continue
        entity_candidates_raw.append(
            {
                "term": term,
                "document_frequency": df,
                "pages": sorted(term_pages_map[term]),
            }
        )

    entity_candidates_raw.sort(
        key=lambda x: (-x["document_frequency"], x["term"])
    )
    entity_candidates = [
        EntityCandidate(**e) for e in entity_candidates_raw[:30]
    ]

    # --- Section weight analysis ---
    all_section_entries: list[dict[str, Any]] = []

    for page in pages:
        total_wc = _count_words(page["main_text"])
        if total_wc == 0:
            continue
        sections = _split_sections(page["main_text"], page["headings"])
        for sec in sections:
            if sec["heading"] == "":
                continue
            if sec["level"] > 2:
                continue
            wc = _count_words(sec["text"])
            pct = (wc / total_wc) * 100
            all_section_entries.append(
                {
                    "heading": sec["heading"],
                    "normalized": _normalize_heading(sec["heading"]),
                    "word_count": wc,
                    "content_percentage": pct,
                    "domain": page["domain"],
                }
            )

    # Greedy Jaccard clustering
    clusters: list[dict[str, Any]] = []
    for entry in all_section_entries:
        found = False
        for cluster in clusters:
            if _jaccard_similarity(cluster["normalized"], entry["normalized"]) >= 0.5:
                cluster["headings"].add(entry["heading"])
                cluster["entries"].append(entry)
                found = True
                break
        if not found:
            clusters.append(
                {
                    "normalized": entry["normalized"],
                    "headings": {entry["heading"]},
                    "entries": [entry],
                }
            )

    section_weights_raw: list[dict[str, Any]] = []
    for cluster in clusters:
        occurrence = len(cluster["entries"])
        total_word_count = sum(e["word_count"] for e in cluster["entries"])
        avg_word_count = js_round(total_word_count / occurrence)
        total_pct = sum(e["content_percentage"] for e in cluster["entries"])
        avg_pct = js_round(total_pct / occurrence * 10) / 10

        if avg_pct > 25:
            weight = "high"
        elif avg_pct >= 10:
            weight = "medium"
        else:
            weight = "low"

        section_weights_raw.append(
            {
                "heading_cluster": cluster["normalized"],
                "sample_headings": sorted(cluster["headings"]),
                "occurrence": occurrence,
                "avg_word_count": avg_word_count,
                "avg_content_percentage": normalize_number(avg_pct),
                "weight": weight,
            }
        )

    section_weights_raw.sort(
        key=lambda x: (-x["occurrence"], x["heading_cluster"])
    )
    section_weights = [SectionWeight(**s) for s in section_weights_raw]

    # --- Content format signals ---
    pages_with_numbered_lists = 0
    pages_with_faq = 0
    pages_with_tables = 0
    total_h2_count = 0

    for page in pages:
        signals = page["signals"]
        if signals.get("ordered_lists", 0) > 0:
            pages_with_numbered_lists += 1
        if signals.get("tables", 0) > 0:
            pages_with_tables += 1

        has_faq_heading = any(
            FAQ_HEADING_RE.search(h.get("text", "")) for h in page["headings"]
        )
        if has_faq_heading or signals.get("faq_sections", 0) > 0:
            pages_with_faq += 1

        h2_count = sum(1 for h in page["headings"] if h.get("level") == 2)
        total_h2_count += h2_count

    avg_h2_count = (
        js_round(total_h2_count / total_pages * 10) / 10 if total_pages else 0
    )

    content_format_signals = ContentFormatSignals(
        pages_with_numbered_lists=pages_with_numbered_lists,
        pages_with_faq=pages_with_faq,
        pages_with_tables=pages_with_tables,
        avg_h2_count=normalize_number(avg_h2_count),
        dominant_pattern=None,
    )

    logger.info(
        "Content topics complete: %d proof keywords, "
        "%d entity candidates, %d section weights",
        len(proof_keywords),
        len(entity_candidates),
        len(section_weights),
    )

    return ContentTopics(
        proof_keywords=proof_keywords,
        entity_candidates=entity_candidates,
        section_weights=section_weights,
        content_format_signals=content_format_signals,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze content topics from competitor pages."
    )
    parser.add_argument(
        "--pages-dir", required=True, type=Path, help="Directory with page JSON files."
    )
    parser.add_argument(
        "--seed", required=True, help="Seed keyword to exclude."
    )
    parser.add_argument(
        "--language", default="de", help="Language code (default: de)."
    )
    parser.add_argument(
        "--output", type=Path, default=None, help="Output file path (default: stdout)."
    )
    return parser


def _normalize_tree(obj: Any) -> Any:
    """Recursively apply normalize_number to all numeric values in a dict tree."""
    if isinstance(obj, dict):
        return {k: _normalize_tree(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_tree(v) for v in obj]
    if isinstance(obj, float):
        return normalize_number(obj)
    return obj


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    args = _build_parser().parse_args(argv)
    result = analyze_content_topics(args.pages_dir, args.seed, args.language)
    # Serialize via model_dump + json.dumps to preserve int/float distinction
    # (Pydantic coerces int->float for float-typed fields; normalize_tree reverses this)
    output_dict = _normalize_tree(result.model_dump())
    output_json = json.dumps(output_dict, indent=2, ensure_ascii=False)

    if args.output:
        args.output.write_text(output_json, encoding="utf-8")
    else:
        sys.stdout.write(output_json + "\n")


if __name__ == "__main__":
    main()
