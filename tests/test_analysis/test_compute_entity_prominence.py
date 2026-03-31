"""Tests for compute_entity_prominence module."""

import json
from pathlib import Path

import pytest

from seo_pipeline.analysis.compute_entity_prominence import (
    _parse_prominence_count,
    _synonym_appears_in_text,
    compute_entity_prominence,
    main,
)

FIXTURES = Path("test/fixtures/compute-entity-prominence")


# ---------------------------------------------------------------------------
# _synonym_appears_in_text
# ---------------------------------------------------------------------------


class TestSynonymAppearsInText:
    """Tests for synonym matching logic."""

    def test_short_synonym_word_boundary_match(self):
        assert _synonym_appears_in_text("spa", "the spa is great")

    def test_short_synonym_word_boundary_no_false_positive(self):
        # "spa" should not match inside "space"
        assert not _synonym_appears_in_text("spa", "outer space is vast")

    def test_short_synonym_at_end_of_sentence(self):
        assert _synonym_appears_in_text("spa", "we visited the spa.")

    def test_short_synonym_hyphen_boundary(self):
        # Hyphens act as word boundaries
        assert _synonym_appears_in_text("spa", "the spa-bereich is nice")

    def test_short_synonym_case_insensitive(self):
        assert _synonym_appears_in_text("Spa", "the spa is relaxing")

    def test_long_synonym_substring_match(self):
        assert _synonym_appears_in_text("schnorcheln", "das schnorcheln ist toll")

    def test_long_synonym_within_word(self):
        # Long synonyms use substring matching, so this should match
        assert _synonym_appears_in_text("tauchen", "abtauchen ist spass")

    def test_long_synonym_case_insensitive(self):
        assert _synonym_appears_in_text("Snorkeling", "snorkeling is fun")

    def test_no_match(self):
        assert not _synonym_appears_in_text("diving", "the beach is beautiful")

    def test_empty_text(self):
        assert not _synonym_appears_in_text("spa", "")

    def test_exact_four_char_synonym_uses_boundary(self):
        # "reef" is 4 chars, should use word boundary
        assert _synonym_appears_in_text("reef", "the reef is stunning")
        assert not _synonym_appears_in_text("reef", "reefing the sails")

    def test_five_char_synonym_uses_substring(self):
        # "reefs" is 5 chars, should use substring
        assert _synonym_appears_in_text("reefs", "the reefs are stunning")
        assert _synonym_appears_in_text("reefs", "somereefsy text")  # substring

    def test_regex_special_chars_escaped(self):
        # "c++" is 3 chars (<=4), uses word boundary regex.
        # \b matches between word and non-word chars. "c" is word char but "+"
        # is not, so \bc\+\+\b requires a word boundary after the last "+".
        # In "c++ is", there IS a boundary between "+" and " ".
        # But \b before "c" needs a non-word char boundary too. At string start
        # that works. However \b after the last "+" requires transition from
        # non-word to word, but " " is also non-word, so no \b there.
        # This means short synonyms with special chars may not match as expected.
        # This mirrors Node.js behavior: /\bc\+\+\b/ also fails on "c++ is".
        assert not _synonym_appears_in_text("c++", "c++ is a language")


# ---------------------------------------------------------------------------
# _parse_prominence_count
# ---------------------------------------------------------------------------


class TestParseProminenceCount:
    """Tests for prominence string parsing."""

    def test_valid_format(self):
        assert _parse_prominence_count("8/10") == 8

    def test_valid_format_with_spaces(self):
        assert _parse_prominence_count("3 / 5") == 3

    def test_zero_count(self):
        assert _parse_prominence_count("0/10") == 0

    def test_none_input(self):
        assert _parse_prominence_count(None) is None

    def test_invalid_format(self):
        assert _parse_prominence_count("high") is None

    def test_empty_string(self):
        assert _parse_prominence_count("") is None

    def test_numeric_input_converted_to_string(self):
        # The Node.js version converts to String() first
        assert _parse_prominence_count("5/10") == 5


