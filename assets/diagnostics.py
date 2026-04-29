"""
PawPal+ AI diagnostic layer.

Components
----------
KnowledgeBase   Loads and indexes the JSON condition library.
RAGRetriever    Scores symptom text against conditions (keyword overlap).
DiagnosisResult Structured output from the AI agent.
DiagnosticAgent Sends retrieved context + symptoms to Claude; parses JSON output.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import anthropic

# ---------------------------------------------------------------------------
# Logging setup — every API call and retrieval step is recorded
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler("pawpal.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("pawpal")


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------

@dataclass
class Condition:
    """One entry from knowledge_base.json."""
    id: str
    name: str
    species: list[str]
    symptoms: list[str]
    severity: str
    description: str
    recommended_actions: list[str]
    suggested_tasks: list[dict]
    vet_urgency: str
    keywords: list[str]

    @classmethod
    def from_dict(cls, d: dict) -> "Condition":
        return cls(
            id=d["id"],
            name=d["name"],
            species=d["species"],
            symptoms=d["symptoms"],
            severity=d["severity"],
            description=d["description"],
            recommended_actions=d["recommended_actions"],
            suggested_tasks=d["suggested_tasks"],
            vet_urgency=d["vet_urgency"],
            keywords=d["keywords"],
        )


class KnowledgeBase:
    """Loads conditions from a JSON file."""

    def __init__(self, path: str | Path = "knowledge_base.json") -> None:
        self.path = Path(path)
        self.conditions: list[Condition] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            logger.error("Knowledge base not found at %s", self.path)
            raise FileNotFoundError(f"Knowledge base not found: {self.path}")
        with open(self.path, encoding="utf-8") as f:
            raw = json.load(f)
        self.conditions = [Condition.from_dict(d) for d in raw]
        logger.info("Loaded %d conditions from %s", len(self.conditions), self.path)

    def filter_by_species(self, species: str) -> list[Condition]:
        """Return only conditions applicable to this species."""
        if species not in ("dog", "cat"):
            return self.conditions  # "other" — return all
        return [c for c in self.conditions if species in c.species]


# ---------------------------------------------------------------------------
# RAG retriever — keyword-overlap scoring (no embeddings required)
# ---------------------------------------------------------------------------

@dataclass
class RetrievedCondition:
    condition: Condition
    score: float        # 0–1 relevance score
    matched_keywords: list[str]


class RAGRetriever:
    """
    Scores each condition against the user's symptom text using
    keyword overlap. Returns top-k conditions sorted by score.

    This is a lightweight retrieval approach suitable for a local
    knowledge base. It can be replaced with vector similarity
    (e.g. OpenAI embeddings or sentence-transformers) if needed.
    """

    def retrieve(
        self,
        symptom_text: str,
        species: str,
        knowledge_base: KnowledgeBase,
        top_k: int = 3,
    ) -> list[RetrievedCondition]:
        """Return the top_k most relevant conditions for the symptom text."""
        text_lower = symptom_text.lower()
        candidates = knowledge_base.filter_by_species(species)
        scored: list[RetrievedCondition] = []

        for condition in candidates:
            all_terms = set(condition.keywords + condition.symptoms)
            matched = [t for t in all_terms if self._term_in_text(t, text_lower)]
            score = len(matched) / max(len(all_terms), 1)
            scored.append(RetrievedCondition(condition, round(score, 3), matched))

        scored.sort(key=lambda r: r.score, reverse=True)
        top = scored[:top_k]

        logger.info(
            "RAG retrieval | species=%s | top-%d: %s",
            species,
            top_k,
            [(r.condition.id, r.score) for r in top],
        )
        return top

    @staticmethod
    def _term_in_text(term: str, text: str) -> bool:
        """Check if a multi-word term appears as a substring."""
        return term.lower() in text


# ---------------------------------------------------------------------------
# Diagnosis result
# ---------------------------------------------------------------------------

@dataclass
class DiagnosisResult:
    """Structured output from the AI diagnostic agent."""

    # Core fields from AI
    primary_condition: str
    confidence: str          # "high" | "medium" | "low"
    severity: str            # "mild" | "moderate" | "critical"
    vet_urgency: str         # "emergency" | "soon" | "routine" | "monitor"
    summary: str
    reasoning: str
    recommended_actions: list[str]
    suggested_tasks: list[dict]
    disclaimer: str

    # Metadata
    retrieved_conditions: list[RetrievedCondition] = field(default_factory=list)
    raw_response: str = ""
    latency_seconds: float = 0.0

    @property
    def is_emergency(self) -> bool:
        return self.vet_urgency == "emergency"

    @property
    def severity_emoji(self) -> str:
        return {"mild": "🟢", "moderate": "🟡", "critical": "🔴"}.get(self.severity, "⚪")

    @property
    def urgency_label(self) -> str:
        return {
            "emergency": "🚨 Emergency — go to vet NOW",
            "soon": "⚠️ See vet within 24–48 hours",
            "routine": "📋 Schedule routine vet appointment",
            "monitor": "👁 Monitor at home for now",
        }.get(self.vet_urgency, self.vet_urgency)


# ---------------------------------------------------------------------------
# Diagnostic agent
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are PawPal+, a veterinary triage assistant. You help pet owners
understand potential health issues based on symptoms they describe.

You will be given:
1. Basic pet information (species, age, name)
2. The owner's symptom description
3. A set of CANDIDATE CONDITIONS retrieved from a veterinary knowledge base

Your job is to reason carefully over the candidate conditions and the symptoms,
then produce a structured JSON diagnosis. You must ALWAYS respond with valid JSON only —
no preamble, no markdown fences, no extra text.

CRITICAL RULES:
- You are a triage aid, NOT a replacement for veterinary care. Always include a disclaimer.
- For any emergency symptoms (collapse, seizure, difficulty breathing, severe bleeding,
  suspected poisoning, inability to urinate), set vet_urgency to "emergency".
- Confidence must reflect genuine uncertainty — use "low" if symptoms are vague.
- Suggested tasks should be actionable today, safe to do at home, and appropriate to severity.

OUTPUT SCHEMA (respond with this JSON and nothing else):
{
  "primary_condition": "string — most likely condition name",
  "confidence": "high | medium | low",
  "severity": "mild | moderate | critical",
  "vet_urgency": "emergency | soon | routine | monitor",
  "summary": "string — 2-3 sentence plain-English summary for the owner",
  "reasoning": "string — why you selected this condition over others",
  "recommended_actions": ["string", ...],
  "suggested_tasks": [
    {"title": "string", "duration_minutes": int, "priority": "high|medium|low", "category": "string"}
  ],
  "disclaimer": "string — reminder that this is not veterinary advice"
}"""


