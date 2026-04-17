"""Tests for the fact-check module.

Covers: prioritization/cap, graceful LLM failure, graceful SERP failure.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from seo_pipeline.analysis.fact_check import (
    _claim_priority,
    fact_check,
    search_claim,
    search_claims_batch,
    supplement_claims,
    verify_claim,
    verify_claims_batch,
)
from seo_pipeline.llm.config import LLMConfig
from seo_pipeline.models.analysis import Claim, VerifiedClaim

# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------


def _make_claim(
    id: str, category: str, value: str = "test",
) -> Claim:
    return Claim(
        id=id,
        category=category,
        value=value,
        sentence=f"The {value} is here.",
        line=1,
        section=None,
    )


def _make_llm_config() -> LLMConfig:
    return LLMConfig(
        provider="anthropic", model="test-model", api_key="k",
    )


# -----------------------------------------------------------------------
# Prioritization tests
# -----------------------------------------------------------------------


class TestClaimPriority:
    def test_prices_costs_highest_priority(self):
        assert _claim_priority(_make_claim("c1", "prices_costs")) == 0

    def test_heights_distances(self):
        c = _make_claim("c1", "heights_distances")
        assert _claim_priority(c) == 1

    def test_dates_years(self):
        assert _claim_priority(_make_claim("c1", "dates_years")) == 2

    def test_counts(self):
        assert _claim_priority(_make_claim("c1", "counts")) == 3

    def test_measurements(self):
        assert _claim_priority(_make_claim("c1", "measurements")) == 4

    def test_geographic(self):
        assert _claim_priority(_make_claim("c1", "geographic")) == 5

    def test_unknown_category_gets_default(self):
        assert _claim_priority(_make_claim("c1", "supplemented")) == 6
        assert _claim_priority(_make_claim("c1", "other")) == 6

    def test_priority_ordering(self):
        """Stable sort by category priority."""
        claims = [
            _make_claim("c1", "geographic"),
            _make_claim("c2", "prices_costs"),
            _make_claim("c3", "counts"),
            _make_claim("c4", "prices_costs"),
            _make_claim("c5", "supplemented"),
        ]
        claims.sort(key=_claim_priority)
        ids = [c.id for c in claims]
        assert ids == ["c2", "c4", "c3", "c1", "c5"]


class TestCappingLogic:
    def test_cap_at_100(self, tmp_path):
        """fact_check processes at most 100 claims."""
        draft = tmp_path / "draft.md"
        lines = [
            f"Der Preis betraegt {i} EUR." for i in range(120)
        ]
        draft.write_text("\n".join(lines), encoding="utf-8")

        def mock_batch_search(claims, api_config, **kw):
            return {c.id: [] for c in claims}

        def mock_batch_verify(claims, snippets_map, config):
            return [
                VerifiedClaim(
                    id=c.id,
                    category=c.category,
                    value=c.value,
                    sentence=c.sentence,
                    line=c.line,
                    section=c.section,
                    verdict="correct",
                )
                for c in claims
            ]

        with (
            patch(
                "seo_pipeline.analysis.fact_check"
                ".supplement_claims",
                return_value=[],
            ),
            patch(
                "seo_pipeline.analysis.fact_check"
                ".search_claims_batch",
                side_effect=mock_batch_search,
            ),
            patch(
                "seo_pipeline.analysis.fact_check"
                ".verify_claims_batch",
                side_effect=mock_batch_verify,
            ),
        ):
            cfg = _make_llm_config()
            api = {"auth": "x", "base": "http://x"}
            result = fact_check(
                str(draft), str(tmp_path), cfg, api,
            )

        assert len(result.verified_claims) <= 100
        assert result.meta.total_claims_checked <= 100


# -----------------------------------------------------------------------
# Graceful failure tests
# -----------------------------------------------------------------------


class TestSupplementClaimsFailure:
    def test_returns_empty_on_llm_exception(self):
        """Returns [] when the LLM call fails."""
        with patch(
            "seo_pipeline.analysis.fact_check.complete",
            side_effect=RuntimeError("LLM down"),
        ):
            result = supplement_claims(
                "Some draft text", [], _make_llm_config(),
            )
        assert result == []


class TestSearchClaimFailure:
    def test_returns_empty_on_http_error(self):
        """Returns [] when the HTTP request fails."""
        with patch("httpx.Client") as mock_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(
                return_value=mock_client,
            )
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = (
                httpx.ConnectError("refused")
            )
            mock_cls.return_value = mock_client

            api = {"auth": "x", "base": "http://x"}
            result = search_claim("test query", api)
        assert result == []

    def test_returns_empty_on_invalid_json(self):
        """Returns [] when the response is not valid JSON."""
        with patch("httpx.Client") as mock_cls:
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.side_effect = ValueError("bad")
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(
                return_value=mock_client,
            )
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_resp
            mock_cls.return_value = mock_client

            api = {"auth": "x", "base": "http://x"}
            result = search_claim("test query", api)
        assert result == []


class TestVerifyClaimFailure:
    def test_returns_unverifiable_on_llm_failure(self):
        """Returns verdict='unverifiable' when LLM fails."""
        claim = _make_claim("c1", "prices_costs", "100 EUR")
        snippets = [
            {
                "title": "Price info",
                "url": "http://example.com",
                "snippet": "costs 100 EUR",
            },
        ]

        with patch(
            "seo_pipeline.analysis.fact_check.complete",
            side_effect=RuntimeError("LLM down"),
        ):
            result = verify_claim(
                claim, snippets, _make_llm_config(),
            )

        assert result.verdict == "unverifiable"
        assert result.notes == "LLM call failed"
        assert result.id == "c1"
        assert result.sources == ["http://example.com"]


class TestSearchClaimSuccess:
    def test_parses_dataforseo_response(self):
        """Extracts title, url, snippet from DataForSEO."""
        mock_data = {
            "tasks": [
                {
                    "result": [
                        {
                            "items": [
                                {
                                    "title": "Result 1",
                                    "url": "http://example.com/1",
                                    "description": "First snippet",
                                },
                                {
                                    "title": "Result 2",
                                    "url": "http://example.com/2",
                                    "description": "Second snippet",
                                },
                            ]
                        }
                    ]
                }
            ]
        }

        with patch("httpx.Client") as mock_cls:
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = mock_data
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(
                return_value=mock_client,
            )
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_resp
            mock_cls.return_value = mock_client

            api = {"auth": "x", "base": "http://x"}
            result = search_claim("test", api)

        assert len(result) == 2
        assert result[0] == {
            "title": "Result 1",
            "url": "http://example.com/1",
            "snippet": "First snippet",
        }
        # description -> snippet mapping
        assert "snippet" in result[1]
        assert "description" not in result[1]


# -----------------------------------------------------------------------
# Batch search tests (Issue #103)
# -----------------------------------------------------------------------


class TestSearchClaimsBatchMultiTask:
    def test_parses_multi_task_response(self):
        """Each task result maps to the correct claim by index."""
        claims = [
            _make_claim("c1", "prices_costs", "100 EUR"),
            _make_claim("c2", "dates_years", "2024"),
        ]
        mock_data = {
            "tasks": [
                {
                    "result": [
                        {
                            "items": [
                                {
                                    "title": "Price page",
                                    "url": "http://ex.com/1",
                                    "description": "costs 100",
                                },
                            ]
                        }
                    ]
                },
                {
                    "result": [
                        {
                            "items": [
                                {
                                    "title": "Date page",
                                    "url": "http://ex.com/2",
                                    "description": "year 2024",
                                },
                                {
                                    "title": "Date page 2",
                                    "url": "http://ex.com/3",
                                    "description": "also 2024",
                                },
                            ]
                        }
                    ]
                },
            ]
        }

        with patch("httpx.Client") as mock_cls:
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = mock_data
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(
                return_value=mock_client,
            )
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_resp
            mock_cls.return_value = mock_client

            api = {"auth": "x", "base": "http://x"}
            result = search_claims_batch(claims, api)

        assert len(result) == 2
        assert result["c1"] == [
            {
                "title": "Price page",
                "url": "http://ex.com/1",
                "snippet": "costs 100",
            },
        ]
        assert len(result["c2"]) == 2
        assert result["c2"][0]["title"] == "Date page"

    def test_sends_single_post(self):
        """All claims are sent in one HTTP POST."""
        claims = [
            _make_claim("c1", "prices_costs", "100 EUR"),
            _make_claim("c2", "dates_years", "2024"),
            _make_claim("c3", "counts", "50 items"),
        ]
        mock_data = {"tasks": [{"result": []} for _ in claims]}

        with patch("httpx.Client") as mock_cls:
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = mock_data
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(
                return_value=mock_client,
            )
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_resp
            mock_cls.return_value = mock_client

            api = {"auth": "x", "base": "http://x"}
            search_claims_batch(claims, api)

            # Exactly one POST call
            assert mock_client.post.call_count == 1
            # Payload has 3 entries
            call_kwargs = mock_client.post.call_args
            payload = call_kwargs.kwargs.get(
                "json", call_kwargs[1].get("json"),
            )
            assert len(payload) == 3


class TestSearchClaimsBatchPartialFailure:
    def test_partial_task_failures(self):
        """Successful tasks return results; failed ones return []."""
        claims = [
            _make_claim("c1", "prices_costs", "100 EUR"),
            _make_claim("c2", "dates_years", "2024"),
        ]
        mock_data = {
            "tasks": [
                {
                    "result": [
                        {
                            "items": [
                                {
                                    "title": "Found",
                                    "url": "http://ex.com",
                                    "description": "snippet",
                                },
                            ]
                        }
                    ]
                },
                {
                    # Empty result = task failed
                    "result": []
                },
            ]
        }

        with patch("httpx.Client") as mock_cls:
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = mock_data
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(
                return_value=mock_client,
            )
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_resp
            mock_cls.return_value = mock_client

            api = {"auth": "x", "base": "http://x"}
            result = search_claims_batch(claims, api)

        assert len(result["c1"]) == 1
        assert result["c2"] == []


class TestSearchClaimsBatchHttpFailure:
    def test_full_http_failure_returns_empty_dict(self):
        """Returns {} when the HTTP request fails entirely."""
        claims = [
            _make_claim("c1", "prices_costs", "100 EUR"),
        ]

        with patch("httpx.Client") as mock_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(
                return_value=mock_client,
            )
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = (
                httpx.ConnectError("refused")
            )
            mock_cls.return_value = mock_client

            api = {"auth": "x", "base": "http://x"}
            result = search_claims_batch(claims, api)

        assert result == {}

    def test_empty_claims_returns_empty_dict(self):
        """Returns {} immediately for empty claims list."""
        api = {"auth": "x", "base": "http://x"}
        result = search_claims_batch([], api)
        assert result == {}


class TestFactCheckCorrections:
    def test_corrections_applied_to_draft(self, tmp_path):
        """Replaces incorrect claim values in the draft."""
        draft = tmp_path / "draft.md"
        draft.write_text(
            "Der Preis betraegt 100 EUR fuer das Ticket.",
            encoding="utf-8",
        )

        def mock_batch_search(claims, api_config, **kw):
            return {c.id: [] for c in claims}

        def mock_batch_verify(claims, snippets_map, config):
            return [
                VerifiedClaim(
                    id=c.id,
                    category=c.category,
                    value=c.value,
                    sentence=c.sentence,
                    line=c.line,
                    section=c.section,
                    verdict="incorrect",
                    corrected_value="120 EUR",
                )
                for c in claims
            ]

        with (
            patch(
                "seo_pipeline.analysis.fact_check"
                ".supplement_claims",
                return_value=[],
            ),
            patch(
                "seo_pipeline.analysis.fact_check"
                ".search_claims_batch",
                side_effect=mock_batch_search,
            ),
            patch(
                "seo_pipeline.analysis.fact_check"
                ".verify_claims_batch",
                side_effect=mock_batch_verify,
            ),
        ):
            cfg = _make_llm_config()
            api = {"auth": "x", "base": "http://x"}
            result = fact_check(
                str(draft), str(tmp_path), cfg, api,
            )

        corrected = draft.read_text(encoding="utf-8")
        assert "120 EUR" in corrected
        assert result.meta.corrections_applied >= 1


class TestFactCheckReports:
    def test_writes_json_and_md_reports(self, tmp_path):
        """Writes both JSON and Markdown report files."""
        draft = tmp_path / "draft.md"
        draft.write_text(
            "Der Preis betraegt 50 EUR.", encoding="utf-8",
        )

        def mock_batch_search(claims, api_config, **kw):
            return {c.id: [] for c in claims}

        def mock_batch_verify(claims, snippets_map, config):
            return [
                VerifiedClaim(
                    id=c.id,
                    category=c.category,
                    value=c.value,
                    sentence=c.sentence,
                    line=c.line,
                    section=c.section,
                    verdict="correct",
                )
                for c in claims
            ]

        with (
            patch(
                "seo_pipeline.analysis.fact_check"
                ".supplement_claims",
                return_value=[],
            ),
            patch(
                "seo_pipeline.analysis.fact_check"
                ".search_claims_batch",
                side_effect=mock_batch_search,
            ),
            patch(
                "seo_pipeline.analysis.fact_check"
                ".verify_claims_batch",
                side_effect=mock_batch_verify,
            ),
        ):
            cfg = _make_llm_config()
            api = {"auth": "x", "base": "http://x"}
            fact_check(str(draft), str(tmp_path), cfg, api)

        json_path = tmp_path / "fact-check-report.json"
        md_path = tmp_path / "fact-check-report.md"
        assert json_path.exists()
        assert md_path.exists()

        md = md_path.read_text(encoding="utf-8")
        assert "Fact-Check Report" in md
        assert "Verified Claims" in md


# -----------------------------------------------------------------------
# Batch verify tests (Issue #104)
# -----------------------------------------------------------------------


class TestVerifyClaimsBatchSuccess:
    def test_batch_of_3_returns_correct_verdicts(self):
        """Single LLM call verifies 3 claims with correct mapping."""
        claims = [
            _make_claim("c1", "prices_costs", "100 EUR"),
            _make_claim("c2", "dates_years", "2024"),
            _make_claim("c3", "counts", "50 items"),
        ]
        snippets_map = {
            "c1": [
                {
                    "title": "Price",
                    "url": "http://ex.com/1",
                    "snippet": "costs 100",
                },
            ],
            "c2": [
                {
                    "title": "Date",
                    "url": "http://ex.com/2",
                    "snippet": "year 2024",
                },
            ],
            "c3": [],
        }

        # Mock LLM to return batch verdicts
        from seo_pipeline.analysis.fact_check import (
            _BatchVerdictItem,
            _BatchVerdictResponse,
        )

        mock_response = _BatchVerdictResponse(
            verdicts=[
                _BatchVerdictItem(
                    claim_id="c1",
                    verdict="correct",
                    corrected_value=None,
                    notes="Price confirmed",
                ),
                _BatchVerdictItem(
                    claim_id="c2",
                    verdict="incorrect",
                    corrected_value="2025",
                    notes="Date is wrong",
                ),
                _BatchVerdictItem(
                    claim_id="c3",
                    verdict="unverifiable",
                    corrected_value=None,
                    notes=None,
                ),
            ]
        )

        with patch(
            "seo_pipeline.analysis.fact_check.complete",
            return_value=mock_response,
        ):
            result = verify_claims_batch(
                claims, snippets_map, _make_llm_config(),
            )

        assert len(result) == 3
        assert result[0].id == "c1"
        assert result[0].verdict == "correct"
        assert result[0].notes == "Price confirmed"
        assert result[0].sources == ["http://ex.com/1"]
        assert result[1].id == "c2"
        assert result[1].verdict == "incorrect"
        assert result[1].corrected_value == "2025"
        assert result[2].id == "c3"
        assert result[2].verdict == "unverifiable"


class TestVerifyClaimsBatchLLMFailure:
    def test_returns_all_unverifiable_on_failure(self):
        """All claims returned as unverifiable when LLM fails."""
        claims = [
            _make_claim("c1", "prices_costs", "100 EUR"),
            _make_claim("c2", "dates_years", "2024"),
        ]
        snippets_map = {
            "c1": [
                {
                    "title": "Price",
                    "url": "http://ex.com/1",
                    "snippet": "costs 100",
                },
            ],
            "c2": [],
        }

        with patch(
            "seo_pipeline.analysis.fact_check.complete",
            side_effect=RuntimeError("LLM down"),
        ):
            result = verify_claims_batch(
                claims, snippets_map, _make_llm_config(),
            )

        assert len(result) == 2
        assert all(r.verdict == "unverifiable" for r in result)
        assert all(
            r.notes == "LLM batch call failed" for r in result
        )
        assert result[0].sources == ["http://ex.com/1"]
        assert result[1].sources == []


class TestVerifyClaimsBatchMissingIDs:
    def test_missing_claim_ids_handled_gracefully(self):
        """Claims missing from LLM response get unverifiable."""
        claims = [
            _make_claim("c1", "prices_costs", "100 EUR"),
            _make_claim("c2", "dates_years", "2024"),
            _make_claim("c3", "counts", "50 items"),
        ]
        snippets_map = {"c1": [], "c2": [], "c3": []}

        from seo_pipeline.analysis.fact_check import (
            _BatchVerdictItem,
            _BatchVerdictResponse,
        )

        # LLM only returns verdict for c1, omits c2 and c3
        mock_response = _BatchVerdictResponse(
            verdicts=[
                _BatchVerdictItem(
                    claim_id="c1",
                    verdict="correct",
                    corrected_value=None,
                    notes=None,
                ),
            ]
        )

        with patch(
            "seo_pipeline.analysis.fact_check.complete",
            return_value=mock_response,
        ):
            result = verify_claims_batch(
                claims, snippets_map, _make_llm_config(),
            )

        assert len(result) == 3
        assert result[0].verdict == "correct"
        assert result[1].verdict == "unverifiable"
        assert result[1].notes == "Missing from batch response"
        assert result[2].verdict == "unverifiable"
        assert result[2].notes == "Missing from batch response"


# -----------------------------------------------------------------------
# Orchestration tests (Issue #106)
# -----------------------------------------------------------------------


class TestFactCheckUsesBatchSearch:
    def test_calls_search_claims_batch(self, tmp_path):
        """fact_check calls search_claims_batch, not search_claim."""
        draft = tmp_path / "draft.md"
        draft.write_text(
            "Der Preis betraegt 50 EUR.", encoding="utf-8",
        )

        batch_search_called = []

        def mock_batch_search(claims, api_config, **kw):
            batch_search_called.append(len(claims))
            return {c.id: [] for c in claims}

        def mock_batch_verify(claims, snippets_map, config):
            return [
                VerifiedClaim(
                    id=c.id,
                    category=c.category,
                    value=c.value,
                    sentence=c.sentence,
                    line=c.line,
                    section=c.section,
                    verdict="correct",
                )
                for c in claims
            ]

        with (
            patch(
                "seo_pipeline.analysis.fact_check"
                ".supplement_claims",
                return_value=[],
            ),
            patch(
                "seo_pipeline.analysis.fact_check"
                ".search_claims_batch",
                side_effect=mock_batch_search,
            ),
            patch(
                "seo_pipeline.analysis.fact_check"
                ".verify_claims_batch",
                side_effect=mock_batch_verify,
            ),
        ):
            cfg = _make_llm_config()
            api = {"auth": "x", "base": "http://x"}
            fact_check(str(draft), str(tmp_path), cfg, api)

        # search_claims_batch called exactly once
        assert len(batch_search_called) == 1


class TestFactCheckChunkedVerification:
    def test_chunks_claims_into_groups_of_10(self, tmp_path):
        """Claims are verified in chunks of ~10."""
        draft = tmp_path / "draft.md"
        lines = [
            f"Der Preis betraegt {i} EUR." for i in range(25)
        ]
        draft.write_text("\n".join(lines), encoding="utf-8")

        chunk_sizes: list[int] = []

        def mock_batch_search(claims, api_config, **kw):
            return {c.id: [] for c in claims}

        def mock_batch_verify(claims, snippets_map, config):
            chunk_sizes.append(len(claims))
            return [
                VerifiedClaim(
                    id=c.id,
                    category=c.category,
                    value=c.value,
                    sentence=c.sentence,
                    line=c.line,
                    section=c.section,
                    verdict="correct",
                )
                for c in claims
            ]

        with (
            patch(
                "seo_pipeline.analysis.fact_check"
                ".supplement_claims",
                return_value=[],
            ),
            patch(
                "seo_pipeline.analysis.fact_check"
                ".search_claims_batch",
                side_effect=mock_batch_search,
            ),
            patch(
                "seo_pipeline.analysis.fact_check"
                ".verify_claims_batch",
                side_effect=mock_batch_verify,
            ),
        ):
            cfg = _make_llm_config()
            api = {"auth": "x", "base": "http://x"}
            result = fact_check(
                str(draft), str(tmp_path), cfg, api,
            )

        # With ~25 claims, expect 3 chunks (10, 10, 5)
        assert len(chunk_sizes) >= 2
        assert all(s <= 10 for s in chunk_sizes)
        total_verified = sum(chunk_sizes)
        assert total_verified == len(result.verified_claims)


class TestFactCheckBatchFallback:
    def test_fallback_to_per_claim_on_batch_failure(self, tmp_path):
        """When batch verify raises, falls back to per-claim."""
        draft = tmp_path / "draft.md"
        # 5 claims = 1 chunk, so fallback covers all
        lines = [
            f"Der Preis betraegt {i} EUR." for i in range(5)
        ]
        draft.write_text("\n".join(lines), encoding="utf-8")

        per_claim_calls: list[str] = []

        def mock_batch_search(claims, api_config, **kw):
            return {c.id: [] for c in claims}

        def mock_batch_verify(claims, snippets_map, config):
            raise RuntimeError("LLM batch failed")

        def mock_verify_single(claim, snippets, config):
            per_claim_calls.append(claim.id)
            return VerifiedClaim(
                id=claim.id,
                category=claim.category,
                value=claim.value,
                sentence=claim.sentence,
                line=claim.line,
                section=claim.section,
                verdict="unverifiable",
                notes="Fallback",
            )

        with (
            patch(
                "seo_pipeline.analysis.fact_check"
                ".supplement_claims",
                return_value=[],
            ),
            patch(
                "seo_pipeline.analysis.fact_check"
                ".search_claims_batch",
                side_effect=mock_batch_search,
            ),
            patch(
                "seo_pipeline.analysis.fact_check"
                ".verify_claims_batch",
                side_effect=mock_batch_verify,
            ),
            patch(
                "seo_pipeline.analysis.fact_check"
                ".verify_claim",
                side_effect=mock_verify_single,
            ),
        ):
            cfg = _make_llm_config()
            api = {"auth": "x", "base": "http://x"}
            result = fact_check(
                str(draft), str(tmp_path), cfg, api,
            )

        # All claims verified via per-claim fallback
        assert len(per_claim_calls) == len(result.verified_claims)
        assert all(
            vc.notes == "Fallback"
            for vc in result.verified_claims
        )

    def test_partial_chunk_fallback(self, tmp_path):
        """Only the failing chunk falls back; others use batch."""
        draft = tmp_path / "draft.md"
        # 15 claims = 2 chunks (10, 5)
        lines = [
            f"Der Preis betraegt {i} EUR." for i in range(15)
        ]
        draft.write_text("\n".join(lines), encoding="utf-8")

        batch_call_count = [0]
        per_claim_calls: list[str] = []

        def mock_batch_search(claims, api_config, **kw):
            return {c.id: [] for c in claims}

        def mock_batch_verify(claims, snippets_map, config):
            batch_call_count[0] += 1
            # First chunk succeeds, second chunk fails
            if batch_call_count[0] == 2:
                raise RuntimeError("LLM batch failed")
            return [
                VerifiedClaim(
                    id=c.id,
                    category=c.category,
                    value=c.value,
                    sentence=c.sentence,
                    line=c.line,
                    section=c.section,
                    verdict="correct",
                    notes="batch",
                )
                for c in claims
            ]

        def mock_verify_single(claim, snippets, config):
            per_claim_calls.append(claim.id)
            return VerifiedClaim(
                id=claim.id,
                category=claim.category,
                value=claim.value,
                sentence=claim.sentence,
                line=claim.line,
                section=claim.section,
                verdict="unverifiable",
                notes="fallback",
            )

        with (
            patch(
                "seo_pipeline.analysis.fact_check"
                ".supplement_claims",
                return_value=[],
            ),
            patch(
                "seo_pipeline.analysis.fact_check"
                ".search_claims_batch",
                side_effect=mock_batch_search,
            ),
            patch(
                "seo_pipeline.analysis.fact_check"
                ".verify_claims_batch",
                side_effect=mock_batch_verify,
            ),
            patch(
                "seo_pipeline.analysis.fact_check"
                ".verify_claim",
                side_effect=mock_verify_single,
            ),
        ):
            cfg = _make_llm_config()
            api = {"auth": "x", "base": "http://x"}
            result = fact_check(
                str(draft), str(tmp_path), cfg, api,
            )

        total = len(result.verified_claims)
        assert total > 0
        # First chunk (10) used batch, second chunk used fallback
        batch_results = [
            vc for vc in result.verified_claims
            if vc.notes == "batch"
        ]
        fallback_results = [
            vc for vc in result.verified_claims
            if vc.notes == "fallback"
        ]
        assert len(batch_results) == 10
        assert len(fallback_results) == total - 10
        assert len(per_claim_calls) == total - 10
