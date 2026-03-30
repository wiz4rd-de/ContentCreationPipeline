"""Tests for the preflight validation module."""

import tempfile
from pathlib import Path

from seo_pipeline.utils.preflight import (
    check_api_env,
    check_auth,
    check_auth_format,
    check_base,
    check_base64,
    parse_env_content,
    run_preflight,
)


class TestCheckApiEnv:
    """Tests for check_api_env."""

    def test_returns_ok_true_when_api_env_exists(self):
        """Returns ok:true when api.env exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / "api.env"
            env_file.write_text("DATAFORSEO_AUTH=abc\n")
            result = check_api_env(tmpdir)
            assert result.ok is True
            assert "api.env" in result.message

    def test_returns_ok_false_when_api_env_missing(self):
        """Returns ok:false when api.env is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = check_api_env(tmpdir)
            assert result.ok is False
            assert "api.env not found" in result.message
            assert "cp api.env.example api.env" in result.message


class TestParseEnvContent:
    """Tests for parse_env_content."""

    def test_parses_key_value_lines_into_map(self):
        """Parses KEY=VALUE lines into a map."""
        env = parse_env_content(
            "DATAFORSEO_AUTH=abc123\nDATAFORSEO_BASE=https://api.example.com\n"
        )
        assert env["DATAFORSEO_AUTH"] == "abc123"
        assert env["DATAFORSEO_BASE"] == "https://api.example.com"

    def test_skips_comment_lines_and_empty_lines(self):
        """Skips comment lines and empty lines."""
        env = parse_env_content(
            "# comment\n\nDATAFORSEO_AUTH=secret\n\n# another\nDATAFORSEO_BASE=https://base.example.com\n"
        )
        assert env["DATAFORSEO_AUTH"] == "secret"
        assert env["DATAFORSEO_BASE"] == "https://base.example.com"

    def test_preserves_values_containing_equals_signs(self):
        """Preserves values containing = signs (e.g. base64 tokens)."""
        env = parse_env_content("DATAFORSEO_AUTH=abc123==\n")
        assert env["DATAFORSEO_AUTH"] == "abc123=="


class TestCheckAuth:
    """Tests for check_auth."""

    def test_returns_ok_true_when_auth_is_set(self):
        """Returns ok:true when DATAFORSEO_AUTH is set."""
        result = check_auth({"DATAFORSEO_AUTH": "abc123base64token"})
        assert result.ok is True
        assert "DATAFORSEO_AUTH" in result.message

    def test_returns_ok_false_when_auth_missing(self):
        """Returns ok:false when DATAFORSEO_AUTH is missing."""
        result = check_auth({})
        assert result.ok is False
        assert "DATAFORSEO_AUTH is not set" in result.message
        assert "api.env.example" in result.message

    def test_returns_ok_false_when_auth_empty_string(self):
        """Returns ok:false when DATAFORSEO_AUTH is empty string."""
        result = check_auth({"DATAFORSEO_AUTH": ""})
        assert result.ok is False
        assert "DATAFORSEO_AUTH is not set" in result.message


class TestCheckBase64:
    """Tests for check_base64."""

    def test_returns_true_for_valid_base64_without_padding(self):
        """Returns true for a valid base64 string without padding."""
        assert check_base64("abc123BASE64token") is True

    def test_returns_true_for_valid_base64_with_padding(self):
        """Returns true for a valid base64 string with = padding."""
        assert check_base64("abc123==") is True

    def test_returns_true_for_realistic_base64_encoded_login_password(self):
        """Returns true for realistic base64-encoded login:password."""
        import base64

        simple_encoded = base64.b64encode(b"login:password").decode()
        assert check_base64(simple_encoded) is True

    def test_returns_false_for_string_with_colon(self):
        """Returns false for a string containing a colon (raw login:password)."""
        assert check_base64("login:password") is False

    def test_returns_false_for_string_with_spaces(self):
        """Returns false for a string containing spaces."""
        assert check_base64("abc def") is False

    def test_returns_false_for_empty_string(self):
        """Returns false for an empty string."""
        assert check_base64("") is False

    def test_returns_false_for_non_string_input(self):
        """Returns false for non-string input."""
        assert check_base64(None) is False  # type: ignore
        assert check_base64(123) is False  # type: ignore

    def test_returns_false_for_placeholder_string(self):
        """Returns false for a placeholder string with angle brackets."""
        assert check_base64("<your-base64-token-here>") is False

    def test_returns_true_for_strings_with_trailing_padding(self):
        """Returns true for strings with only trailing = padding."""
        assert check_base64("dGVzdA==") is True

    def test_returns_false_for_string_with_equals_in_middle(self):
        """Returns false for a string with = in the middle."""
        assert check_base64("abc=def") is False


