"""
PawPal+ — Streamlit UI with AI diagnostics
Run with:  streamlit run app.py
"""

import streamlit as st
from pawPal_system import Owner, Pet, Task, Scheduler
from diagnostics import DiagnosticAgent, DiagnosisResult

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

# ---------------------------------------------------------------------------
# Session-state defaults
# ---------------------------------------------------------------------------
if "tasks" not in st.session_state:
    st.session_state.tasks: list[Task] = []
if "plan" not in st.session_state:
    st.session_state.plan = None
if "diagnosis" not in st.session_state:
    st.session_state.diagnosis: DiagnosisResult | None = None
if "agent" not in st.session_state:
    try:
        st.session_state.agent = DiagnosticAgent()
        st.session_state.agent_error = None
    except EnvironmentError as e:
        st.session_state.agent = None
        st.session_state.agent_error = str(e)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🐾 PawPal+")
st.caption("AI-powered pet care planning and health triage assistant.")

if st.session_state.agent_error:
    st.error(
        f"**AI diagnostics unavailable:** {st.session_state.agent_error}\n\n"
        "Set your key with `export ANTHROPIC_API_KEY=sk-ant-...` and restart."
    )

# ---------------------------------------------------------------------------
# Sidebar — owner & pet info
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Owner info")
    owner_name = st.text_input("Your name", value="Jordan")
    available = st.slider("Available time today (minutes)", 30, 480, 120, step=15)
    start_time = st.time_input("Start time", value=None)
    preferred_start = start_time.strftime("%H:%M") if start_time else "08:00"
    owner_notes = st.text_area("Notes for the scheduler", placeholder="e.g. rainy day, late morning only")

    st.divider()

    st.header("Pet info")
    pet_name = st.text_input("Pet name", value="Mochi")
    species = st.selectbox("Species", ["dog", "cat", "other"])
    pet_age = st.number_input("Age (years)", min_value=0, max_value=30, value=3)
    pet_notes = st.text_area("Pet notes", placeholder="e.g. recovering from surgery")

# ---------------------------------------------------------------------------
# Tab layout
# ---------------------------------------------------------------------------
tab_diagnose, tab_schedule = st.tabs(["🩺 Symptom checker", "🗓 Daily schedule"])

# ===========================================================================
# TAB 1 — AI Diagnostic
# ===========================================================================
with tab_diagnose:
    st.subheader("Describe your pet's symptoms")
    st.caption(
        "Describe what you've noticed in plain language. The AI will retrieve relevant "
        "conditions from the knowledge base and reason over them to suggest a likely cause."
    )

    symptom_text = st.text_area(
        "Symptom description",
        placeholder=(
            "e.g. Mochi has been scratching her ears constantly for two days, "
            "shaking her head, and there's a dark discharge and a bad smell coming from the left ear."
        ),
        height=120,
    )

    col_btn, col_hint = st.columns([1, 3])
    run_diagnosis = col_btn.button(
        "Run AI diagnosis",
        type="primary",
        disabled=st.session_state.agent is None,
    )
    col_hint.caption(
        "⚠️ This tool is a triage aid only. It does **not** replace a veterinarian."
    )

    if run_diagnosis:
        if not symptom_text.strip():
            st.error("Please describe at least one symptom.")
        else:
            with st.spinner("Retrieving conditions and reasoning with AI..."):
                try:
                    diagnosis = st.session_state.agent.diagnose(
                        symptom_text=symptom_text,
                        species=species,
                        pet_name=pet_name,
                        pet_age=int(pet_age),
                    )
                    st.session_state.diagnosis = diagnosis
                except ValueError as e:
                    st.error(str(e))
                except RuntimeError as e:
                    st.error(f"AI error: {e}")

    # --- Display diagnosis ---
    if st.session_state.diagnosis:
        d = st.session_state.diagnosis

        # Emergency banner
        if d.is_emergency:
            st.error(
                "🚨 **EMERGENCY — seek veterinary care immediately.** "
                "Do not wait — contact an emergency vet clinic now."
            )

        # Main result card
        st.divider()
        col1, col2, col3 = st.columns(3)
        col1.metric("Likely condition", d.primary_condition)
        col2.metric("Severity", f"{d.severity_emoji} {d.severity.title()}")
        col3.metric("Confidence", d.confidence.title())

        st.info(f"**{d.urgency_label}**")
        st.markdown(f"**Summary:** {d.summary}")

        # Recommended actions
        with st.expander("Recommended actions", expanded=True):
            for action in d.recommended_actions:
                st.markdown(f"- {action}")

        # AI reasoning + disclaimer
        with st.expander("AI reasoning"):
            st.markdown(d.reasoning)
            st.caption(f"Response time: {d.latency_seconds:.2f}s")

        with st.expander("RAG — retrieved conditions"):
            for r in d.retrieved_conditions:
                st.markdown(
                    f"**{r.condition.name}** — relevance score: `{r.score:.3f}`  \n"
                    f"Matched terms: {', '.join(r.matched_keywords) if r.matched_keywords else 'none'}"
                )

        st.caption(f"⚠️ {d.disclaimer}")

        # Auto-inject suggested tasks into scheduler
        if d.suggested_tasks:
            st.divider()
            st.markdown("**Tasks suggested by AI diagnosis:**")

            for t_dict in d.suggested_tasks:
                st.markdown(
                    f"- {t_dict.get('title')} "
                    f"({t_dict.get('duration_minutes')} min, {t_dict.get('priority')} priority)"
                )

            if st.button("Add all suggested tasks to schedule", type="primary"):
                added = 0
                for t_dict in d.suggested_tasks:
                    try:
                        task = Task(
                            title=t_dict["title"],
                            duration_minutes=int(t_dict["duration_minutes"]),
                            priority=t_dict.get("priority", "medium"),
                            category=t_dict.get("category", "medical"),
                        )
                        st.session_state.tasks.append(task)
                        added += 1
                    except (KeyError, ValueError):
                        pass
                st.session_state.plan = None
                st.success(f"Added {added} task(s) — switch to the Schedule tab to generate your plan.")


