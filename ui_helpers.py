"""Display-formatting helpers for the AI LeetCode Coach Streamlit interface.

These functions turn raw business data (attempts, plan items, topic
progress) into readable strings and display-only dictionaries. They never
mutate the data they're given and never import Streamlit, so they can be
tested without a browser.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

import curriculum

ITEM_TYPE_LABELS = {
    "review": "Review",
    "new": "New",
}


def _humanize_snake_case(value: str) -> str:
    label = value.replace("_", " ")
    if not label:
        return label
    return label[0].upper() + label[1:]


def format_datetime_for_display(value: Optional[str]) -> str:
    """Format an ISO datetime string for display, keeping timezone info if present."""
    if not isinstance(value, str) or not value:
        return "Unknown"

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value

    formatted = parsed.strftime("%b %d, %Y %I:%M %p")
    if parsed.tzinfo is not None:
        offset = parsed.strftime("%z")
        if offset:
            formatted += f" (UTC{offset[:3]}:{offset[3:]})"
    return formatted


def format_date_for_display(value: Optional[str]) -> str:
    """Format an ISO 'YYYY-MM-DD' date string for display."""
    if not isinstance(value, str) or not value:
        return "—"

    try:
        parsed_date = date.fromisoformat(value)
    except ValueError:
        return value

    return parsed_date.strftime("%b %d, %Y")


def format_boolean(value: Any) -> str:
    """Format a Boolean as Yes/No, handling missing values gracefully."""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return "—"


def format_status_label(status: Optional[str]) -> str:
    """Format a snake_case status value (e.g. 'in_progress') as 'In progress'."""
    if not isinstance(status, str) or not status:
        return "Unknown"
    return _humanize_snake_case(status)


def format_error_type(error_type: Optional[str]) -> str:
    """Format a snake_case error type (e.g. 'boundary_condition') as a readable label."""
    if not isinstance(error_type, str) or not error_type:
        return "Unknown"
    return _humanize_snake_case(error_type)


def build_problem_lookup(roadmap: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Return a new dict mapping problem_id to a copy of its roadmap entry."""
    return {problem["id"]: dict(problem) for problem in roadmap}


def get_problem_title(problem_lookup: Dict[str, Dict[str, Any]], problem_id: Any) -> str:
    """Return a problem's title, falling back safely to its ID when unavailable."""
    problem = problem_lookup.get(problem_id)
    if problem is None:
        return str(problem_id)
    return problem.get("title", str(problem_id))


def _is_demo_attempt(attempt: Dict[str, Any]) -> bool:
    attempt_id = attempt.get("attempt_id", "")
    return isinstance(attempt_id, str) and attempt_id.startswith("manual-test")


def prepare_history_rows(
    history: List[Dict[str, Any]], roadmap: List[Dict[str, Any]], limit: int = 10
) -> List[Dict[str, Any]]:
    """Return display-ready history rows, newest first, limited to `limit` rows."""
    problem_lookup = build_problem_lookup(roadmap)

    sorted_history = sorted(
        history,
        key=lambda attempt: curriculum._parse_attempted_at(attempt.get("attempted_at", "")),
        reverse=True,
    )

    rows = []
    for attempt in sorted_history[:limit]:
        rows.append(
            {
                "Problem": get_problem_title(problem_lookup, attempt.get("problem_id")),
                "Attempted": format_datetime_for_display(attempt.get("attempted_at")),
                "Solved": format_boolean(attempt.get("solved")),
                "Time (min)": attempt.get("time_minutes"),
                "Attempts": attempt.get("attempt_count"),
                "Hint": format_boolean(attempt.get("used_hint")),
                "Full Solution": format_boolean(attempt.get("viewed_solution")),
                "Confidence": attempt.get("confidence"),
                "Error Type": format_error_type(attempt.get("error_type")),
                "Next Review": format_date_for_display(attempt.get("next_review_date")),
                "Demo": "Yes" if _is_demo_attempt(attempt) else "No",
            }
        )
    return rows


def prepare_topic_progress_rows(topic_progress: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rename Curriculum's topic-progress fields to concise, readable column names."""
    rows = []
    for row in topic_progress:
        rows.append(
            {
                "Topic": row["topic"],
                "Total": row["total_problems"],
                "Started": row["started_problems"],
                "Completed": row["completed_problems"],
                "Independent": row["independently_solved_problems"],
                "Assisted only": row["assisted_only_problems"],
                "Unsolved": row["attempted_unsolved_problems"],
                "Completion %": row["completion_percentage"],
            }
        )
    return rows


def prepare_plan_item_display(item: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of a plan item with added readable display fields."""
    display = dict(item)
    display["item_type_label"] = ITEM_TYPE_LABELS.get(item.get("item_type"), "New")
    display["status_label"] = "Completed" if item.get("completed") else "Pending"

    next_review_date = item.get("next_review_date")
    display["review_date_label"] = (
        format_date_for_display(next_review_date) if next_review_date else None
    )

    days_overdue = item.get("days_overdue")
    if days_overdue is None:
        display["overdue_label"] = None
    elif days_overdue <= 0:
        display["overdue_label"] = "Due today"
    else:
        day_word = "day" if days_overdue == 1 else "days"
        display["overdue_label"] = f"{days_overdue} {day_word} overdue"

    return display
