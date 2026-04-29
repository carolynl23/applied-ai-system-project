# PawPal+ setup

## Files required
```
pawpal/
├── app.py                  ← Streamlit UI
├── pawPal_system.py        ← Scheduler logic
├── diagnostics.py          ← RAG retriever + AI agent
├── knowledge_base.json     ← Pet health condition library
├── test_diagnostics.py     ← AI reliability suite
├── test_scheduler.py       ← Scheduler unit tests
└── requirements.txt
```

## requirements.txt
```
streamlit>=1.35.0
anthropic>=0.25.0
pytest>=8.0.0
```

## Installation
```bash
pip install -r requirements.txt
```

## API key
The AI diagnostic feature requires an Anthropic API key.

**macOS / Linux:**
```bash
export ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**Windows (PowerShell):**
```powershell
$env:ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

The app works without a key — the scheduler tab remains fully functional,
but the symptom checker tab will show an error banner.

## Run the app
```bash
streamlit run app.py
```

## Run tests (no API calls)
```bash
pytest test_scheduler.py test_diagnostics.py -v
```

## Run live API tests (requires key, makes real calls)
```bash
pytest test_diagnostics.py -v -m live
```

## Logs
All AI calls and retrieval steps are written to `pawpal.log` in the project directory.
Each log line includes a timestamp, log level, and structured message.