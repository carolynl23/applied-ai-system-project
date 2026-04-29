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
export ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**Windows (PowerShell):**
```powershell
$env:ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

> The app runs without a key — the scheduler tab works fully, but the symptom checker tab will display an error banner until a key is provided.

### 5. Run the app
```bash
streamlit run app.py
```

### 6. Run tests
```bash
# Fast unit tests — no API calls
pytest test_scheduler.py test_diagnostics.py -v

# Live API tests (requires key, makes real calls, may incur cost)
pytest test_diagnostics.py -v -m live
```

---

## 💬 Sample Interactions

### Example 1 — Ear infection (routine)

**Input:**
```
Species: Dog | Age: 4
Symptoms: "Buddy won't stop scratching his left ear. There's a dark brown
discharge and a really bad smell. He keeps shaking his head."
```

**AI output (summarized):**
```
Primary condition:  Ear infection (otitis externa)
Severity:           Mild  🟢
Confidence:         High
Vet urgency:        Schedule routine appointment

Summary: Buddy's symptoms — persistent ear scratching, dark discharge,
and odor — are classic signs of an outer ear infection, likely caused
by yeast or bacteria. This is very common in dogs and responds well
to prescription ear drops.

Recommended actions:
- Schedule vet appointment for diagnosis and ear drops
- Do not insert anything into the ear canal
- Keep the ear dry — no swimming until resolved

Suggested tasks added to schedule:
- Inspect ear for discharge/odor (5 min, high priority)
- Book vet appointment (5 min, high priority)
- Prevent swimming/bath (5 min, medium priority)
```

---

### Example 2 — Suspected parvovirus (emergency)

**Input:**
```
Species: Dog | Age: 0 (puppy)
Symptoms: "My puppy is vomiting repeatedly and has bloody diarrhea.
She hasn't eaten, she's completely weak and can barely stand up.
She wasn't fully vaccinated yet."
```

**AI output (summarized):**
```
🚨 EMERGENCY — seek veterinary care immediately.

Primary condition:  Canine parvovirus
Severity:           Critical  🔴
Confidence:         High
Vet urgency:        EMERGENCY — go to vet NOW

Summary: The combination of bloody diarrhea, repeated vomiting, severe
lethargy, and incomplete vaccination in a puppy is a textbook presentation
of parvovirus. This is life-threatening and requires immediate IV fluids
and supportive care at an emergency veterinary clinic.

Recommended actions:
- Go to an emergency vet immediately
- Do not offer food or water without vet guidance
- Isolate completely from other dogs
- Bring vaccination records
```

---

### Example 3 — Anxiety (monitor at home)

**Input:**
```
Species: Cat | Age: 6
Symptoms: "Luna has been hiding under the bed for two days and won't
come out to eat much. We just moved to a new apartment last week.
She's panting a little which she never does."
```

**AI output (summarized):**
```
Primary condition:  Anxiety / stress
Severity:           Mild  🟢
Confidence:         Medium
Vet urgency:        Monitor at home

Summary: Luna's hiding, reduced appetite, and unusual panting following
a home move are consistent with relocation stress and anxiety. Cats are
highly sensitive to environmental changes. Most cats adjust within 1–2
weeks with patience and a calm, enriched environment.

Recommended actions:
- Create a safe hiding space with familiar-smelling bedding
- Do not force interaction — let Luna come out on her own terms
- Place food, water, and litter box close to her safe spot initially
- Consider a Feliway pheromone diffuser near her hiding area
- Consult vet if she stops eating entirely for more than 48 hours

