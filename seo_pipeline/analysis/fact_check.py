"""Fact-check pipeline: supplement, search, verify claims.

Orchestrates the full fact-check workflow:
1. Extract regex-based claims from a draft
2. Supplement with LLM-discovered claims
3. Search each claim against the web
4. Verify each claim via LLM
5. Apply corrections and generate a report
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx
from pydantic import Field

from seo_pipeline.analysis.extract_claims import extract_claims
from seo_pipeline.llm.client import complete
from seo_pipeline.llm.config import LLMConfig
from seo_pipeline.models.analysis import (
    Claim,
    FactCheckMeta,
    FactCheckOutput,
    VerifiedClaim,
)
from seo_pipeline.models.common import PipelineBaseModel

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------
# Module-private response models for structured LLM output
# -----------------------------------------------------------------------


class _SupplementClaim(PipelineBaseModel):
    category: str
    value: str
    sentence: str
    line: int
    section: str | None


class _SupplementResponse(PipelineBaseModel):
    claims: list[_SupplementClaim]


class _VerdictResponse(PipelineBaseModel):
    verdict: str
    corrected_value: str | None
    notes: str | None


# -----------------------------------------------------------------------
# Category priority for claim sorting (lower = higher priority)
# -----------------------------------------------------------------------

_CATEGORY_PRIORITY: dict[str, int] = {
    "prices_costs": 0,
    "heights_distances": 1,
    "dates_years": 2,
    "counts": 3,
    "measurements": 4,
    "geographic": 5,
}

_DEFAULT_PRIORITY = 6  # supplemented or unknown categories


def _claim_priority(claim: Claim) -> int:
    """Return sort priority for a claim category."""
    return _CATEGORY_PRIORITY.get(claim.category, _DEFAULT_PRIORITY)


# -----------------------------------------------------------------------
# Public functions
# -----------------------------------------------------------------------


def supplement_claims(
    draft_text: str,
    existing_claims: list[Claim],
    llm_config: LLMConfig,
) -> list[Claim]:
    """Use LLM to find claims missed by regex extraction.

    Targets: named facts, superlatives, comparatives, legal claims.
    Returns Claim objects with IDs s001, s002, ... or [] on failure.
    """
    existing_summary = "\n".join(
        f"- [{c.category}] {c.value}" for c in existing_claims
    )

    sys_prompt = (
        "You are a fact-checking assistant. Identify verifiable "
        "factual claims in the draft that are NOT already in the "
        "existing claims list. Focus on: named facts, superlatives, "
        "comparatives, and legal claims. Return JSON with a 'claims' "
        "array. Each claim object must have: 'category' (string), "
        "'value' (the exact text), 'sentence' (full sentence), "
        "'line' (approximate 1-based line number), "
        "'section' (heading or null)."
    )

    messages = [
        {"role": "system", "content": sys_prompt},
        {
            "role": "user",
            "content": (
                f"Draft text:\n{draft_text}\n\n"
                f"Already extracted claims:\n{existing_summary}"
            ),
        },
    ]

    try:
        response = complete(
            messages,
            config=llm_config,
            response_model=_SupplementResponse,
            label="supplement_claims",
        )
        result: list[Claim] = []
        for i, raw in enumerate(response.claims):
            result.append(
                Claim(
                    id=f"s{i + 1:03d}",
                    category=raw.category or "supplemented",
                    value=raw.value,
                    sentence=raw.sentence,
                    line=raw.line,
                    section=raw.section,
                )
            )
        return result
    except Exception:
        logger.warning(
            "supplement_claims failed, returning empty list",
            exc_info=True,
        )
        return []


def search_claim(
    query: str,
    api_config: dict,
    *,
    timeout: float = 30.0,
) -> list[dict]:
    """Search for a claim via DataForSEO organic SERP.

    Returns up to 5 dicts with keys: title, url, snippet.
    Returns [] on any failure.
    """
    url = (
        f"{api_config['base']}"
        "/serp/google/organic/live/advanced"
    )
    headers = {
        "Authorization": f"Basic {api_config['auth']}",
        "Content-Type": "application/json",
    }
    payload = [
        {
            "keyword": query,
            "language_code": "en",
            "location_code": 2840,
            "depth": 5,
        }
    ]

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        results: list[dict] = []
        tasks = data.get("tasks", [])
        if tasks:
            task_result = tasks[0].get("result", [])
            if task_result:
                items = task_result[0].get("items", [])
                for item in items[:5]:
                    results.append(
                        {
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "snippet": item.get(
                                "description", ""
                            ),
                        }
                    )
        return results
    except Exception:
        logger.warning(
            "search_claim failed for query=%r",
            query,
            exc_info=True,
        )
        return []


def verify_claim(
    claim: Claim,
    snippets: list[dict],
    llm_config: LLMConfig,
) -> VerifiedClaim:
    """Verify a claim against search snippets via LLM.

    Returns a VerifiedClaim. On failure returns verdict="unverifiable".
    """
    snippets_text = "\n".join(
        f"- [{s.get('title', '')}]"
        f"({s.get('url', '')}): {s.get('snippet', '')}"
        for s in snippets
    )

    sys_prompt = (
        "You are a fact-checking assistant. Given a claim and web "
        "search snippets, determine if the claim is correct, "
        "incorrect, uncertain, or unverifiable. Return JSON with: "
        "'verdict' (one of: correct, incorrect, uncertain, "
        "unverifiable), 'corrected_value' (string or null - the "
        "corrected text if incorrect), 'notes' (string or null - "
        "brief explanation)."
    )

    messages = [
        {"role": "system", "content": sys_prompt},
        {
            "role": "user",
            "content": (
                f"Claim category: {claim.category}\n"
                f"Claim value: {claim.value}\n"
                f"Claim sentence: {claim.sentence}\n"
                f"Section: {claim.section or 'N/A'}\n\n"
                f"Search results:\n{snippets_text}"
            ),
        },
    ]

    source_urls = [
        s.get("url", "") for s in snippets if s.get("url")
    ]

    try:
        response = complete(
            messages,
            config=llm_config,
            response_model=_VerdictResponse,
            label="verify_claim",
        )
        return VerifiedClaim(
            id=claim.id,
            category=claim.category,
            value=claim.value,
            sentence=claim.sentence,
            line=claim.line,
            section=claim.section,
            verdict=response.verdict,
            corrected_value=response.corrected_value,
            sources=source_urls,
            notes=response.notes,
        )
    except Exception:
        logger.warning(
            "verify_claim failed for claim=%s",
            claim.id,
            exc_info=True,
        )
        return VerifiedClaim(
            id=claim.id,
            category=claim.category,
            value=claim.value,
            sentence=claim.sentence,
            line=claim.line,
            section=claim.section,
            verdict="unverifiable",
            sources=source_urls,
            notes="LLM call failed",
        )


def fact_check(
    draft_path: str,
    out_dir: str,
    llm_config: LLMConfig,
    api_config: dict,
) -> FactCheckOutput:
    """Run the full fact-check pipeline on a draft.

    Steps: extract, supplement, prioritize, search, verify, correct.
    """
    draft_path_obj = Path(draft_path)
    out_dir_obj = Path(out_dir)
    out_dir_obj.mkdir(parents=True, exist_ok=True)

    # Step 1: Extract regex-based claims
    claims_output = extract_claims(draft_path)
    regex_claims = claims_output.claims
    logger.info("Extracted %d claims via regex", len(regex_claims))

    # Step 2: Supplement with LLM
    draft_text = draft_path_obj.read_text(encoding="utf-8")
    logger.info("Supplementing claims via LLM...")
    supplemented = supplement_claims(
        draft_text, regex_claims, llm_config
    )
    logger.info("LLM added %d supplemental claims", len(supplemented))

    # Step 3: Prioritize and cap
    all_claims = regex_claims + supplemented
    all_claims.sort(key=_claim_priority)
    capped_claims = all_claims[:40]
    logger.info("Checking %d claims (capped at 40)", len(capped_claims))

    # Step 4: Search and verify
    verified: list[VerifiedClaim] = []
    for i, claim in enumerate(capped_claims, 1):
        logger.info(
            "[%d/%d] %s: %s", i, len(capped_claims),
            claim.id, claim.value[:60],
        )
        snippets = search_claim(claim.value, api_config)
        vc = verify_claim(claim, snippets, llm_config)
        logger.info("  → %s", vc.verdict)
        verified.append(vc)

    # Step 5: Apply corrections
    corrections_applied = 0
    for vc in verified:
        if vc.verdict == "incorrect" and vc.corrected_value:
            new_text = draft_text.replace(
                vc.value, vc.corrected_value
            )
            if new_text != draft_text:
                draft_text = new_text
                corrections_applied += 1

    draft_path_obj.write_text(draft_text, encoding="utf-8")

    # Step 6: Build output
    checked_at = (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
    meta = FactCheckMeta(
        draft=str(draft_path),
        checked_at=checked_at,
        total_claims_extracted=len(regex_claims),
        total_claims_supplemented=len(supplemented),
        total_claims_checked=len(verified),
        corrections_applied=corrections_applied,
    )
    output = FactCheckOutput(meta=meta, verified_claims=verified)

    # Write JSON report
    json_path = out_dir_obj / "fact-check-report.json"
    json_path.write_text(
        json.dumps(
            output.model_dump(), indent=2, ensure_ascii=False
        )
        + "\n",
        encoding="utf-8",
    )

    # Write Markdown report
    md_path = out_dir_obj / "fact-check-report.md"
    md_path.write_text(
        _build_markdown_report(output), encoding="utf-8"
    )

    return output


# -----------------------------------------------------------------------
# Markdown report builder
# -----------------------------------------------------------------------


def _build_markdown_report(output: FactCheckOutput) -> str:
    """Build a markdown report from a FactCheckOutput."""
    m = output.meta
    lines: list[str] = [
        "# Fact-Check Report",
        "",
        f"**Draft:** {m.draft}",
        f"**Checked at:** {m.checked_at}",
        "",
        "## Summary",
        "",
        f"- Claims extracted (regex): {m.total_claims_extracted}",
        f"- Claims supplemented (LLM): {m.total_claims_supplemented}",
        f"- Claims checked: {m.total_claims_checked}",
        f"- Corrections applied: {m.corrections_applied}",
        "",
        "## Verified Claims",
        "",
        "| ID | Category | Verdict | Value | Notes |",
        "|---|---|---|---|---|",
    ]

    for vc in output.verified_claims:
        notes = vc.notes or ""
        lines.append(
            f"| {vc.id} | {vc.category} | {vc.verdict}"
            f" | {vc.value} | {notes} |"
        )

    corrections = [
        vc
        for vc in output.verified_claims
        if vc.verdict == "incorrect" and vc.corrected_value
    ]
    if corrections:
        lines.extend(["", "## Corrections Applied", ""])
        for vc in corrections:
            lines.append(
                f"- **{vc.id}**: "
                f"`{vc.value}` -> `{vc.corrected_value}`"
            )

    lines.append("")
    return "\n".join(lines)
