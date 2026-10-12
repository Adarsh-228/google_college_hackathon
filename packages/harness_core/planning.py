from typing import List, Dict, Any, Optional

class PlanningEngine:
    """
    Manages persistent plan state, validation, and per-turn plan prompt injection (§2.1).
    Plans are maintained dynamically and injected fresh every turn outside persistent history.
    """

    SYSTEM_PROMPT = """# Task planning
You have an `update_plan` tool that holds a todo list. The harness shows the current plan back to you before every turn, so use it to stay on track.
- For any non-trivial task (about 3+ steps), your FIRST action MUST be to call `update_plan` to break the task into concrete steps.
- Keep it current: mark exactly ONE task `in_progress` while you work on it, and mark a task `completed` the moment it is actually done (don't batch completions).
- Add new tasks as you discover them; re-send the COMPLETE list each time.
- Skip planning only for a single trivial step or a purely informational request."""

    FIRST_TURN_REMINDER = """<system-reminder>
You have not created a plan yet. Before taking any other action, call update_plan to break this task into concrete steps. (Skip planning only for a single trivial step or a purely informational request.)
</system-reminder>"""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.current_plan: List[Dict[str, Any]] = []

    def update_plan(self, plan: List[Dict[str, Any]]) -> str:
        """Replaces the entire in-memory plan list and enforces protocol constraints."""
        if not self.enabled:
            return "[Error: Planning is disabled in this harness configuration]"

        # Validate structure
        in_progress_count = 0
        cleaned_plan = []
        for item in plan:
            content = str(item.get("content", "")).strip()
            status = str(item.get("status", "pending")).lower()
            if status not in ("pending", "in_progress", "completed"):
                status = "pending"
            if status == "in_progress":
                in_progress_count += 1
            cleaned_plan.append({
                "content": content,
                "status": status,
                "activeForm": item.get("activeForm", content),
            })

        self.current_plan = cleaned_plan
        msg = f"[update_plan: Plan updated with {len(cleaned_plan)} step(s).]"
        if in_progress_count != 1:
            msg += f" Note: Protocol expects exactly ONE task marked 'in_progress' (currently {in_progress_count})."
        return msg

    def format_plan_reminder(self) -> Optional[str]:
        """Formats the fresh plan reminder injected before each turn (§2.1 / Figure 17)."""
        if not self.enabled:
            return None

        if not self.current_plan:
            return self.FIRST_TURN_REMINDER

        lines = []
        for idx, item in enumerate(self.current_plan, start=1):
            status_box = "[ ]"
            if item["status"] == "completed":
                status_box = "[x]"
            elif item["status"] == "in_progress":
                status_box = "[*]"
            lines.append(f"{idx}. {status_box} {item['content']} ({item['status']})")

        plan_str = "\n".join(lines)
        return (
            f"<system-reminder>\n"
            f"Current plan (update it via update_plan as you progress; keep exactly one task in_progress, "
            f"and mark a task completed the moment it is actually done):\n"
            f"{plan_str}\n"
            f"</system-reminder>"
        )
