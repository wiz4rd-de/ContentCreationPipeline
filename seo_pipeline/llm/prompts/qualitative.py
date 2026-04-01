"""Prompt builders for qualitative analysis (SKILL.md steps 2.1/2.2)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from seo_pipeline.models.analysis import BriefingData


def _serialize_briefing(briefing_data: BriefingData) -> str:
    """Serialize BriefingData to compact JSON for prompt inclusion."""
    return json.dumps(
        briefing_data.model_dump(mode="json"),
        ensure_ascii=False,
    )


def build_qualitative_prompt(
    briefing_data: BriefingData,
) -> list[dict]:
    """Build system + user messages for the 5 qualitative fields.

    Returns a list of message dicts with role/content keys suitable
    for passing to ``complete()``.  The LLM is asked to return JSON
    matching ``QualitativeResponse``.
    """
    seed = briefing_data.meta.seed_keyword
    data_json = _serialize_briefing(briefing_data)

    system = (
        "You are an expert SEO content strategist. "
        "You will receive pre-computed pipeline data as JSON. "
        "All quantitative data is authoritative -- do NOT "
        "re-count, re-rank, or modify any numeric values. "
        "Your role is strictly qualitative interpretation "
        "and strategic recommendation.\n\n"
        "Return a JSON object with exactly these 5 keys:\n"
        "  entity_clusters, geo_audit, "
        "content_format_recommendation, "
        "unique_angles, aio_strategy\n\n"
        "Follow the output schemas described in the user "
        "message precisely."
    )

    user = (
        f"Seed keyword: {seed}\n"
        f"\n"
        f"Briefing data:\n"
        f"{data_json}\n"
        f"\n"
        "Perform the following 5 qualitative analyses "
        "and return them as a single JSON object.\n"
        "\n"
        "---\n"
        "\n"
        '### 2.1A: Entity Categorization -> '
        '"entity_clusters"\n'
        "\n"
        "Input: content_analysis.entity_candidates "
        "(list of terms with document_frequency, "
        "prominence)\n"
        "\n"
        "Task: Group the entity candidates into 3-5 "
        "semantic categories (e.g., "
        '"Orte & Regionen", '
        '"Aktivitaeten & Erlebnisse", '
        '"Praktische Infos"). '
        "For each category, list the entities and "
        "generate a synonym list.\n"
        "\n"
        "Output schema:\n"
        "```json\n"
        "[\n"
        "  {\n"
        '    "category": "Category Name",\n'
        '    "entities": ["entity1", "entity2"],\n'
        '    "synonyms": '
        '{ "entity1": ["synonym1", "synonym2"] }\n'
        "  }\n"
        "]\n"
        "```\n"
        "\n"
        "---\n"
        "\n"
        '### 2.1B: GEO Audit -> "geo_audit"\n'
        "\n"
        "Input: meta.seed_keyword + full briefing data "
        "for context\n"
        "\n"
        "Task: Based on your training data "
        "(not the pipeline data), assess:\n"
        "- Semantic must-haves: Topics/entities the "
        "article MUST cover to be authoritative\n"
        "- Hidden gems: Lesser-known aspects that could "
        "differentiate the content\n"
        "- Hallucination risks: Facts commonly stated "
        "incorrectly about this topic\n"
        "- Information gaps: Topics the competitor data "
        "does NOT cover but should\n"
        "\n"
        "Output schema:\n"
        "```json\n"
        "{\n"
        '  "must_haves": ["..."],\n'
        '  "hidden_gems": ["..."],\n'
        '  "hallucination_risks": ["..."],\n'
        '  "information_gaps": ["..."]\n'
        "}\n"
        "```\n"
        "\n"
        "---\n"
        "\n"
        "### 2.1C: Content Format Recommendation -> "
        '"content_format_recommendation"\n'
        "\n"
        "Input: content_analysis.content_format_signals "
        "+ competitor_analysis.page_structures\n"
        "\n"
        "Task: Given the format signals (list counts, "
        "heading patterns, avg word count), recommend "
        "one of: Ratgeber, Listicle, or Hybrid. "
        "Provide a brief rationale.\n"
        "\n"
        "Output schema:\n"
        "```json\n"
        "{\n"
        '  "format": "Hybrid",\n'
        '  "rationale": "..."\n'
        "}\n"
        "```\n"
        "\n"
        "---\n"
        "\n"
        '### 2.1D: Unique Angles -> "unique_angles"\n'
        "\n"
        "Input: All data from the briefing (especially "
        "competitor_analysis, content_analysis, "
        "faq_data)\n"
        "\n"
        "Task: Identify 3-5 differentiation "
        "opportunities beyond what the deterministic "
        "data shows. What can this article offer that "
        "competitors do not?\n"
        "\n"
        "Output schema:\n"
        "```json\n"
        '[ { "angle": "...", "rationale": "..." } ]\n'
        "```\n"
        "\n"
        "---\n"
        "\n"
        "### 2.1E: AIO Optimization Strategy -> "
        '"aio_strategy"\n'
        "\n"
        "Input: serp_data.aio + faq_data + "
        "content_analysis.proof_keywords\n"
        "\n"
        "Task: Given the AIO data (presence, citations, "
        "text), recommend 3-5 quotable snippet patterns "
        "the article should include to maximize AI "
        "Overview citation probability. Each snippet "
        "should be a concise, factual statement that "
        "an AI could cite directly.\n"
        "\n"
        "Output schema:\n"
        "```json\n"
        "{\n"
        '  "snippets": [\n'
        "    { "
        '"topic": "...", '
        '"pattern": "...", '
        '"target_section": "..." }\n'
        "  ]\n"
        "}\n"
        "```\n"
        "\n"
        "---\n"
        "\n"
        "Return ONLY the JSON object with all 5 keys. "
        "No markdown fences, no explanation."
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_briefing_assembly_prompt(
    briefing_data: BriefingData,
    template: str | None,
    tone_of_voice: str | None,
) -> list[dict]:
    """Build system + user messages for final briefing markdown.

    Returns a list of message dicts.  The LLM returns plain
    markdown text (no structured output / response_model).
    """
    seed = briefing_data.meta.seed_keyword
    data_json = _serialize_briefing(briefing_data)

    template_block = ""
    if template:
        template_block = (
            f"\n\n### Content Template\n\n{template}"
        )

    tov_block = ""
    if tone_of_voice:
        tov_block = (
            "\n\n### Tone of Voice Guidelines"
            f"\n\n{tone_of_voice}"
        )

    system = (
        "You are an expert SEO content strategist "
        "assembling a final content briefing. "
        "All quantitative data in the briefing JSON is "
        "pre-computed and authoritative. "
        "Do NOT re-count keywords, re-rank clusters, "
        "re-compute volumes, or modify any "
        "numeric values. Every number, ranking, and "
        "classification must appear unchanged "
        "in your output.\n\n"
        "Return the briefing as structured markdown. "
        "No JSON, no code fences around the "
        "entire output."
    )

    user = (
        f"Seed keyword: {seed}\n"
        "\n"
        "Briefing data (JSON):\n"
        f"{data_json}{template_block}{tov_block}\n"
        "\n"
        "Assemble a complete content briefing as a "
        "structured markdown document with these "
        "sections:\n"
        "\n"
        "**1. Strategische Ausrichtung**\n"
        "- Content format recommendation "
        "(from qualitative.content_format_recommendation)"
        "\n"
        "- Target audience and search intent\n"
        "- Competitive positioning summary\n"
        "\n"
        "**2. Keywords & Semantik**\n"
        "- Primary keyword cluster "
        "(from keyword_data.clusters[0])\n"
        "- Top 5 keyword clusters with volumes "
        "(from keyword_data -- copy exactly, "
        "do NOT re-rank)\n"
        "- Entity categories with synonyms "
        "(from qualitative.entity_clusters)\n"
        "- Proof keywords "
        "(from content_analysis.proof_keywords "
        "-- copy exactly)\n"
        "\n"
        "**3. Seitenaufbau & Pflicht-Module**\n"
        "- Common modules that ALL competitors use "
        "(from competitor_analysis.common_modules "
        "-- copy exactly)\n"
        "- Rare modules used by few competitors "
        "(from competitor_analysis.rare_modules "
        "-- copy exactly)\n"
        "- Average word count benchmark "
        "(from competitor_analysis.avg_word_count)\n"
        "- Section weight distribution "
        "(from content_analysis.section_weights "
        "-- copy exactly)\n"
        "\n"
        "**4. Differenzierungs-Chancen**\n"
        "- Rare modules as opportunities "
        "(from deterministic data)\n"
        "- Unique angles "
        "(from qualitative.unique_angles)\n"
        "- Information gaps "
        "(from qualitative.geo_audit)\n"
        "\n"
        "**5. AI-Overview-Optimierung**\n"
        "- Current AIO status "
        "(from serp_data.aio -- present/absent, "
        "cited domains)\n"
        "- Quotable snippet recommendations "
        "(from qualitative.aio_strategy)\n"
        "- AIO-relevant FAQ questions "
        "(cross-reference with faq_data)\n"
        "\n"
        "**6. FAQ-Sektion**\n"
        "- FAQ questions in deterministic priority "
        "order (from faq_data.questions "
        "-- copy ranking exactly)\n"
        "- For each question: the priority score "
        "and source\n"
        "- Answer guidelines per question "
        "(qualitative: what the answer should cover)\n"
        "\n"
        "**7. Content-Struktur**\n"
        "- If a template was provided: map template "
        "sections to keyword clusters and "
        "section weights\n"
        "- If no template: propose a section outline "
        "based on competitor section weights and "
        "keyword clusters\n"
        "\n"
        "**8. Informationsluecken**\n"
        "- GEO audit must-haves not covered by "
        "competitors (from qualitative.geo_audit)\n"
        "- Hidden gems "
        "(from qualitative.geo_audit)\n"
        "- Hallucination risks to avoid "
        "(from qualitative.geo_audit)\n"
        "\n"
        "**9. Keyword-Referenz**\n"
        "This section is FULLY DETERMINISTIC. "
        "Copy directly from keyword_data.clusters. "
        "For each cluster:\n"
        "- Cluster keyword, rank, total search volume, "
        "keyword count, opportunity score\n"
        "Do NOT summarize, re-rank, or omit "
        "any clusters."
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
