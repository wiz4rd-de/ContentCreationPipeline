"""Tests for the ToV compliance check module.

Covers: prompt building, orchestration with mocked LLM, report generation,
default ToV resolution, and graceful error handling.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from seo_pipeline.analysis.tov_check import _find_tov, tov_check
from seo_pipeline.llm.config import LLMConfig
from seo_pipeline.llm.prompts.tov_check import build_tov_check_prompt
from seo_pipeline.models.analysis import TovCheckOutput, TovViolation

# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------


def _make_llm_config() -> LLMConfig:
    return LLMConfig(
        provider="anthropic", model="test-model", api_key="k",
    )


def _make_tov_check_output(
    violations: list[TovViolation] | None = None,
) -> TovCheckOutput:
    """Build a TovCheckOutput for testing."""
    if violations is None:
        violations = []
    critical = sum(1 for v in violations if v.severity == "critical")
    warning = sum(1 for v in violations if v.severity == "warning")
    return TovCheckOutput(
        violations=violations,
        summary={"critical": critical, "warning": warning},
        compliant=len(violations) == 0,
    )


# -----------------------------------------------------------------------
# Prompt builder tests
# -----------------------------------------------------------------------


class TestBuildTovCheckPrompt:
    def test_returns_two_messages(self):
        messages = build_tov_check_prompt("ToV text", "Draft text")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_system_mentions_constraint_groups(self):
        messages = build_tov_check_prompt("ToV", "Draft")
        system = messages[0]["content"]
        assert "Constraint-Gruppe A" in system
        assert "Constraint-Gruppe B" in system
        assert "Constraint-Gruppe C" in system
        assert "Schicht 2" in system
        assert "Schicht 5" in system

    def test_user_contains_tov_and_draft(self):
        messages = build_tov_check_prompt("My ToV rules", "Line one\nLine two")
        user = messages[1]["content"]
        assert "My ToV rules" in user
        assert "1: Line one" in user
        assert "2: Line two" in user

    def test_line_numbers_prepended(self):
        draft = "First\nSecond\nThird"
        messages = build_tov_check_prompt("tov", draft)
        user = messages[1]["content"]
        assert "1: First" in user
        assert "2: Second" in user
        assert "3: Third" in user


# -----------------------------------------------------------------------
# Find ToV tests
# -----------------------------------------------------------------------


class TestFindTov:
    def test_explicit_path(self, tmp_path):
        tov = tmp_path / "custom-tov.md"
        tov.write_text("custom", encoding="utf-8")
        result = _find_tov(str(tov))
        assert result == tov

    def test_explicit_path_not_found(self, tmp_path):
        import pytest

        with pytest.raises(FileNotFoundError, match="not found"):
            _find_tov(str(tmp_path / "nope.md"))

    def test_default_path_resolution(self):
        """Default ToV resolves to templates/DT_ToV_v3.md."""
        result = _find_tov(None)
        assert result.name == "DT_ToV_v3.md"
        assert result.exists()


# -----------------------------------------------------------------------
# Orchestration tests (mocked LLM)
# -----------------------------------------------------------------------


class TestTovCheck:
    def test_compliant_draft(self, tmp_path):
        """A compliant draft produces no violations."""
        draft = tmp_path / "draft.md"
        draft.write_text("Ein guter Text ohne Verstoesse.", encoding="utf-8")

        tov = tmp_path / "tov.md"
        tov.write_text("Constraint-Gruppe A: ...", encoding="utf-8")

        mock_output = _make_tov_check_output(violations=[])

        with patch(
            "seo_pipeline.analysis.tov_check.complete",
            return_value=mock_output,
        ):
            result = tov_check(
                str(draft), str(tmp_path),
                _make_llm_config(), tov_path=str(tov),
            )

        assert result.compliant is True
        assert result.summary == {"critical": 0, "warning": 0}
        assert len(result.violations) == 0

    def test_non_compliant_draft(self, tmp_path):
        """A non-compliant draft returns violations."""
        draft = tmp_path / "draft.md"
        draft.write_text(
            "Kreta hat fuer jeden etwas zu bieten.",
            encoding="utf-8",
        )

        tov = tmp_path / "tov.md"
        tov.write_text("ToV rules", encoding="utf-8")

        violation = TovViolation(
            line=1,
            rule="A1",
            severity="critical",
            text="fuer jeden etwas zu bieten",
            suggestion="Konkrete Zielgruppe nennen",
        )
        mock_output = _make_tov_check_output(violations=[violation])

        with patch(
            "seo_pipeline.analysis.tov_check.complete",
            return_value=mock_output,
        ):
            result = tov_check(
                str(draft), str(tmp_path),
                _make_llm_config(), tov_path=str(tov),
            )

        assert result.compliant is False
        assert result.summary["critical"] == 1
        assert len(result.violations) == 1
        assert result.violations[0].rule == "A1"

    def test_writes_json_report(self, tmp_path):
        """Writes a JSON report file."""
        draft = tmp_path / "draft.md"
        draft.write_text("Text", encoding="utf-8")

        tov = tmp_path / "tov.md"
        tov.write_text("ToV", encoding="utf-8")

        mock_output = _make_tov_check_output()

        with patch(
            "seo_pipeline.analysis.tov_check.complete",
            return_value=mock_output,
        ):
            tov_check(
                str(draft), str(tmp_path),
                _make_llm_config(), tov_path=str(tov),
            )

        json_path = tmp_path / "tov-check-report.json"
        assert json_path.exists()
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert "violations" in data
        assert "summary" in data
        assert "compliant" in data

    def test_writes_markdown_report(self, tmp_path):
        """Writes a Markdown report file."""
        draft = tmp_path / "draft.md"
        draft.write_text("Text", encoding="utf-8")

        tov = tmp_path / "tov.md"
        tov.write_text("ToV", encoding="utf-8")

        violation = TovViolation(
            line=1,
            rule="B3",
            severity="critical",
            text="kostenlos",
            suggestion="kostenfrei",
        )
        mock_output = _make_tov_check_output(violations=[violation])

        with patch(
            "seo_pipeline.analysis.tov_check.complete",
            return_value=mock_output,
        ):
            tov_check(
                str(draft), str(tmp_path),
                _make_llm_config(), tov_path=str(tov),
            )

        md_path = tmp_path / "tov-check-report.md"
        assert md_path.exists()
        md = md_path.read_text(encoding="utf-8")
        assert "ToV Compliance Report" in md
        assert "B3" in md
        assert "kostenlos" in md
        assert "kostenfrei" in md

    def test_draft_not_found(self, tmp_path):
        """Raises FileNotFoundError for missing draft."""
        import pytest

        with pytest.raises(FileNotFoundError, match="Draft not found"):
            tov_check(
                str(tmp_path / "nope.md"), str(tmp_path),
                _make_llm_config(),
            )

    def test_defaults_out_dir_to_draft_parent(self, tmp_path):
        """Output defaults to draft's parent directory."""
        sub = tmp_path / "subdir"
        sub.mkdir()
        draft = sub / "draft.md"
        draft.write_text("Text", encoding="utf-8")

        tov = tmp_path / "tov.md"
        tov.write_text("ToV", encoding="utf-8")

        mock_output = _make_tov_check_output()

        with patch(
            "seo_pipeline.analysis.tov_check.complete",
            return_value=mock_output,
        ):
            tov_check(
                str(draft), llm_config=_make_llm_config(),
                tov_path=str(tov),
            )

        assert (sub / "tov-check-report.json").exists()

    def test_multiple_violations_mixed_severity(self, tmp_path):
        """Handles mixed critical and warning violations."""
        draft = tmp_path / "draft.md"
        draft.write_text("Draft with issues", encoding="utf-8")

        tov = tmp_path / "tov.md"
        tov.write_text("ToV", encoding="utf-8")

        violations = [
            TovViolation(
                line=1, rule="A1", severity="critical",
                text="fuer jeden etwas", suggestion="fix A1",
            ),
            TovViolation(
                line=2, rule="C/Zahlen", severity="warning",
                text="3 Straende", suggestion="drei Straende",
            ),
            TovViolation(
                line=3, rule="B8", severity="critical",
                text="garantiert", suggestion="remove guarantee",
            ),
        ]
        mock_output = _make_tov_check_output(violations=violations)

        with patch(
            "seo_pipeline.analysis.tov_check.complete",
            return_value=mock_output,
        ):
            result = tov_check(
                str(draft), str(tmp_path),
                _make_llm_config(), tov_path=str(tov),
            )

        assert result.summary["critical"] == 2
        assert result.summary["warning"] == 1
        assert len(result.violations) == 3


# -----------------------------------------------------------------------
# Model tests
# -----------------------------------------------------------------------


class TestTovCheckOutputModel:
    def test_round_trip(self):
        """Model validates and serializes correctly."""
        data = {
            "violations": [
                {
                    "line": 5,
                    "rule": "A2",
                    "severity": "critical",
                    "text": "der schoenste",
                    "suggestion": "einer der bekanntesten",
                },
            ],
            "summary": {"critical": 1, "warning": 0},
            "compliant": False,
        }
        output = TovCheckOutput.model_validate(data)
        assert output.compliant is False
        assert len(output.violations) == 1
        dumped = output.model_dump()
        assert dumped["violations"][0]["rule"] == "A2"
        assert dumped["summary"]["critical"] == 1

    def test_empty_violations(self):
        """Compliant output with no violations."""
        output = TovCheckOutput(
            violations=[],
            summary={"critical": 0, "warning": 0},
            compliant=True,
        )
        assert output.compliant is True
        dumped = output.model_dump()
        assert dumped["violations"] == []