# ===========================================================================
# TAB 2 — Scheduler (unchanged from original, condensed)
# ===========================================================================
with tab_schedule:
    st.subheader("Tasks")

    CATEGORIES = ["exercise", "feeding", "grooming", "medical", "enrichment", "hygiene", "other"]
    CATEGORY_EMOJIS = {
        "exercise": "🏃", "feeding": "🍖", "grooming": "✂️",
        "medical": "💊", "enrichment": "🧩", "hygiene": "🛁", "other": "📋",
    }

    with st.expander("➕ Add a task manually", expanded=not st.session_state.tasks):
        c1, c2 = st.columns(2)
        with c1:
            task_title = st.text_input("Task title", placeholder="Morning walk", key="manual_title")
            duration = st.number_input("Duration (minutes)", 1, 240, 20, key="manual_dur")
        with c2:
            priority = st.selectbox("Priority", ["high", "medium", "low"], key="manual_pri")
            category = st.selectbox("Category", CATEGORIES, key="manual_cat")
        task_notes = st.text_input("Notes (optional)", key="manual_notes")

        if st.button("Add task", type="primary"):
            if not task_title.strip():
                st.error("Please enter a task title.")
            else:
                try:
                    st.session_state.tasks.append(
                        Task(task_title.strip(), int(duration), priority, category, task_notes.strip())
                    )
                    st.session_state.plan = None
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    # Preset bundles
    st.markdown("**Quick-add presets:**")
    pcols = st.columns(3)
    PRESETS = {
        "🐕 Dog basics": [
            Task("Morning walk", 30, "high", "exercise"),
            Task("Breakfast", 10, "high", "feeding"),
            Task("Evening walk", 20, "high", "exercise"),
            Task("Dinner", 10, "high", "feeding"),
            Task("Playtime", 15, "medium", "enrichment"),
        ],
        "🐈 Cat basics": [
            Task("Breakfast", 5, "high", "feeding"),
            Task("Litter box", 5, "high", "hygiene"),
            Task("Dinner", 5, "high", "feeding"),
            Task("Wand play", 15, "medium", "enrichment"),
        ],
        "💊 Medical day": [
            Task("Morning meds", 5, "high", "medical"),
            Task("Check bandage", 10, "high", "medical"),
            Task("Short gentle walk", 15, "medium", "exercise"),
            Task("Evening meds", 5, "high", "medical"),
        ],
    }
    for col, (label, preset_tasks) in zip(pcols, PRESETS.items()):
        if col.button(label):
            st.session_state.tasks.extend(preset_tasks)
            st.session_state.plan = None
            st.rerun()

    # Task list
    if st.session_state.tasks:
        st.markdown(f"**{len(st.session_state.tasks)} task(s) queued**")
        for i, task in enumerate(st.session_state.tasks):
            cols = st.columns([0.06, 0.36, 0.14, 0.20, 0.14, 0.10])
            cols[0].markdown(CATEGORY_EMOJIS.get(task.category, "📋"))
            cols[1].markdown(f"**{task.title}**")
            cols[2].markdown(f"{task.duration_minutes} min")
            cols[3].markdown(
                f"{'🔴' if task.priority=='high' else '🟡' if task.priority=='medium' else '🟢'} {task.priority}"
            )
            cols[4].markdown(task.category)
            if cols[5].button("✕", key=f"del_{i}"):
                st.session_state.tasks.pop(i)
                st.session_state.plan = None
                st.rerun()
    else:
        st.info("No tasks yet — add manually, use a preset, or run a diagnosis to auto-suggest tasks.")

    st.divider()
    st.subheader("Generate schedule")

    if st.button("🗓 Generate schedule", type="primary", disabled=not st.session_state.tasks):
        try:
            owner = Owner(owner_name, int(available), preferred_start, owner_notes)
            pet = Pet(pet_name, species, int(pet_age), pet_notes)
            st.session_state.plan = Scheduler().build_plan(owner, pet, st.session_state.tasks)
        except ValueError as e:
            st.error(str(e))

    if st.session_state.plan:
        plan = st.session_state.plan
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Scheduled", len(plan.scheduled))
        m2.metric("Skipped", len(plan.skipped))
        m3.metric("Time used", f"{plan.total_scheduled_minutes} min")
        m4.metric("Time free", f"{plan.remaining_minutes} min")

        st.markdown(f"**Schedule for {pet_name} — from {preferred_start}**")
        for st_task in plan.scheduled:
            badge = {"high": "🔴", "medium": "🟡", "low": "🟢"}[st_task.priority]
            with st.container(border=True):
                row = st.columns([0.06, 0.26, 0.38, 0.21, 0.09])
                row[0].markdown(st_task.emoji)
                row[1].markdown(f"**{st_task.title}**")
                row[2].markdown(f"_{st_task.reason}_")
                row[3].markdown(f"`{st_task.start_time} – {st_task.end_time}`")
                row[4].markdown(badge)

        if plan.skipped:
            st.warning(f"{len(plan.skipped)} task(s) skipped — not enough time.")
            for t in plan.skipped:
                st.markdown(f"- ✗ {t.emoji} **{t.title}** ({t.duration_minutes} min)")

        with st.expander("View plain-text summary"):
            st.code(plan.summary(), language=None)

        if st.button("🔄 Clear all"):
            st.session_state.tasks = []
            st.session_state.plan = None
            st.rerun()