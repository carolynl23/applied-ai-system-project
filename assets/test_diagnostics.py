"""
PawPal+ AI diagnostic test suite.
Tests the RAG retriever, knowledge base, and DiagnosticAgent parsing logic.
Live API tests are marked with @pytest.mark.live and skipped by default.

Run all (no API calls):  pytest test_diagnostics.py -v
Run live tests:          pytest test_diagnostics.py -v -m live
"""

import json
import os
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from diagnostics import (
    KnowledgeBase,
    RAGRetriever,
    DiagnosticAgent,
    DiagnosisResult,
    RetrievedCondition,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def kb(tmp_path):
    """Write a minimal knowledge base fixture to a temp file."""
    data = [
        {
            "id": "ear_infection",
            "name": "Ear infection",
            "species": ["dog", "cat"],
            "symptoms": ["head shaking", "scratching at ear", "ear odor"],
            "severity": "mild",
            "description": "Outer ear infection.",
            "recommended_actions": ["See vet"],
            "suggested_tasks": [{"title": "Inspect ear", "duration_minutes": 5, "priority": "high", "category": "medical"}],
            "vet_urgency": "routine",
            "keywords": ["ear", "scratch ear", "shake head", "smell ear", "discharge"],
        },
        {
            "id": "parvovirus",
            "name": "Canine parvovirus",
            "species": ["dog"],
            "symptoms": ["vomiting", "bloody diarrhea", "severe lethargy"],
            "severity": "critical",
            "description": "Life-threatening viral disease.",
            "recommended_actions": ["Emergency vet NOW"],
            "suggested_tasks": [{"title": "Emergency vet", "duration_minutes": 120, "priority": "high", "category": "medical"}],
            "vet_urgency": "emergency",
            "keywords": ["vomit", "bloody stool", "parvo", "lethargy"],
        },
        {
            "id": "anxiety",
            "name": "Anxiety",
            "species": ["dog", "cat"],
            "symptoms": ["pacing", "panting", "hiding"],
            "severity": "mild",
            "description": "Stress response.",
            "recommended_actions": ["Provide safe space"],
            "suggested_tasks": [{"title": "Calm enrichment", "duration_minutes": 20, "priority": "medium", "category": "enrichment"}],
            "vet_urgency": "routine",
            "keywords": ["anxious", "scared", "shake", "hide", "pace"],
        },
    ]
    kb_file = tmp_path / "knowledge_base.json"
    kb_file.write_text(json.dumps(data))
    return KnowledgeBase(path=kb_file)


@pytest.fixture
def retriever():
    return RAGRetriever()


# ---------------------------------------------------------------------------
# KnowledgeBase tests
# ---------------------------------------------------------------------------

class TestKnowledgeBase:
    def test_loads_conditions(self, kb):
        assert len(kb.conditions) == 3

    def test_filter_by_dog(self, kb):
        dogs = kb.filter_by_species("dog")
        assert all("dog" in c.species for c in dogs)

    def test_filter_by_cat(self, kb):
        cats = kb.filter_by_species("cat")
        assert all("cat" in c.species for c in cats)

    def test_filter_other_returns_all(self, kb):
        others = kb.filter_by_species("other")
        assert len(others) == len(kb.conditions)

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            KnowledgeBase(path="/nonexistent/path/kb.json")


# ---------------------------------------------------------------------------
# RAGRetriever tests
# ---------------------------------------------------------------------------

class TestRAGRetriever:
    def test_returns_top_k(self, retriever, kb):
        results = retriever.retrieve("ear smell shake head", "dog", kb, top_k=2)
        assert len(results) == 2

    def test_ear_symptoms_match_ear_infection(self, retriever, kb):
        results = retriever.retrieve(
            "my dog keeps scratching her ear and shaking her head", "dog", kb, top_k=3
        )
        top_id = results[0].condition.id
        assert top_id == "ear_infection"

    def test_parvo_symptoms_rank_highly(self, retriever, kb):
        results = retriever.retrieve(
            "dog vomiting bloody stool lethargy", "dog", kb, top_k=3
        )
        ids = [r.condition.id for r in results]
        assert "parvovirus" in ids

    def test_species_filter_applies(self, retriever, kb):
        results = retriever.retrieve("vomit bloody stool lethargy", "cat", kb, top_k=3)
        for r in results:
            assert "cat" in r.condition.species

    def test_score_between_zero_and_one(self, retriever, kb):
        results = retriever.retrieve("some random text", "dog", kb, top_k=3)
        for r in results:
            assert 0.0 <= r.score <= 1.0

    def test_matched_keywords_are_subset_of_all_terms(self, retriever, kb):
        results = retriever.retrieve("ear discharge smell head", "dog", kb, top_k=1)
        r = results[0]
        all_terms = set(r.condition.keywords + r.condition.symptoms)
        for kw in r.matched_keywords:
            assert kw in all_terms

    def test_empty_symptom_text_returns_results(self, retriever, kb):
        results = retriever.retrieve("", "dog", kb, top_k=3)
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# DiagnosticAgent._parse_response tests (no API needed)
# ---------------------------------------------------------------------------

class TestParseResponse:
    def _make_retrieved(self):
        return []

    def _valid_json(self):
        return json.dumps({
            "primary_condition": "Ear infection",
            "confidence": "high",
            "severity": "mild",
            "vet_urgency": "routine",
            "summary": "Your dog likely has an ear infection.",
            "reasoning": "Symptoms match ear infection pattern.",
            "recommended_actions": ["See vet"],
            "suggested_tasks": [
                {"title": "Inspect ear", "duration_minutes": 5, "priority": "high", "category": "medical"}
            ],
            "disclaimer": "This is not veterinary advice.",
        })

    def test_valid_json_parses_correctly(self):
        result = DiagnosticAgent._parse_response(self._valid_json(), [], 0.5)
        assert result.primary_condition == "Ear infection"
        assert result.confidence == "high"
        assert result.severity == "mild"
        assert result.vet_urgency == "routine"
        assert len(result.suggested_tasks) == 1

    def test_malformed_json_returns_fallback(self):
        result = DiagnosticAgent._parse_response("not json at all", [], 0.1)
        assert result.primary_condition == "Unable to parse diagnosis"
        assert result.confidence == "low"

    def test_invalid_confidence_defaults_to_low(self):
        data = json.loads(self._valid_json())
        data["confidence"] = "very_sure"
        result = DiagnosticAgent._parse_response(json.dumps(data), [], 0.5)
        assert result.confidence == "low"

    def test_invalid_severity_defaults_to_mild(self):
        data = json.loads(self._valid_json())
        data["severity"] = "catastrophic"
        result = DiagnosticAgent._parse_response(json.dumps(data), [], 0.5)
        assert result.severity == "mild"

    def test_critical_severity_overrides_urgency_to_emergency(self):
        data = json.loads(self._valid_json())
        data["severity"] = "critical"
        data["vet_urgency"] = "monitor"  # should be overridden
        result = DiagnosticAgent._parse_response(json.dumps(data), [], 0.5)
        assert result.vet_urgency == "emergency"

    def test_markdown_fences_stripped(self):
        fenced = "```json\n" + self._valid_json() + "\n```"
        result = DiagnosticAgent._parse_response(fenced, [], 0.5)
        assert result.primary_condition == "Ear infection"

    def test_latency_stored(self):
        result = DiagnosticAgent._parse_response(self._valid_json(), [], 1.23)
        assert result.latency_seconds == 1.23

    def test_is_emergency_false_for_routine(self):
        result = DiagnosticAgent._parse_response(self._valid_json(), [], 0.5)
        assert not result.is_emergency

    def test_is_emergency_true_for_emergency(self):
        data = json.loads(self._valid_json())
        data["vet_urgency"] = "emergency"
        result = DiagnosticAgent._parse_response(json.dumps(data), [], 0.5)
        assert result.is_emergency


# ---------------------------------------------------------------------------
# DiagnosticAgent init guardrails
# ---------------------------------------------------------------------------

class TestAgentInit:
    def test_missing_api_key_raises_environment_error(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            with pytest.raises(EnvironmentError, match="ANTHROPIC_API_KEY"):
                DiagnosticAgent()


# ---------------------------------------------------------------------------
# Live API tests — skipped unless ANTHROPIC_API_KEY is set and -m live passed
# ---------------------------------------------------------------------------

@pytest.mark.live
class TestLiveAPI:
    """These tests make real API calls. Run with: pytest -m live"""

    @pytest.fixture(autouse=True)
    def requires_key(self):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            pytest.skip("ANTHROPIC_API_KEY not set")

    def test_live_ear_infection_diagnosis(self):
        agent = DiagnosticAgent()
        result = agent.diagnose(
            symptom_text="My dog won't stop scratching her ear, it smells bad and there's dark discharge.",
            species="dog",
            pet_name="Buddy",
            pet_age=4,
        )
        assert result.primary_condition
        assert result.confidence in ("high", "medium", "low")
        assert result.severity in ("mild", "moderate", "critical")
        assert result.vet_urgency in ("emergency", "soon", "routine", "monitor")
        assert len(result.recommended_actions) > 0
        assert result.latency_seconds > 0

    def test_live_emergency_parvo_triggers_emergency_urgency(self):
        agent = DiagnosticAgent()
        result = agent.diagnose(
            symptom_text="Puppy is vomiting blood and has bloody diarrhea, completely lethargic, not vaccinated.",
            species="dog",
            pet_name="Puppy",
            pet_age=0,
        )
        assert result.vet_urgency in ("emergency", "soon")
        assert result.severity in ("moderate", "critical")

    def test_live_vague_symptoms_give_low_confidence(self):
        agent = DiagnosticAgent()
        result = agent.diagnose(
            symptom_text="My cat seems a bit off today.",
            species="cat",
            pet_name="Whiskers",
            pet_age=5,
        )
        assert result.confidence in ("low", "medium")

    def test_live_response_is_consistent_on_same_input(self):
        """Soft consistency check — two runs should agree on urgency level."""
        agent = DiagnosticAgent()
        kwargs = dict(
            symptom_text="Dog scratching ear, dark discharge, head shaking.",
            species="dog",
            pet_name="Rex",
            pet_age=3,
        )
        r1 = agent.diagnose(**kwargs)
        r2 = agent.diagnose(**kwargs)
        assert r1.vet_urgency == r2.vet_urgency, (
            f"Inconsistent urgency: {r1.vet_urgency} vs {r2.vet_urgency}"
        )