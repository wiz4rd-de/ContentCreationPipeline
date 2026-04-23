"""Prompt builder for article draft generation (content-draft SKILL.md)."""

from __future__ import annotations


def build_draft_prompt(
    briefing_markdown: str,
    tone_of_voice: str | None,
    special_instructions: str | None,
) -> list[dict]:
    """Build system + user messages for article draft generation.

    Returns a list of message dicts with role/content keys suitable
    for passing to ``complete()``.  The LLM returns plain markdown text
    (no structured output / response_model).

    The Tone of Voice (ToV) is placed in the system prompt -- the
    highest-priority position for LLM attention -- so its constraints
    (A1-A7, B1-B8, C formatting rules) take precedence over any
    generic guidelines.
    """
    # -- ToV block: placed in system prompt for maximum priority --------
    tov_system_block = ""
    if tone_of_voice:
        tov_system_block = (
            "\n\n**Tone of Voice (PRIORITY -- overrides any "
            "generic quality rules below):**\n\n"
            f"{tone_of_voice}\n\n"
            "The Tone of Voice guidelines above are authoritative. "
            "When any other instruction in this prompt contradicts "
            "the ToV, the ToV wins. Pay special attention to "
            "Constraint-Gruppe A (A1-A7: critical frequency patterns), "
            "Constraint-Gruppe B (B1-B8: brand and legal rules), "
            "and Constraint-Gruppe C (formatting rules)."
        )

    instructions_block = ""
    if special_instructions:
        instructions_block = (
            "\n\n### Special Instructions\n\n"
            f"{special_instructions}"
        )

    system = (
        "You are an expert SEO content writer. "
        "You will receive a content briefing as markdown. "
        "Your task is to write a complete, publish-ready "
        "article draft following the briefing exactly."
        f"{tov_system_block}\n\n"
        "**Structure:**\n"
        "- Follow the outline from the brief exactly "
        "(H1, H2, H3 hierarchy)\n"
        "- Include all sections and key points specified "
        "in the brief\n"
        "- Respect the target word count from the brief\n\n"
        "**SEO:**\n"
        "- Place the primary keyword in the title, H1, "
        "first 100 words, and naturally throughout the text\n"
        "- Distribute secondary keywords organically "
        "-- never force them\n"
        "- Write the meta description from the brief "
        "or improve it\n"
        "- Suggest image alt texts where images are "
        "recommended\n\n"
        "**Quality:**\n"
        "- Follow the Tone of Voice guidelines provided. "
        "They override any generic quality rules.\n"
        "- Write in the target language natively "
        "-- no translation artifacts\n"
        "- Include concrete examples, data points, or "
        "expert quotes where the brief suggests them\n\n"
        "**Formatting:**\n"
        "- Use markdown formatting: headers, bold, lists, "
        "blockquotes where appropriate\n"
        "- Add `> **[TODO]** ...` blockquote markers for "
        "elements the writer must manually complete "
        "(e.g. internal links, proprietary data, images)\n"
        "- Mark any facts or statistics that should be "
        "verified with `> **[VERIFY]** ...` blockquote "
        "markers\n\n"
        "**Output format:**\n\n"
        "The draft document must follow this structure "
        "exactly:\n\n"
        "```\n"
        "# Draft: <Haupt-Keyword>\n\n"
        "| Feld | Wert |\n"
        "|------|------|\n"
        "| **Haupt-Keyword** | primary keyword (search volume) |\n"
        "| **Neben-Keywords** | secondary keywords, comma-separated "
        "(with SV each) |\n"
        "| **Title Tag** | composed title tag |\n"
        "| **Meta Description** | composed meta description "
        "(max 155 chars) |\n"
        "| **URL-Slug** | from briefing section A |\n"
        "| **Suchintention** | from briefing section A |\n"
        "| **Ziel-Wortanzahl** | from briefing section A |\n"
        "| **Zielgruppe** | from briefing section A |\n\n"
        "---\n\n"
        "# <H1 -- actual article headline>\n\n"
        "<article content follows>\n"
        "```\n\n"
        "Rules:\n"
        "- The document title `# Draft: <Haupt-Keyword>` is "
        "the first line -- no YAML frontmatter\n"
        "- The meta table sits between the document title "
        "and the article's H1\n"
        "- A `---` separator divides the meta block from "
        "the article content\n"
        "- All field values are pulled from the briefing's "
        '"A. Meta-Daten & Steuerung" section, except '
        "**Title Tag** and **Meta Description** which are "
        "composed during drafting\n"
        "- Do NOT put Title Tag or Meta Description into "
        "blockquote markers -- the meta table replaces "
        "that pattern\n\n"
        "**Self-review before returning:**\n"
        "- Primary keyword in title, H1, and first 100 words\n"
        "- All secondary keywords used at least once\n"
        "- All outline sections covered\n"
        "- Word count within +/-10%% of target\n"
        "- CTA(s) included\n"
        "- Meta info table present below document title "
        "with all required fields\n"
        "- Title Tag and Meta Description in table match "
        "SEO guidelines\n"
        "- No unverified facts stated as definitive "
        "(mark uncertain claims with "
        "`> **[VERIFY]** ...`)\n\n"
        "**ToV-Compliance self-review:**\n"
        "- No 'fuer jeden etwas zu bieten' or similar "
        "hedging phrases (A1)\n"
        "- No unqualified superlatives -- only with "
        "'einer der', 'gilt als', 'zaehlt zu' (A2)\n"
        "- No tricolon lists as stylistic device "
        "'Sonne, Strand und Meer' (A3)\n"
        "- No imperative cascades "
        "'Entdecke... Erlebe... Geniesse...' (A4)\n"
        "- No pseudo-personal promises "
        "'Du wirst es lieben' (A5)\n"
        "- No vague quality claims "
        "'erstklassige Hotels', 'traumhafte Straende' (A6)\n"
        "- No monotonous sentence structure across "
        "consecutive sentences (A7)\n"
        "- DERTOUR always uppercase, no hyphen in brand "
        "combinations (B1)\n"
        "- No 'Sterne' for hotels -- use "
        "'Kategorie' or 'Rauten' (B2)\n"
        "- 'kostenfrei' instead of "
        "'kostenlos'/'gratis' (B3)\n"
        "- No competitor names (B5)\n"
        "- No animal attractions in unnatural "
        "environments (B6)\n"
        "- No guarantees or performance promises "
        "'garantiert', 'perfekt' (B8)\n"
        "- Numbers < 12 spelled out, >= 12 as digits; "
        "units spelled out; abbreviations spelled out (C)\n"
        "- No sentence exceeds 40 words (Schicht 2.2)\n"
        "- Paragraph openings vary -- no two consecutive "
        "paragraphs with same opening strategy "
        "(Schicht 2.3)\n\n"
        "Return ONLY the draft markdown. "
        "No explanation, no code fences around the "
        "entire output."
    )

    user = (
        f"Content briefing:\n\n{briefing_markdown}"
        f"{instructions_block}"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
