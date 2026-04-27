"""
PawPal+ — Streamlit UI
Run with:  streamlit run app.py
"""

import streamlit as st
from pawPal_system import Owner, Pet, Task, Scheduler

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

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🐾 PawPal+")
st.caption("A daily pet-care planner that fits tasks around your schedule.")

# ---------------------------------------------------------------------------
# Sidebar — owner & pet info
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Owner info")
    owner_name = st.text_input("Your name", value="Jordan")
    available = st.slider("Available time today (minutes)", 30, 480, 120, step=15)
    start_time = st.time_input("Start time", value=None)
    preferred_start = start_time.strftime("%H:%M") if start_time else "08:00"
    owner_notes = st.text_area("Any notes for the scheduler?", placeholder="e.g. rainy day, late morning only")

    st.divider()

    st.header("Pet info")
    pet_name = st.text_input("Pet name", value="Mochi")
    species = st.selectbox("Species", ["dog", "cat", "other"])
    pet_age = st.number_input("Age (years)", min_value=0, max_value=30, value=3)
    pet_notes = st.text_area("Pet notes", placeholder="e.g. recovering from surgery, needs extra walks")

# ---------------------------------------------------------------------------
# Main — task management
# ---------------------------------------------------------------------------
st.subheader("Tasks")

CATEGORIES = ["exercise", "feeding", "grooming", "medical", "enrichment", "hygiene", "other"]
CATEGORY_EMOJIS = {
    "exercise": "🏃", "feeding": "🍖", "grooming": "✂️",
    "medical": "💊", "enrichment": "🧩", "hygiene": "🛁", "other": "📋",
}

with st.expander("➕ Add a task", expanded=not st.session_state.tasks):
    col1, col2 = st.columns(2)
    with col1:
        task_title = st.text_input("Task title", placeholder="Morning walk")
        duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
    with col2:
        priority = st.selectbox("Priority", ["high", "medium", "low"], index=0)
        category = st.selectbox("Category", CATEGORIES)
    task_notes = st.text_input("Task notes (optional)", placeholder="e.g. use the park route")

    if st.button("Add task", type="primary"):
        if not task_title.strip():
            st.error("Please enter a task title.")
        else:
            try:
                t = Task(
                    title=task_title.strip(),
                    duration_minutes=int(duration),
                    priority=priority,
                    category=category,
                    notes=task_notes.strip(),
                )
                st.session_state.tasks.append(t)
                st.session_state.plan = None  # reset plan when tasks change
                st.rerun()
            except ValueError as e:
                st.error(str(e))

# Show current task list
if st.session_state.tasks:
    st.markdown(f"**{len(st.session_state.tasks)} task(s) queued**")

    for i, task in enumerate(st.session_state.tasks):
        cols = st.columns([0.07, 0.38, 0.15, 0.18, 0.12, 0.10])
        cols[0].markdown(CATEGORY_EMOJIS.get(task.category, "📋"))
        cols[1].markdown(f"**{task.title}**")
        cols[2].markdown(f"{task.duration_minutes} min")

        priority_colors = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        cols[3].markdown(f"{priority_colors[task.priority]} {task.priority}")
        cols[4].markdown(task.category)

        if cols[5].button("✕", key=f"del_{i}", help="Remove this task"):
            st.session_state.tasks.pop(i)
            st.session_state.plan = None
            st.rerun()
else:
    st.info("No tasks yet — add one above.")

# Preset task bundles
st.markdown("**Quick-add presets:**")
preset_cols = st.columns(3)
PRESETS = {
    "🐕 Dog basics": [
        Task("Morning walk", 30, "high", "exercise", "leash walk around the block"),
        Task("Breakfast", 10, "high", "feeding"),
        Task("Evening walk", 20, "high", "exercise"),
        Task("Dinner", 10, "high", "feeding"),
        Task("Playtime", 15, "medium", "enrichment"),
        Task("Brush coat", 10, "low", "grooming"),
    ],
    "🐈 Cat basics": [
        Task("Breakfast", 5, "high", "feeding"),
        Task("Litter box", 5, "high", "hygiene"),
        Task("Dinner", 5, "high", "feeding"),
        Task("Wand play", 15, "medium", "enrichment"),
        Task("Brush", 10, "low", "grooming"),
    ],
    "💊 Medical day": [
        Task("Morning meds", 5, "high", "medical", "crush pill in food"),
        Task("Check bandage", 10, "high", "medical"),
        Task("Short gentle walk", 15, "medium", "exercise", "no running"),
        Task("Evening meds", 5, "high", "medical"),
    ],
}
for col, (label, preset_tasks) in zip(preset_cols, PRESETS.items()):
    if col.button(label):
        st.session_state.tasks.extend(preset_tasks)
        st.session_state.plan = None
        st.rerun()

# ---------------------------------------------------------------------------
# Generate schedule
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Daily schedule")

