"""
PawPal+ scheduling logic.

Classes
-------
Task            A single care task with duration and priority.
ScheduledTask   A Task pinned to a specific time slot with a reason string.
Pet             Basic pet info.
Owner           Owner info including daily time budget and preferred start time.
DailyPlan       The result of a scheduling run.
Scheduler       Builds a DailyPlan from an Owner, Pet, and list of Tasks.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

@dataclass
class Task:
    """Represents one pet care task."""

    PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
    CATEGORY_EMOJIS = {
        "exercise": "🏃",
        "feeding": "🍖",
        "grooming": "✂️",
        "medical": "💊",
        "enrichment": "🧩",
        "hygiene": "🛁",
        "other": "📋",
    }

    title: str
    duration_minutes: int
    priority: str = "medium"   # "high" | "medium" | "low"
    category: str = "other"
    notes: str = ""

    def __post_init__(self) -> None:
        self.priority = self.priority.lower()
        if self.priority not in self.PRIORITY_ORDER:
            raise ValueError(f"priority must be high/medium/low, got {self.priority!r}")
        if self.duration_minutes <= 0:
            raise ValueError("duration_minutes must be positive")

    @property
    def priority_rank(self) -> int:
        return self.PRIORITY_ORDER[self.priority]

    @property
    def emoji(self) -> str:
        return self.CATEGORY_EMOJIS.get(self.category, "📋")

    def __repr__(self) -> str:
        return f"Task({self.title!r}, {self.duration_minutes}min, {self.priority})"


# ---------------------------------------------------------------------------
# ScheduledTask
# ---------------------------------------------------------------------------

@dataclass
class ScheduledTask:
    """A Task placed at a concrete time with a human-readable reason."""

    task: Task
    start_time: str   # "HH:MM"
    end_time: str     # "HH:MM"
    reason: str = ""

    @property
    def title(self) -> str:
        return self.task.title

    @property
    def duration_minutes(self) -> int:
        return self.task.duration_minutes

    @property
    def priority(self) -> str:
        return self.task.priority

    @property
    def emoji(self) -> str:
        return self.task.emoji

    def __repr__(self) -> str:
        return f"ScheduledTask({self.title!r}, {self.start_time}–{self.end_time})"


# ---------------------------------------------------------------------------
# Pet
# ---------------------------------------------------------------------------

@dataclass
class Pet:
    """Basic pet profile."""

    name: str
    species: str = "dog"    # "dog" | "cat" | "other"
    age: Optional[int] = None
    notes: str = ""

    def __repr__(self) -> str:
        return f"Pet({self.name!r}, {self.species})"


# ---------------------------------------------------------------------------
# Owner
# ---------------------------------------------------------------------------

@dataclass
class Owner:
    """Owner profile including scheduling constraints."""

    name: str
    available_minutes: int = 120        # total free time in minutes
    preferred_start: str = "08:00"      # "HH:MM" — when the day starts
    notes: str = ""

    def __post_init__(self) -> None:
        if self.available_minutes <= 0:
            raise ValueError("available_minutes must be positive")
        # Validate preferred_start format
        datetime.strptime(self.preferred_start, "%H:%M")

    def __repr__(self) -> str:
        return f"Owner({self.name!r}, {self.available_minutes}min from {self.preferred_start})"


# ---------------------------------------------------------------------------
# DailyPlan
# ---------------------------------------------------------------------------

@dataclass
class DailyPlan:
    """The output of a Scheduler run."""

    owner: Owner
    pet: Pet
    scheduled: list[ScheduledTask] = field(default_factory=list)
    skipped: list[Task] = field(default_factory=list)

    @property
    def total_scheduled_minutes(self) -> int:
        return sum(st.duration_minutes for st in self.scheduled)

    @property
    def remaining_minutes(self) -> int:
        return self.owner.available_minutes - self.total_scheduled_minutes

    def summary(self) -> str:
        lines = [
            f"Daily plan for {self.pet.name} ({self.owner.name})",
            f"  Time budget: {self.owner.available_minutes} min  |  "
            f"Used: {self.total_scheduled_minutes} min  |  "
            f"Free: {self.remaining_minutes} min",
            "",
            "Scheduled tasks:",
        ]
        for st in self.scheduled:
            lines.append(
                f"  {st.start_time}–{st.end_time}  {st.emoji} {st.title} "
                f"({st.duration_minutes} min, {st.priority}) — {st.reason}"
            )
        if self.skipped:
            lines.append("\nSkipped tasks (not enough time):")
            for t in self.skipped:
                lines.append(f"  ✗ {t.title} ({t.duration_minutes} min, {t.priority})")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class Scheduler:
    """
    Greedy scheduler: sorts tasks by priority (high → medium → low), then
    fits them into the owner's available time window one by one.

    Strategy
    --------
    1. Sort tasks: primary = priority rank, secondary = duration (shorter first
       among equal-priority tasks so more tasks can fit).
    2. Walk through sorted tasks and schedule each one that fits in the
       remaining time.
    3. Tasks that don't fit are marked as skipped with a reason.
    """

    # Buffer in minutes to add between tasks
    BUFFER_MINUTES: int = 5

    def build_plan(
        self,
        owner: Owner,
        pet: Pet,
        tasks: list[Task],
    ) -> DailyPlan:
        """Return a DailyPlan for the given owner, pet, and task list."""
        plan = DailyPlan(owner=owner, pet=pet)

        # Sort: priority first, then duration (shorter tasks first on a tie)
        sorted_tasks = sorted(
            tasks,
            key=lambda t: (t.priority_rank, t.duration_minutes),
        )

        current_time = datetime.strptime(owner.preferred_start, "%H:%M")
        budget_end = current_time + timedelta(minutes=owner.available_minutes)
        time_used = 0

        for task in sorted_tasks:
            needed = task.duration_minutes
            buffer = self.BUFFER_MINUTES if plan.scheduled else 0
            total_needed = needed + buffer

            if time_used + total_needed <= owner.available_minutes:
                if plan.scheduled:
                    current_time += timedelta(minutes=self.BUFFER_MINUTES)
                    time_used += self.BUFFER_MINUTES

                start_str = current_time.strftime("%H:%M")
                end_time = current_time + timedelta(minutes=needed)
                end_str = end_time.strftime("%H:%M")

                reason = self._build_reason(task, time_used, owner)

                plan.scheduled.append(
                    ScheduledTask(
                        task=task,
                        start_time=start_str,
                        end_time=end_str,
                        reason=reason,
                    )
                )

                current_time = end_time
                time_used += needed
            else:
                plan.skipped.append(task)

        return plan

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_reason(self, task: Task, time_used: int, owner: Owner) -> str:
        """Generate a plain-English reason for scheduling this task."""
        remaining_after = owner.available_minutes - time_used - task.duration_minutes
        parts = []

        if task.priority == "high":
            parts.append("high-priority task scheduled first")
        elif task.priority == "medium":
            parts.append("medium-priority task")
        else:
            parts.append("low-priority task fit within remaining time")

        if task.notes:
            parts.append(task.notes)

        parts.append(f"{remaining_after} min remaining after this")
        return "; ".join(parts)

    @staticmethod
    def _time_add(base: str, minutes: int) -> str:
        """Add minutes to an 'HH:MM' string, return new 'HH:MM' string."""
        t = datetime.strptime(base, "%H:%M") + timedelta(minutes=minutes)
        return t.strftime("%H:%M")

    @staticmethod
    def _fmt_range(start: str, duration: int) -> tuple[str, str]:
        """Return (start_str, end_str) given a start and duration."""
        start_dt = datetime.strptime(start, "%H:%M")
        end_dt = start_dt + timedelta(minutes=duration)
        return start_dt.strftime("%H:%M"), end_dt.strftime("%H:%M")