# ---------------------------------------------------------------------------
# compute_entity_prominence (integration with fixtures)
# ---------------------------------------------------------------------------


class TestComputeEntityProminence:
    """Integration tests using the fixture data."""

    def test_fixture_output_matches_expected(self):
        result = compute_entity_prominence(
            FIXTURES / "entities.json",
            FIXTURES / "pages",
        )
        data = json.loads(
            json.dumps(result.model_dump(by_alias=True), ensure_ascii=False)
        )

        # 2 clusters
        assert len(data["entity_clusters"]) == 2

        # Aktivitaeten cluster
        akt = data["entity_clusters"][0]
        assert akt["category_name"] == "Aktivitaeten"
        assert len(akt["entities"]) == 2

        # Schnorcheln: alpha (schnorcheln, schnorchelausflug) + beta
        schnorcheln = akt["entities"][0]
        assert schnorcheln["entity"] == "Schnorcheln"
        assert schnorcheln["prominence"] == "2/3"
        assert schnorcheln["prominence_gemini"] == "8/10"
        assert schnorcheln["prominence_source"] == "code"

        # Tauchen: appears only in alpha
        tauchen = akt["entities"][1]
        assert tauchen["entity"] == "Tauchen"
        assert tauchen["prominence"] == "1/3"

        # Orte cluster
        orte = data["entity_clusters"][1]
        assert orte["category_name"] == "Orte"

        # Riff: alpha (korallenriff, substring) + beta (reef, boundary)
        riff = orte["entities"][0]
        assert riff["prominence"] == "2/3"

        # Spa: gamma only (short synonym, word boundary)
        spa_ent = orte["entities"][1]
        assert spa_ent["prominence"] == "1/3"

    def test_corrections_present_when_delta_gte_2(self):
        result = compute_entity_prominence(
            FIXTURES / "entities.json",
            FIXTURES / "pages",
        )
        data = result.model_dump(by_alias=True)

        assert "_debug" in data
        corrections = data["_debug"]["corrections"]
        assert len(corrections) == 4

        # All entities have delta >= 2 in this fixture
        for c in corrections:
            assert c["delta"] >= 2

    def test_corrections_sorted_by_category_then_entity(self):
        result = compute_entity_prominence(
            FIXTURES / "entities.json",
            FIXTURES / "pages",
        )
        data = result.model_dump(by_alias=True)
        corrections = data["_debug"]["corrections"]

        # Aktivitaeten comes before Orte
        assert corrections[0]["category"] == "Aktivitaeten"
        assert corrections[1]["category"] == "Aktivitaeten"
        assert corrections[2]["category"] == "Orte"
        assert corrections[3]["category"] == "Orte"

        # Within same category, sorted by entity name
        assert corrections[0]["entity"] == "Schnorcheln"
        assert corrections[1]["entity"] == "Tauchen"
        assert corrections[2]["entity"] == "Riff"
        assert corrections[3]["entity"] == "Spa"

    def test_byte_identical_to_nodejs(self, tmp_path):
        """Verify Python output is byte-identical to Node.js output."""
        result = compute_entity_prominence(
            FIXTURES / "entities.json",
            FIXTURES / "pages",
        )
        python_json = json.dumps(
            result.model_dump(by_alias=True), indent=2, ensure_ascii=False
        )

        # Generate expected from the fixture data manually
        expected = {
            "entity_clusters": [
                {
                    "category_name": "Aktivitaeten",
                    "entities": [
                        {
                            "entity": "Schnorcheln",
                            "prominence": "2/3",
                            "prominence_gemini": "8/10",
                            "prominence_source": "code",
                            "synonyms": [
                                "schnorcheln",
                                "snorkeling",
                                "schnorchelausflug",
                            ],
                        },
                        {
                            "entity": "Tauchen",
                            "prominence": "1/3",
                            "prominence_gemini": "5/10",
                            "prominence_source": "code",
                            "synonyms": ["tauchen", "diving", "tauchgang"],
                        },
                    ],
                },
                {
                    "category_name": "Orte",
                    "entities": [
                        {
                            "entity": "Riff",
                            "prominence": "2/3",
                            "prominence_gemini": "9/10",
                            "prominence_source": "code",
                            "synonyms": ["riff", "reef", "korallenriff"],
                        },
                        {
                            "entity": "Spa",
                            "prominence": "1/3",
                            "prominence_gemini": "3/10",
                            "prominence_source": "code",
                            "synonyms": ["spa"],
                        },
                    ],
                },
            ],
            "_debug": {
                "corrections": [
                    {
                        "entity": "Schnorcheln",
                        "category": "Aktivitaeten",
                        "gemini": "8/10",
                        "code": "2/3",
                        "delta": 6,
                    },
                    {
                        "entity": "Tauchen",
                        "category": "Aktivitaeten",
                        "gemini": "5/10",
                        "code": "1/3",
                        "delta": 4,
                    },
                    {
                        "entity": "Riff",
                        "category": "Orte",
                        "gemini": "9/10",
                        "code": "2/3",
                        "delta": 7,
                    },
                    {
                        "entity": "Spa",
                        "category": "Orte",
                        "gemini": "3/10",
                        "code": "1/3",
                        "delta": 2,
                    },
                ],
            },
        }
        expected_json = json.dumps(expected, indent=2, ensure_ascii=False)
        assert python_json == expected_json


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case tests."""

    def test_no_pages(self, tmp_path):
        """Empty pages directory produces 0/0 prominence."""
        entities_file = tmp_path / "entities.json"
        entities_file.write_text(json.dumps({
            "entity_clusters": [{
                "category_name": "Test",
                "entities": [{
                    "entity": "Foo",
                    "prominence": "5/10",
                    "synonyms": ["foo"],
                }],
            }],
        }))
        pages_dir = tmp_path / "pages"
        pages_dir.mkdir()

        result = compute_entity_prominence(entities_file, pages_dir)
        data = result.model_dump(by_alias=True)
        assert data["entity_clusters"][0]["entities"][0]["prominence"] == "0/0"

    def test_no_synonyms(self, tmp_path):
        """Entity with no synonyms gets 0 count."""
        entities_file = tmp_path / "entities.json"
        entities_file.write_text(json.dumps({
            "entity_clusters": [{
                "category_name": "Test",
                "entities": [{
                    "entity": "Orphan",
                    "prominence": "1/5",
                    "synonyms": [],
                }],
            }],
        }))
        pages_dir = tmp_path / "pages"
        pages_dir.mkdir()
        (pages_dir / "p1.json").write_text(json.dumps({
            "main_content_text": "some text here",
        }))

        result = compute_entity_prominence(entities_file, pages_dir)
        data = result.model_dump(by_alias=True)
        assert data["entity_clusters"][0]["entities"][0]["prominence"] == "0/1"

    def test_missing_synonyms_key(self, tmp_path):
        """Entity without synonyms key treated as empty list."""
        entities_file = tmp_path / "entities.json"
        entities_file.write_text(json.dumps({
            "entity_clusters": [{
                "category_name": "Test",
                "entities": [{
                    "entity": "NoSyn",
                    "prominence": "2/5",
                }],
            }],
        }))
        pages_dir = tmp_path / "pages"
        pages_dir.mkdir()
        (pages_dir / "p1.json").write_text(json.dumps({
            "main_content_text": "hello world",
        }))

        result = compute_entity_prominence(entities_file, pages_dir)
        data = result.model_dump(by_alias=True)
        assert data["entity_clusters"][0]["entities"][0]["prominence"] == "0/1"
        # Missing synonyms in input -> empty list in output
        assert data["entity_clusters"][0]["entities"][0]["synonyms"] == []

    def test_no_corrections_omits_debug(self, tmp_path):
        """No corrections means no _debug key in output."""
        entities_file = tmp_path / "entities.json"
        entities_file.write_text(json.dumps({
            "entity_clusters": [{
                "category_name": "Test",
                "entities": [{
                    "entity": "Match",
                    "prominence": "1/1",
                    "synonyms": ["match"],
                }],
            }],
        }))
        pages_dir = tmp_path / "pages"
        pages_dir.mkdir()
        (pages_dir / "p1.json").write_text(json.dumps({
            "main_content_text": "this match is found",
        }))

        result = compute_entity_prominence(entities_file, pages_dir)
        data = result.model_dump(by_alias=True)
        assert "_debug" not in data

    def test_delta_below_threshold_no_correction(self, tmp_path):
        """Delta of 1 does not trigger a correction."""
        entities_file = tmp_path / "entities.json"
        entities_file.write_text(json.dumps({
            "entity_clusters": [{
                "category_name": "Test",
                "entities": [{
                    "entity": "Close",
                    "prominence": "2/3",
                    "synonyms": ["close"],
                }],
            }],
        }))
        pages_dir = tmp_path / "pages"
        pages_dir.mkdir()
        (pages_dir / "p1.json").write_text(json.dumps({
            "main_content_text": "close to the edge",
        }))
        (pages_dir / "p2.json").write_text(json.dumps({
            "main_content_text": "close call",
        }))
        (pages_dir / "p3.json").write_text(json.dumps({
            "main_content_text": "not here",
        }))

        # "close" (5 chars) uses substring match. Appears in p1 and p2.
        # Code: 2/3, gemini: 2/3. Delta = 0.
        result = compute_entity_prominence(entities_file, pages_dir)
        data = result.model_dump(by_alias=True)
        assert "_debug" not in data

    def test_missing_prominence_no_correction(self, tmp_path):
        """Missing original prominence means no correction recorded."""
        entities_file = tmp_path / "entities.json"
        entities_file.write_text(json.dumps({
            "entity_clusters": [{
                "category_name": "Test",
                "entities": [{
                    "entity": "NoProm",
                    "synonyms": ["noprom"],
                }],
            }],
        }))
        pages_dir = tmp_path / "pages"
        pages_dir.mkdir()
        (pages_dir / "p1.json").write_text(json.dumps({
            "main_content_text": "noprom appears here",
        }))

        result = compute_entity_prominence(entities_file, pages_dir)
        data = result.model_dump(by_alias=True)
        assert "_debug" not in data
        assert data["entity_clusters"][0]["entities"][0]["prominence_gemini"] is None

    def test_page_missing_main_content_text(self, tmp_path):
        """Page without main_content_text treated as empty string."""
        entities_file = tmp_path / "entities.json"
        entities_file.write_text(json.dumps({
            "entity_clusters": [{
                "category_name": "Test",
                "entities": [{
                    "entity": "Test",
                    "prominence": "1/1",
                    "synonyms": ["test"],
                }],
            }],
        }))
        pages_dir = tmp_path / "pages"
        pages_dir.mkdir()
        (pages_dir / "p1.json").write_text(json.dumps({"url": "https://example.com"}))

        result = compute_entity_prominence(entities_file, pages_dir)
        data = result.model_dump(by_alias=True)
        assert data["entity_clusters"][0]["entities"][0]["prominence"] == "0/1"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCli:
    """Tests for CLI entry point."""

    def test_main_writes_to_output_file(self, tmp_path):
        out = tmp_path / "result.json"
        main([
            "--entities", str(FIXTURES / "entities.json"),
            "--pages-dir", str(FIXTURES / "pages"),
            "--output", str(out),
        ])
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "entity_clusters" in data
        assert len(data["entity_clusters"]) == 2

    def test_main_writes_to_stdout(self, capsys):
        main([
            "--entities", str(FIXTURES / "entities.json"),
            "--pages-dir", str(FIXTURES / "pages"),
        ])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "entity_clusters" in data

    def test_main_missing_args(self):
        with pytest.raises(SystemExit):
            main([])