if st.button("🗓 Generate schedule", type="primary", disabled=not st.session_state.tasks):
    try:
        owner = Owner(
            name=owner_name,
            available_minutes=int(available),
            preferred_start=preferred_start,
            notes=owner_notes,
        )
        pet = Pet(name=pet_name, species=species, age=int(pet_age), notes=pet_notes)
        scheduler = Scheduler()
        st.session_state.plan = scheduler.build_plan(owner, pet, st.session_state.tasks)
    except ValueError as e:
        st.error(f"Could not build plan: {e}")

# ---------------------------------------------------------------------------
# Display plan
# ---------------------------------------------------------------------------
if st.session_state.plan:
    plan = st.session_state.plan

    # Summary metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Tasks scheduled", len(plan.scheduled))
    m2.metric("Tasks skipped", len(plan.skipped))
    m3.metric("Time used", f"{plan.total_scheduled_minutes} min")
    m4.metric("Time free", f"{plan.remaining_minutes} min")

    st.markdown(f"**Schedule for {pet.name} — starting at {preferred_start}**")

    if plan.scheduled:
        for st_task in plan.scheduled:
            priority_badge = {"high": "🔴", "medium": "🟡", "low": "🟢"}[st_task.priority]
            with st.container(border=True):
                row = st.columns([0.06, 0.25, 0.40, 0.20, 0.09])
                row[0].markdown(st_task.emoji)
                row[1].markdown(f"**{st_task.title}**")
                row[2].markdown(f"_{st_task.reason}_")
                row[3].markdown(f"`{st_task.start_time} – {st_task.end_time}`")
                row[4].markdown(f"{priority_badge}")

    if plan.skipped:
        st.warning(
            f"**{len(plan.skipped)} task(s) skipped** — not enough time in the "
            f"{available}-minute budget."
        )
        for t in plan.skipped:
            st.markdown(f"- ✗ {t.emoji} **{t.title}** ({t.duration_minutes} min, {t.priority})")
        st.caption(
            "Tip: increase your available time, shorten some tasks, or remove lower-priority items."
        )

    # Raw text summary (collapsible)
    with st.expander("View plain-text summary"):
        st.code(plan.summary(), language=None)

    # Reset button
    if st.button("🔄 Clear plan and start over"):
        st.session_state.tasks = []
        st.session_state.plan = None
        st.rerun()
elif not st.session_state.tasks:
    st.info("Add tasks above, then generate a schedule.")
    
# import streamlit as st

# st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

# st.title("🐾 PawPal+")

# st.markdown(
#     """
# Welcome to the PawPal+ starter app.

# This file is intentionally thin. It gives you a working Streamlit app so you can start quickly,
# but **it does not implement the project logic**. Your job is to design the system and build it.

# Use this app as your interactive demo once your backend classes/functions exist.
# """
# )

# with st.expander("Scenario", expanded=True):
#     st.markdown(
#         """
# **PawPal+** is a pet care planning assistant. It helps a pet owner plan care tasks
# for their pet(s) based on constraints like time, priority, and preferences.

# You will design and implement the scheduling logic and connect it to this Streamlit UI.
# """
#     )

# with st.expander("What you need to build", expanded=True):
#     st.markdown(
#         """
# At minimum, your system should:
# - Represent pet care tasks (what needs to happen, how long it takes, priority)
# - Represent the pet and the owner (basic info and preferences)
# - Build a plan/schedule for a day that chooses and orders tasks based on constraints
# - Explain the plan (why each task was chosen and when it happens)
# """
#     )

# st.divider()

# st.subheader("Quick Demo Inputs (UI only)")
# owner_name = st.text_input("Owner name", value="Jordan")
# pet_name = st.text_input("Pet name", value="Mochi")
# species = st.selectbox("Species", ["dog", "cat", "other"])

# st.markdown("### Tasks")
# st.caption("Add a few tasks. In your final version, these should feed into your scheduler.")

# if "tasks" not in st.session_state:
#     st.session_state.tasks = []

# col1, col2, col3 = st.columns(3)
# with col1:
#     task_title = st.text_input("Task title", value="Morning walk")
# with col2:
#     duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
# with col3:
#     priority = st.selectbox("Priority", ["low", "medium", "high"], index=2)

# if st.button("Add task"):
#     st.session_state.tasks.append(
#         {"title": task_title, "duration_minutes": int(duration), "priority": priority}
#     )

# if st.session_state.tasks:
#     st.write("Current tasks:")
#     st.table(st.session_state.tasks)
# else:
#     st.info("No tasks yet. Add one above.")

# st.divider()

# st.subheader("Build Schedule")
# st.caption("This button should call your scheduling logic once you implement it.")

# if st.button("Generate schedule"):
#     st.warning(
#         "Not implemented yet. Next step: create your scheduling logic (classes/functions) and call it here."
#     )
#     st.markdown(
#         """
# Suggested approach:
# 1. Design your UML (draft).
# 2. Create class stubs (no logic).
# 3. Implement scheduling behavior.
# 4. Connect your scheduler here and display results.
# """
#     )