Suggested tasks added to schedule:
- Calm enrichment activity (20 min, high priority)
- Set up safe hiding space (10 min, medium priority)
```

---

## 🔧 Design Decisions and Trade-offs

### Why keyword-overlap RAG instead of embeddings?

The knowledge base has 10 conditions. A vector similarity search with sentence-transformers or OpenAI embeddings would add setup complexity (model download, embedding step, vector store) for negligible accuracy improvement at this scale. Keyword overlap is fully transparent — you can read the matched terms in the UI — which matters for a medical triage tool where explainability builds trust. The retriever can be swapped out for embedding-based similarity later without touching the agent or UI.

### Why force JSON output from Claude?

Structured JSON output lets the app parse the diagnosis reliably, extract suggested tasks, apply safety overrides, and display individual fields (severity badge, urgency banner, etc.) without brittle regex parsing of prose. The system prompt is explicit about the schema, and `_parse_response()` validates every field with safe defaults so a malformed response never crashes the app.

### Why a local JSON knowledge base instead of a live veterinary API?

Reproducibility and cost. A live API introduces network dependencies, rate limits, and potential cost per retrieval. The JSON file is versioned, auditable, and works offline. In a production system you would replace this with a proper vector database (Pinecone, Chroma, or pgvector) backed by a larger curated dataset.

### Why keep the scheduler separate from the AI layer?

The scheduler is deterministic and fully testable without any API calls or mocks. Keeping it independent means the scheduling logic can be verified with fast unit tests, and the AI layer can be replaced or upgraded without touching the scheduler. The integration point is clean: the AI returns a list of `suggested_tasks` dicts, and the UI converts them to `Task` objects before passing them to the scheduler.

### Trade-offs made

| Decision | Benefit | Cost |
|---|---|---|
| Keyword RAG | Transparent, no setup, fast | Less semantic — misses paraphrases |
| Forced JSON output | Reliable parsing, structured UI | Slightly more prompt engineering |
| Local knowledge base | Reproducible, auditable, free | Manual maintenance, small coverage |
| Graceful parse fallback | App never crashes | Bad responses silently degrade |
| Safety urgency override | Catches model contradictions | Could override a valid edge case |

---

## 🧪 Testing Summary

### What the tests cover

The test suite has three layers:

**Scheduler tests (`test_scheduler.py`) — 18 tests, no API**
- Priority ordering is always respected (high before medium before low)
- Time slots never overlap
- Total scheduled time never exceeds the budget
- Shorter tasks are scheduled first among equal-priority tasks
- Edge cases: empty task list, single task that doesn't fit, custom start time

**Diagnostic tests (`test_diagnostics.py`) — 20 tests**
- `KnowledgeBase`: loads correctly, species filtering works, missing file raises
- `RAGRetriever`: returns correct top-k, ear symptoms rank ear infection first, species filter applies, scores are in [0, 1]
- `_parse_response`: valid JSON parses correctly, malformed JSON returns graceful fallback, invalid enum fields default safely, critical severity overrides urgency to emergency, markdown fences are stripped
- `DiagnosticAgent` init: missing API key raises `EnvironmentError` (no key needed to run this test)
- **Live API tests** (`@pytest.mark.live`): ear infection diagnosis returns valid structure, suspected parvo triggers emergency or soon urgency, vague symptoms yield low/medium confidence, same input twice gives consistent urgency

### What worked well

- The safety override test caught a real behavior: early prompt versions occasionally returned `severity=critical, vet_urgency=routine` for severe symptoms. The override corrects this silently and logs a warning.
- The graceful JSON fallback has been triggered by responses that included stray explanation text before the JSON — stripping markdown fences and retrying handles most cases.
- The live consistency test (running the same input twice and comparing urgency) revealed that urgency is stable across runs for clear-symptom inputs but can vary for vague ones — this informed the decision to display confidence alongside urgency.

### What didn't work as expected

- Early versions of the RAG retriever ranked anxiety higher than ear infection for ear-scratch symptoms because "scratch" appears in the anxiety keywords. Adding more specific keywords to each condition (e.g. "scratch ear" as a bigram rather than just "scratch") significantly improved precision.
- The model occasionally adds explanatory prose before the JSON despite the system prompt instruction. The `re.sub` fence-stripper handles this for markdown fences but not for freeform preamble. A more robust solution would use Anthropic's structured output / tool use feature to guarantee schema compliance.

### What I learned

- Testing the parsing layer independently from the API is essential — it lets you iterate on output handling without burning API credits.
- Logging every API call from day one saves significant debugging time when something unexpected comes back.
- The live consistency test is more useful as a development signal than a pass/fail gate: it tells you which inputs are well-covered by the knowledge base versus which are genuinely ambiguous.

---

## 🪞 Reflection

### What this project taught me about AI

The biggest insight was how much the *retrieval* step matters relative to the *generation* step. Early versions sent only the symptom text to Claude with a general veterinary prompt, and the responses were plausible but generic. Adding RAG — even simple keyword retrieval — dramatically sharpened the outputs because the model was now reasoning over specific, structured, curated information rather than pattern-matching from training data. The quality of the knowledge base turned out to matter more than prompt engineering.

I also learned that structured output is a design decision, not just a convenience. Forcing JSON with a defined schema meant I could build a UI that acts on the model's output (urgency banners, task injection, severity badges) rather than just displaying text. It also made testing tractable — I can write deterministic assertions about parsed fields rather than trying to evaluate free-form prose.

### On problem-solving

Building the safety override felt like the most important engineering decision in the project. A model that returns `severity=critical` but `vet_urgency=routine` is not just wrong — it's potentially dangerous. Writing a post-processing step that detects and corrects this contradiction, logs a warning, and is covered by a test, is the kind of guardrail that distinguishes a toy demo from something you'd actually trust.

### Ethical considerations

**This tool is a triage aid, not a diagnostic system.** Every AI response includes a disclaimer, and the UI displays it prominently. Emergency outputs trigger a full-screen error banner with explicit instructions to go to a vet immediately. The system is designed to lower anxiety and provide structure, not to replace professional judgment.

**Knowledge base bias:** The current knowledge base covers 10 common conditions weighted toward dogs. Cats are underrepresented, exotic pets are not covered at all, and conditions that present differently by breed are not differentiated. A user with a rabbit or a senior Dachshund is getting less reliable triage than a user with a young mixed-breed dog. This is disclosed in the tool's scope and would need to be addressed with domain expert review before any wider deployment.

**Overconfidence risk:** The model can sound authoritative even when its confidence field is "low." The UI displays the confidence score prominently for this reason — an owner should weight a low-confidence result very differently from a high-confidence one.

---

## 📹 Demo Walkthrough

> 📎 [Loom walkthrough link — replace with your recording]

The walkthrough covers:
1. Entering pet info in the sidebar
2. Running a symptom check for an ear infection (routine urgency)
3. Running a symptom check for suspected parvovirus (emergency banner)
4. Auto-adding AI-suggested tasks to the schedule
5. Generating a daily plan and viewing the scheduled output

---

## 📄 License

MIT — see `LICENSE` file.
