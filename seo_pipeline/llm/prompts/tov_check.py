"""Prompt builder for ToV compliance audit."""

from __future__ import annotations


def build_tov_check_prompt(
    tov_text: str,
    draft_text: str,
) -> list[dict]:
    """Build system + user messages for ToV compliance checking.

    The LLM receives the full ToV as authoritative reference and the
    draft with line numbers prepended.  It returns structured JSON
    (via response_model) listing every violation found.
    """
    # Prepend line numbers so the LLM can reference exact locations
    numbered_lines = [
        f"{i + 1}: {line}"
        for i, line in enumerate(draft_text.splitlines())
    ]
    numbered_draft = "\n".join(numbered_lines)

    system = (
        "Du bist ein ToV-Auditor. Deine Aufgabe ist es, den "
        "folgenden Draft gegen die bereitgestellten Tone-of-Voice-"
        "Richtlinien zu pruefen.\n\n"
        "Pruefe den Draft systematisch gegen ALLE Constraint-Gruppen:\n"
        "- Constraint-Gruppe A (A1-A7): Kritische Frequenzmuster\n"
        "- Constraint-Gruppe B (B1-B8): Marken- und Rechtsregeln\n"
        "- Constraint-Gruppe C: Formatierung\n"
        "- Schicht 2: Generierungslogik (Adjektiv-Test, Satzlaenge, "
        "Absatzstruktur, Satzstruktur-Variation)\n"
        "- Schicht 5: Ueberschriften & Meta\n\n"
        "Fuer jeden Verstoss gib an:\n"
        "- line: Die 1-basierte Zeilennummer im Draft\n"
        "- rule: Die Regel-Referenz (z.B. 'A2', 'B3', 'C/Zahlen', "
        "'Schicht2.2')\n"
        "- severity: 'critical' fuer Constraint-Gruppe A und B "
        "Verstoesse, 'warning' fuer C, Schicht 2, Schicht 5\n"
        "- text: Der betroffene Text (exaktes Zitat aus dem Draft)\n"
        "- suggestion: Ein konkreter Korrekturvorschlag\n\n"
        "Setze compliant auf true nur wenn KEINE Verstoesse gefunden "
        "wurden. Zaehle in summary die Anzahl der Verstoesse nach "
        "Schweregrad."
    )

    user = (
        f"Tone of Voice (AUTORITATIV):\n\n{tov_text}\n\n"
        f"---\n\nDraft (mit Zeilennummern):\n\n{numbered_draft}"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