class TestCheckAuthFormat:
    """Tests for check_auth_format."""

    def test_returns_ok_true_for_valid_base64_auth(self):
        """Returns ok:true for a valid base64 AUTH value."""
        result = check_auth_format({"DATAFORSEO_AUTH": "dGVzdA=="})
        assert result.ok is True
        assert "valid base64" in result.message

    def test_returns_ok_false_for_raw_login_password(self):
        """Returns ok:false for a raw login:password value."""
        result = check_auth_format({"DATAFORSEO_AUTH": "user:password"})
        assert result.ok is False
        assert "does not look like valid base64" in result.message
        assert "base64" in result.message

    def test_returns_ok_false_when_auth_missing(self):
        """Returns ok:false when DATAFORSEO_AUTH is missing."""
        result = check_auth_format({})
        assert result.ok is False


class TestCheckBase:
    """Tests for check_base."""

    def test_returns_ok_true_when_base_is_set(self):
        """Returns ok:true when DATAFORSEO_BASE is set."""
        result = check_base({"DATAFORSEO_BASE": "https://api.dataforseo.com/v3"})
        assert result.ok is True
        assert "DATAFORSEO_BASE" in result.message

    def test_returns_ok_false_when_base_missing(self):
        """Returns ok:false when DATAFORSEO_BASE is missing."""
        result = check_base({})
        assert result.ok is False
        assert "DATAFORSEO_BASE is not set" in result.message
        assert "https://api.dataforseo.com/v3" in result.message

    def test_returns_ok_false_when_base_empty_string(self):
        """Returns ok:false when DATAFORSEO_BASE is empty string."""
        result = check_base({"DATAFORSEO_BASE": ""})
        assert result.ok is False


class TestRunPreflight:
    """Tests for run_preflight."""

    def test_all_checks_pass_with_valid_env(self, capsys):
        """All checks pass with a valid env file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / "api.env"
            env_file.write_text(
                "DATAFORSEO_AUTH=dGVzdA==\nDATAFORSEO_BASE=https://api.dataforseo.com/v3\n"
            )
            result = run_preflight(tmpdir)
            assert result is True
            captured = capsys.readouterr()
            assert "[OK]" in captured.err

    def test_missing_auth_fails(self, capsys):
        """Missing DATAFORSEO_AUTH fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / "api.env"
            env_file.write_text("DATAFORSEO_BASE=https://api.dataforseo.com/v3\n")
            result = run_preflight(tmpdir)
            assert result is False
            captured = capsys.readouterr()
            assert "[FAIL]" in captured.err

    def test_empty_auth_fails(self, capsys):
        """Empty DATAFORSEO_AUTH value fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / "api.env"
            env_file.write_text(
                "DATAFORSEO_AUTH=\nDATAFORSEO_BASE=https://api.dataforseo.com/v3\n"
            )
            result = run_preflight(tmpdir)
            assert result is False
            captured = capsys.readouterr()
            assert "[FAIL]" in captured.err

    def test_invalid_base64_detected(self, capsys):
        """Invalid base64 format is detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / "api.env"
            env_file.write_text(
                "DATAFORSEO_AUTH=user:password\nDATAFORSEO_BASE=https://api.dataforseo.com/v3\n"
            )
            result = run_preflight(tmpdir)
            assert result is False
            captured = capsys.readouterr()
            assert "[FAIL]" in captured.err
            assert "base64" in captured.err

    def test_missing_base_fails(self, capsys):
        """Missing DATAFORSEO_BASE fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / "api.env"
            env_file.write_text("DATAFORSEO_AUTH=dGVzdA==\n")
            result = run_preflight(tmpdir)
            assert result is False
            captured = capsys.readouterr()
            assert "[FAIL]" in captured.err

    def test_reports_all_failures_not_just_first(self, capsys):
        """Reports all failures, not just the first one."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / "api.env"
            # Missing both AUTH and BASE, and AUTH is invalid format
            env_file.write_text("DATAFORSEO_AUTH=\n")
            result = run_preflight(tmpdir)
            assert result is False
            captured = capsys.readouterr()
            # Should have multiple [FAIL] entries
            fail_count = captured.err.count("[FAIL]")
            assert fail_count >= 2, "Should report multiple failures"

    def test_missing_api_env_file_fails(self, capsys):
        """Missing api.env file fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_preflight(tmpdir)
            assert result is False
            captured = capsys.readouterr()
            assert "[FAIL]" in captured.err
            assert "api.env not found" in captured.err
