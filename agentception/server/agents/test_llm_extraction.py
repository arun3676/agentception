"""
Unit tests for LLM extraction helpers:
- needs_llm_extraction()
- extract_with_llm() (mocked)
- extract_job_entities() (extraction ladder)
- extract_job_entities_cached() (caching layer)
"""
import pytest
import asyncio
import os
import sys

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from server.agents.rag_companies import (
    needs_llm_extraction, 
    extract_with_llm, 
    JOB_ENTITY_SCHEMA,
    extract_job_entities,
    extract_job_entities_cached,
    _extraction_cache
)


class TestNeedsLLMExtraction:
    """Test the heuristic uncertainty detection."""

    def test_missing_company_needs_llm(self):
        """Empty or None company should trigger LLM."""
        assert needs_llm_extraction("", "Software Engineer", "https://example.com") is True
        assert needs_llm_extraction(None, "Software Engineer", "https://example.com") is True

    def test_missing_title_needs_llm(self):
        """Empty or None title should trigger LLM."""
        assert needs_llm_extraction("Acme Corp", "", "https://example.com") is True
        assert needs_llm_extraction("Acme Corp", None, "https://example.com") is True

    def test_ats_vendor_name_needs_llm(self):
        """ATS vendor names as company should trigger LLM."""
        ats_vendors = ['lever', 'greenhouse', 'ashby', 'workday', 'workable', 'icims', 'jobvite']
        for vendor in ats_vendors:
            assert needs_llm_extraction(vendor, "Software Engineer", "https://example.com") is True
            assert needs_llm_extraction(vendor.upper(), "Software Engineer", "https://example.com") is True

    def test_generic_company_names_need_llm(self):
        """Generic names like 'jobs', 'careers' should trigger LLM."""
        assert needs_llm_extraction("jobs", "Software Engineer", "https://example.com") is True
        assert needs_llm_extraction("careers", "Software Engineer", "https://example.com") is True
        assert needs_llm_extraction("hiring", "Software Engineer", "https://example.com") is True

    def test_short_company_name_needs_llm(self):
        """Very short company names (< 2 chars) should trigger LLM."""
        assert needs_llm_extraction("A", "Software Engineer", "https://example.com") is True

    def test_valid_extraction_no_llm(self):
        """Valid company and title should NOT trigger LLM."""
        assert needs_llm_extraction("Acme Corp", "Software Engineer", "https://example.com") is False
        assert needs_llm_extraction("OpenAI", "ML Engineer", "https://openai.com/jobs") is False
        assert needs_llm_extraction("Stripe", "Backend Developer", "https://stripe.com") is False

    def test_edge_case_two_char_company(self):
        """Two-char company names should be valid (e.g., 'HP', 'GE')."""
        assert needs_llm_extraction("HP", "Software Engineer", "https://hp.com") is False
        assert needs_llm_extraction("GE", "Data Scientist", "https://ge.com") is False


class TestJobEntitySchema:
    """Test the JSON schema structure."""

    def test_schema_has_required_fields(self):
        """Schema should have all required fields."""
        assert "company" in JOB_ENTITY_SCHEMA["properties"]
        assert "title" in JOB_ENTITY_SCHEMA["properties"]
        assert "location" in JOB_ENTITY_SCHEMA["properties"]
        assert "description" in JOB_ENTITY_SCHEMA["properties"]
        assert "is_remote" in JOB_ENTITY_SCHEMA["properties"]

    def test_schema_required_list(self):
        """All fields should be required."""
        assert set(JOB_ENTITY_SCHEMA["required"]) == {"company", "title", "location", "description", "is_remote"}

    def test_schema_no_additional_properties(self):
        """Schema should not allow additional properties."""
        assert JOB_ENTITY_SCHEMA["additionalProperties"] is False


class TestExtractWithLLM:
    """Test the LLM extraction function (mocked)."""

    def test_raises_without_api_key(self):
        """Should raise RuntimeError if OPENAI_API_KEY is not set."""
        # Temporarily unset the key
        original_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not set"):
                asyncio.run(extract_with_llm(
                    "https://jobs.lever.co/acme/123",
                    "Software Engineer at Acme",
                    "Join our team..."
                ))
        finally:
            if original_key:
                os.environ["OPENAI_API_KEY"] = original_key


class TestExtractionLadder:
    """Test the extraction ladder (extract_job_entities)."""

    def test_heuristic_extraction_for_valid_url(self):
        """Valid ATS URL should use heuristic extraction."""
        original_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            result = asyncio.run(extract_job_entities(
                "https://jobs.lever.co/acme/12345",
                "Software Engineer at Acme",
                "Join our engineering team..."
            ))
            assert result["company"] == "Acme"
            assert result["extraction_method"] == "heuristic"
        finally:
            if original_key:
                os.environ["OPENAI_API_KEY"] = original_key

    def test_fallback_when_no_api_key(self):
        """Should fallback to heuristic with needs_review when LLM unavailable."""
        original_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            result = asyncio.run(extract_job_entities(
                "https://jobs.lever.co/lever/12345",  # "lever" triggers LLM need
                "Job Opening",
                "Some snippet..."
            ))
            # Should fallback since no API key
            assert result["extraction_method"] == "heuristic_fallback"
            assert result.get("needs_review") is True
        finally:
            if original_key:
                os.environ["OPENAI_API_KEY"] = original_key

    def test_greenhouse_url_extraction(self):
        """Greenhouse URL should extract company correctly."""
        original_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            result = asyncio.run(extract_job_entities(
                "https://boards.greenhouse.io/stripe/jobs/12345",
                "Backend Engineer at Stripe",
                "Build payment infrastructure..."
            ))
            assert result["company"] == "Stripe"
            assert result["extraction_method"] == "heuristic"
        finally:
            if original_key:
                os.environ["OPENAI_API_KEY"] = original_key


class TestExtractionCache:
    """Test the caching layer."""

    def test_cache_stores_result(self):
        """First call should store result in cache."""
        original_key = os.environ.pop("OPENAI_API_KEY", None)
        # Clear cache first
        _extraction_cache.clear()
        try:
            url = "https://jobs.lever.co/testcompany/99999"
            result = asyncio.run(extract_job_entities_cached(
                url,
                "Test Engineer at TestCompany",
                "Test snippet..."
            ))
            
            assert url in _extraction_cache
            assert result["company"] == "Testcompany"
        finally:
            if original_key:
                os.environ["OPENAI_API_KEY"] = original_key

    def test_cache_returns_cached_result(self):
        """Second call should return cached result with from_cache flag."""
        # Clear and populate cache
        _extraction_cache.clear()
        
        url = "https://jobs.lever.co/cachedcompany/11111"
        
        # First call
        result1 = asyncio.run(extract_job_entities_cached(url, "Engineer", "Snippet"))
        assert result1.get("from_cache") is None or result1.get("from_cache") is False
        
        # Second call should be from cache
        result2 = asyncio.run(extract_job_entities_cached(url, "Engineer", "Snippet"))
        assert result2.get("from_cache") is True


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
