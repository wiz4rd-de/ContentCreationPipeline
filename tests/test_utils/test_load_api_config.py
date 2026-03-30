"""Tests for the load_api_config module."""

import os
import tempfile

import pytest

from seo_pipeline.utils.load_api_config import load_env


class TestLoadEnv:
    """Tests for the load_env function."""

    def test_returns_auth_and_base_for_valid_env_file(self):
        """Returns auth and base for a valid env file."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.env', delete=False, encoding='utf-8'
        ) as f:
            f.write('DATAFORSEO_AUTH=abc123base64token\n')
            f.write('DATAFORSEO_BASE=https://api.dataforseo.com/v3\n')
            f.flush()
            temp_path = f.name

        try:
            result = load_env(temp_path)
            assert result['auth'] == 'abc123base64token'
            assert result['base'] == 'https://api.dataforseo.com/v3'
        finally:
            os.unlink(temp_path)

    def test_skips_comment_lines_and_blank_lines_ignores_extra_keys(self):
        """Skips comment lines and blank lines, ignores extra keys."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.env', delete=False, encoding='utf-8'
        ) as f:
            f.write('# DataForSEO API credentials\n')
            f.write('# Set these before running any pipeline script\n')
            f.write('\n')
            f.write('DATAFORSEO_AUTH=commenttest==\n')
            f.write('# The base URL should not have a trailing slash\n')
            f.write('DATAFORSEO_BASE=https://api.dataforseo.com/v3\n')
            f.write('\n')
            f.write('EXTRA_KEY=ignored\n')
            f.flush()
            temp_path = f.name

        try:
            result = load_env(temp_path)
            assert result['auth'] == 'commenttest=='
            assert result['base'] == 'https://api.dataforseo.com/v3'
            # The returned dict should only have auth and base
            assert len(result) == 2
        finally:
            os.unlink(temp_path)

    def test_throws_with_dataforseo_auth_in_message_when_auth_key_is_missing(
        self,
    ):
        """Throws with DATAFORSEO_AUTH in message when auth key is missing."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.env', delete=False, encoding='utf-8'
        ) as f:
            f.write('DATAFORSEO_BASE=https://api.dataforseo.com/v3\n')
            f.flush()
            temp_path = f.name

        try:
            with pytest.raises(ValueError) as exc_info:
                load_env(temp_path)
            assert 'DATAFORSEO_AUTH' in str(exc_info.value)
        finally:
            os.unlink(temp_path)

    def test_throws_with_dataforseo_base_in_message_when_base_key_is_missing(
        self,
    ):
        """Throws with DATAFORSEO_BASE in message when base key is missing."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.env', delete=False, encoding='utf-8'
        ) as f:
            f.write('DATAFORSEO_AUTH=abc123base64token\n')
            f.flush()
            temp_path = f.name

        try:
            with pytest.raises(ValueError) as exc_info:
                load_env(temp_path)
            assert 'DATAFORSEO_BASE' in str(exc_info.value)
        finally:
            os.unlink(temp_path)

    def test_throws_when_both_values_are_empty_strings(self):
        """Throws when both values are empty strings."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.env', delete=False, encoding='utf-8'
        ) as f:
            f.write('DATAFORSEO_AUTH=\n')
            f.write('DATAFORSEO_BASE=\n')
            f.flush()
            temp_path = f.name

        try:
            with pytest.raises(ValueError) as exc_info:
                load_env(temp_path)
            # The first validation (auth) fires first
            assert 'DATAFORSEO_AUTH' in str(exc_info.value)
        finally:
            os.unlink(temp_path)

    def test_throws_file_not_found_when_file_does_not_exist(self):
        """Throws FileNotFoundError when file does not exist."""
        with pytest.raises(FileNotFoundError):
            load_env('/nonexistent/path/to/file.env')

    def test_is_deterministic_same_input_produces_identical_output(self):
        """Same input produces identical output (deterministic behavior)."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.env', delete=False, encoding='utf-8'
        ) as f:
            f.write('DATAFORSEO_AUTH=abc123base64token\n')
            f.write('DATAFORSEO_BASE=https://api.dataforseo.com/v3\n')
            f.flush()
            temp_path = f.name

        try:
            run1 = load_env(temp_path)
            run2 = load_env(temp_path)
            assert run1 == run2
        finally:
            os.unlink(temp_path)

    def test_handles_values_containing_equals_signs(self):
        """Handles values containing = signs (e.g. base64 tokens)."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.env', delete=False, encoding='utf-8'
        ) as f:
            f.write('DATAFORSEO_AUTH=commenttest==\n')
            f.write('DATAFORSEO_BASE=https://api.dataforseo.com/v3\n')
            f.flush()
            temp_path = f.name

        try:
            result = load_env(temp_path)
            # The trailing == must be preserved, not truncated
            assert result['auth'] == 'commenttest=='
        finally:
            os.unlink(temp_path)
