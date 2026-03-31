"""Deterministic WDF*IDF content draft scorer.

Compares a draft's term profile against the competitor average using WDF*IDF
scoring. Same inputs always produce byte-identical output.

Usage:
    python -m seo_pipeline.analysis.score_draft_wdfidf \
        --draft <path/to/draft.txt> --pages-dir <pages/> \
        [--language de] [--threshold 0.1] [--output path]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

from seo_pipeline.analysis.analyze_content_topics import (
    _extract_ngrams,
    _is_all_stopwords,
    _load_idf_table,
)
from seo_pipeline.models.analysis import WdfIdfMeta, WdfIdfScore, WdfIdfTerm
from seo_pipeline.utils.math import js_round, normalize_number
from seo_pipeline.utils.tokenizer import load_stopword_set, remove_stopwords, tokenize

# ---------------------------------------------------------------------------
# WDF formula
# ---------------------------------------------------------------------------


def _compute_wdf(tf: int, word_count: int) -> float:
    """Compute WDF for a term frequency in a document.

    wdf(t, d) = log2(tf + 1) / log2(word_count)
    Returns 0 when word_count <= 1 (avoids division by zero).
    """
    if word_count <= 1:
        return 0.0
    return math.log2(tf + 1) / math.log2(word_count)


# ---------------------------------------------------------------------------
# Rounding helper
# ---------------------------------------------------------------------------


def _round6(v: float) -> float:
    """Round to 6 decimal places using JS Math.round() semantics."""
    return js_round(v * 1_000_000) / 1_000_000


# ---------------------------------------------------------------------------
# Term extraction
# ---------------------------------------------------------------------------


def _extract_terms(
    text: str, stopword_set: set[str]
) -> tuple[Counter[str], int]:
    """Extract term frequency counts and total word count from text.

    Returns:
        A tuple of (term_counts, word_count) where word_count is the total
        number of tokens before stopword removal (used for WDF denominator).
    """
    all_tokens = tokenize(text)
    word_count = len(all_tokens)
    filtered = remove_stopwords(all_tokens, stopword_set)

    terms: list[str] = _extract_ngrams(filtered, 1)
    for n in (2, 3):
        terms.extend(
            ng
            for ng in _extract_ngrams(all_tokens, n)
            if not _is_all_stopwords(ng, stopword_set)
        )
    return Counter(terms), word_count


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------


def score_draft_wdfidf(
    draft_path: Path,
    pages_dir: Path,
    language: str = "de",
    threshold: float = 0.1,
) -> WdfIdfScore:
    """Score a draft against competitor pages using WDF*IDF.

    Args:
        draft_path: Path to the draft text file.
        pages_dir: Directory containing competitor page JSON files.
        language: Language code for stopwords and IDF table.
        threshold: Delta threshold for signal assignment.

    Returns:
        WdfIdfScore model with metadata and per-term scores.
    """
    stopword_set = load_stopword_set(language)
    idf_table = _load_idf_table(language)

    # Extract draft terms
    draft_text = draft_path.read_text(encoding="utf-8")
    draft_counts, draft_word_count = _extract_terms(draft_text, stopword_set)

    # Load competitor pages (sorted for determinism)
    page_files = sorted(p for p in pages_dir.iterdir() if p.suffix == ".json")
    competitor_texts: list[str] = []
    for f in page_files:
        raw = json.loads(f.read_text(encoding="utf-8"))
        competitor_texts.append(raw.get("main_content_text", "") or "")

    n_competitors = len(competitor_texts)

    # Extract term data from each competitor page
    competitor_term_data = [
        _extract_terms(text, stopword_set) for text in competitor_texts
    ]

    # Build union of all terms from draft and competitors
    all_terms: set[str] = set(draft_counts.keys())
    for counts, _ in competitor_term_data:
        all_terms.update(counts.keys())

    # Corpus-local IDF: compute df per term across competitor pages
    corpus_df: Counter[str] | None = None
    if idf_table is None and n_competitors > 0:
        corpus_df = Counter()
        for counts, _ in competitor_term_data:
            for term in counts:
                corpus_df[term] += 1

    def _resolve_idf(term: str, df: int) -> float:
        """Resolve IDF for a term using reference table or corpus fallback."""
        if idf_table is not None:
            table_val = idf_table.get(term)
            if table_val is not None:
                return table_val
            # Neutral fallback for terms not in reference table
            return math.log2(n_competitors + 1) if n_competitors > 0 else 0.0
        # Corpus-local fallback
        if n_competitors == 0 or df == 0:
            return 0.0
        return math.log2(n_competitors / df)

    # Build per-term scores
    results: list[dict[str, object]] = []
    for term in all_terms:
        # Draft WDF*IDF
        draft_tf = draft_counts.get(term, 0)
        draft_wdf = _compute_wdf(draft_tf, draft_word_count)

        # Competitor average WDF
        competitor_wdf_sum = 0.0
        for counts, wc in competitor_term_data:
            tf = counts.get(term, 0)
            competitor_wdf_sum += _compute_wdf(tf, wc)
        competitor_avg_wdf = (
            competitor_wdf_sum / n_competitors if n_competitors > 0 else 0.0
        )

        # IDF resolution
        df = corpus_df.get(term, 0) if corpus_df is not None else 0
        idf = _resolve_idf(term, df)

        draft_wdfidf = _round6(draft_wdf * idf)
        competitor_avg_wdfidf = _round6(competitor_avg_wdf * idf)
        delta = _round6(draft_wdfidf - competitor_avg_wdfidf)
        abs_delta = abs(delta)

        if abs_delta < threshold:
            signal = "ok"
        elif delta < 0:
            signal = "increase"
        else:
            signal = "decrease"

        results.append(
            {
                "term": term,
                "draft_wdfidf": draft_wdfidf,
                "competitor_avg_wdfidf": competitor_avg_wdfidf,
                "delta": delta,
                "signal": signal,
            }
        )

    # Sort by absolute delta descending, then alphabetically
    results.sort(key=lambda r: (-abs(r["delta"]), r["term"]))

    meta = WdfIdfMeta(
        draft=str(draft_path),
        pages_dir=str(pages_dir),
        language=language,
        threshold=threshold,
        competitor_count=n_competitors,
        idf_source="reference" if idf_table is not None else "corpus-local",
    )
    terms = [WdfIdfTerm(**r) for r in results]

    return WdfIdfScore(meta=meta, terms=terms)


# ---------------------------------------------------------------------------
# Serialization helper
# ---------------------------------------------------------------------------


def _normalize_tree(obj: object) -> object:
    """Recursively apply normalize_number to all numeric values."""
    if isinstance(obj, dict):
        return {k: _normalize_tree(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_tree(v) for v in obj]
    if isinstance(obj, float):
        return normalize_number(obj)
    return obj


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Score a draft against competitor pages using WDF*IDF."
    )
    parser.add_argument(
        "--draft", required=True, type=Path, help="Path to draft text file."
    )
    parser.add_argument(
        "--pages-dir",
        required=True,
        type=Path,
        help="Directory with competitor page JSON files.",
    )
    parser.add_argument(
        "--language", default="de", help="Language code (default: de)."
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.1,
        help="Delta threshold for signal assignment (default: 0.1).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file path (default: stdout).",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    args = _build_parser().parse_args(argv)
    result = score_draft_wdfidf(
        args.draft, args.pages_dir, args.language, args.threshold
    )
    output_dict = _normalize_tree(result.model_dump())
    output_json = json.dumps(output_dict, indent=2, ensure_ascii=False)

    if args.output:
        args.output.write_text(output_json + "\n", encoding="utf-8")
    else:
        sys.stdout.write(output_json + "\n")


if __name__ == "__main__":
    main()
