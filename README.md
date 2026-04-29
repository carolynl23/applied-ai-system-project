# 🐾 PawPal+ — AI-Powered Pet Care Planning & Health Triage

> A Streamlit application that combines intelligent daily schedule planning with an AI diagnostic assistant to help pet owners stay consistent with care and respond confidently to health concerns.

---

## 📌 Original Project (Modules 1–3)

**Original project:** PawPal+ Scheduler (Module 2)

The original PawPal+ was a rule-based pet care scheduling tool. Owners could enter their available time window, add care tasks with priorities and durations, and receive a greedy-optimized daily plan that explained why each task was chosen and when it would happen. The system modeled four core classes — `Owner`, `Pet`, `Task`, and `Scheduler` — and included a full pytest suite covering priority ordering, time budget enforcement, and slot non-overlap. It did not include any AI or external API calls.

---

## 🧠 Title and Summary

**PawPal+** is an AI-assisted pet care companion that does two things:

1. **Symptom triage:** Describe your pet's symptoms in plain language. The system retrieves the most relevant conditions from a veterinary knowledge base (RAG), injects that context into a Claude AI prompt, and returns a structured diagnosis — including likely condition, severity, vet urgency, recommended actions, and a set of care tasks to add to your schedule.
2. **Care scheduling:** A priority-based greedy scheduler fits your care tasks into your available time window for the day, with plain-English explanations for every scheduling decision.

**Why it matters:** Pet owners often face a gap between noticing something is wrong and knowing how urgent it is. A 2am internet search for "dog shaking head" returns panic-inducing forum posts. PawPal+ gives a calm, structured first read of likely causes — backed by a curated knowledge base, not raw web results — while being transparent that it is a triage aid, not a veterinarian.

---

## 🗂 Repository Structure

```
pawpal/
├── app.py                  ← Streamlit UI (tabs: symptom checker + scheduler)
├── pawPal_system.py        ← Scheduler: Owner, Pet, Task, Scheduler, DailyPlan
├── diagnostics.py          ← RAG retriever, DiagnosticAgent, DiagnosisResult
├── knowledge_base.json     ← 10 curated pet health conditions
├── test_scheduler.py       ← 18 unit tests for scheduling logic
├── test_diagnostics.py     ← 20 tests: RAG, parsing, guardrails, live API
├── requirements.txt
├── model_card.md
└── assets/
    └── architecture.png    ← System diagram
```

---

## 🏗 Architecture Overview

```
User describes symptoms
        │
        ▼
┌─────────────────────┐
│   RAG Retriever     │◄──── knowledge_base.json (10 conditions)
│  Keyword scoring    │      Filtered by species, ranked by overlap score
└────────┬────────────┘
         │  Top-3 conditions + matched terms
         ▼
┌─────────────────────┐     ┌──────────────────┐
│  DiagnosticAgent    │────►│  Anthropic API   │
│  Builds prompt with │     │  claude-sonnet   │
│  retrieved context  │◄────│  Returns JSON    │
└────────┬────────────┘     └──────────────────┘
         │  Parsed DiagnosisResult
         ├──────────────────────────────────┐
         ▼                                  ▼
  Diagnosis displayed              Suggested tasks injected
  in Streamlit UI                  into Scheduler
                                           │
                                           ▼
                                  ┌─────────────────┐
                                  │    Scheduler    │
                                  │  Priority sort  │
                                  │  + time fit     │
                                  └─────────────────┘
                                           │
                                           ▼
                                     DailyPlan displayed

All API calls and retrieval steps → pawpal.log
```

**RAG detail:** The retriever scores each condition by computing the fraction of its keyword/symptom set that appears in the user's symptom text. No embeddings or vector database are required — the knowledge base is small enough that exact keyword matching gives accurate results and is fully inspectable. The top-3 matches are formatted into a structured context block and injected into the Claude system prompt, so the model reasons over retrieved veterinary data rather than relying on training memory alone.

**Agentic detail:** `DiagnosticAgent.diagnose()` runs a five-step pipeline: validate → retrieve → build prompt → call API → parse and validate output. A safety override step checks that critical-severity responses always carry emergency urgency, correcting the model if it contradicts itself.

---

## ⚙️ Setup Instructions

### 1. Clone the repository
```bash
git clone https://github.com/your-username/pawpal-plus.git
cd pawpal-plus
```

### 2. Create and activate a virtual environment
```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

**requirements.txt:**
```
streamlit>=1.35.0
anthropic>=0.25.0
pytest>=8.0.0
```

### 4. Set your Anthropic API key

**macOS/Linux:**
```bash