class DiagnosticAgent:
    """
    Calls the Anthropic API with RAG-retrieved context injected into the prompt.
    Returns a parsed DiagnosisResult.
    """

    MODEL = "claude-sonnet-4-20250514"
    MAX_TOKENS = 1000

    def __init__(self) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Set it with: export ANTHROPIC_API_KEY=your_key_here"
            )
        self.client = anthropic.Anthropic(api_key=api_key)
        self.retriever = RAGRetriever()
        self.kb = KnowledgeBase()

    def diagnose(
        self,
        symptom_text: str,
        species: str,
        pet_name: str,
        pet_age: Optional[int],
    ) -> DiagnosisResult:
        """
        Full agentic pipeline:
        1. Retrieve relevant conditions (RAG)
        2. Inject context into prompt
        3. Call AI model
        4. Parse structured output
        5. Validate and return DiagnosisResult
        """
        # --- Step 1: Guardrail — block empty input ---
        if not symptom_text or len(symptom_text.strip()) < 5:
            raise ValueError("Please describe at least one symptom.")

        # --- Step 2: RAG retrieval ---
        retrieved = self.retriever.retrieve(symptom_text, species, self.kb, top_k=3)

        # --- Step 3: Build context block ---
        context_block = self._format_context(retrieved)

        # --- Step 4: Build user message ---
        pet_desc = f"{pet_name}, a {species}"
        if pet_age is not None:
            pet_desc += f" aged {pet_age} year(s)"

        user_message = (
            f"Pet: {pet_desc}\n\n"
            f"Owner's description: {symptom_text}\n\n"
            f"Candidate conditions from knowledge base:\n{context_block}"
        )

        logger.info(
            "Calling AI | pet=%s species=%s age=%s | symptoms=%s",
            pet_name, species, pet_age,
            symptom_text[:80] + ("..." if len(symptom_text) > 80 else ""),
        )

        # --- Step 5: API call ---
        start = time.perf_counter()
        try:
            response = self.client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            latency = round(time.perf_counter() - start, 2)
            raw = response.content[0].text
            logger.info("AI response received | latency=%.2fs | tokens_used=%d",
                        latency, response.usage.input_tokens + response.usage.output_tokens)
        except anthropic.APIError as e:
            logger.error("Anthropic API error: %s", e)
            raise RuntimeError(f"AI service error: {e}") from e

        # --- Step 6: Parse structured output ---
        result = self._parse_response(raw, retrieved, latency)
        logger.info(
            "Diagnosis complete | condition=%s | severity=%s | urgency=%s | confidence=%s",
            result.primary_condition, result.severity,
            result.vet_urgency, result.confidence,
        )
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_context(retrieved: list[RetrievedCondition]) -> str:
        """Format retrieved conditions as a readable context block for the prompt."""
        if not retrieved:
            return "No strong matches found in knowledge base. Reason from general veterinary knowledge."
        parts = []
        for i, r in enumerate(retrieved, 1):
            c = r.condition
            parts.append(
                f"{i}. {c.name} (relevance score: {r.score:.2f})\n"
                f"   Species: {', '.join(c.species)}\n"
                f"   Severity: {c.severity} | Vet urgency: {c.vet_urgency}\n"
                f"   Key symptoms: {', '.join(c.symptoms[:6])}\n"
                f"   Description: {c.description}\n"
                f"   Matched terms: {', '.join(r.matched_keywords) if r.matched_keywords else 'none'}"
            )
        return "\n\n".join(parts)

    @staticmethod
    def _parse_response(
        raw: str,
        retrieved: list[RetrievedCondition],
        latency: float,
    ) -> DiagnosisResult:
        """Parse and validate the AI's JSON output. Falls back gracefully on parse errors."""
        # Strip markdown fences if model adds them despite instructions
        cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("JSON parse failed: %s | raw=%s", e, raw[:200])
            # Graceful fallback so the app never crashes on a bad response
            return DiagnosisResult(
                primary_condition="Unable to parse diagnosis",
                confidence="low",
                severity="mild",
                vet_urgency="routine",
                summary="The AI returned an unexpected response. Please try again or consult your vet.",
                reasoning=raw[:500],
                recommended_actions=["Please consult your veterinarian directly."],
                suggested_tasks=[],
                disclaimer="This tool is not a substitute for professional veterinary advice.",
                retrieved_conditions=retrieved,
                raw_response=raw,
                latency_seconds=latency,
            )

        # Validate required fields with safe defaults
        valid_confidences = {"high", "medium", "low"}
        valid_severities = {"mild", "moderate", "critical"}
        valid_urgencies = {"emergency", "soon", "routine", "monitor"}

        confidence = data.get("confidence", "low")
        if confidence not in valid_confidences:
            confidence = "low"

        severity = data.get("severity", "mild")
        if severity not in valid_severities:
            severity = "mild"

        vet_urgency = data.get("vet_urgency", "routine")
        if vet_urgency not in valid_urgencies:
            vet_urgency = "routine"

        # Safety override: critical severity always → emergency urgency
        if severity == "critical" and vet_urgency not in ("emergency", "soon"):
            vet_urgency = "emergency"
            logger.warning("Safety override: critical severity promoted to emergency urgency")

        return DiagnosisResult(
            primary_condition=str(data.get("primary_condition", "Unknown")),
            confidence=confidence,
            severity=severity,
            vet_urgency=vet_urgency,
            summary=str(data.get("summary", "")),
            reasoning=str(data.get("reasoning", "")),
            recommended_actions=list(data.get("recommended_actions", [])),
            suggested_tasks=list(data.get("suggested_tasks", [])),
            disclaimer=str(data.get("disclaimer", "This is not veterinary advice.")),
            retrieved_conditions=retrieved,
            raw_response=raw,
            latency_seconds=latency,
        )