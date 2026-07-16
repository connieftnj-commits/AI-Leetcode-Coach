"""Deterministic daily Scheduler for the AI LeetCode Coach.

This module decides which problems belong in today's study session by
combining due spaced-repetition reviews with never-attempted roadmap
problems, subject to the user's available time. It never reads or writes
JSON itself (except in run_manual_test), never calls an AI model, and
never saves a plan - saving happens in a later integration milestone.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union

import config
import curriculum
import storage


def validate_available_minutes(available_minutes: Any) -> None:
    """Confirm that available_minutes is a positive, non-Boolean integer."""
    if isinstance(available_minutes, bool) or not isinstance(available_minutes, int):
        raise TypeError(
            f"available_minutes must be an integer, but got {type(available_minutes).__name__}."
        )
    if available_minutes <= 0:
        raise ValueError(f"available_minutes must be positive, but got {available_minutes}.")
    return None


def parse_plan_date(plan_date: Union[date, str]) -> date:
    """Validate and parse a plan date into a datetime.date object.

    Accepts a datetime.date or an ISO 'YYYY-MM-DD' string. Rejects
    datetime.datetime objects so time-of-day information is never
    silently discarded. This function never calls date.today() - callers
    must always supply an explicit value.
    """
    if isinstance(plan_date, datetime):
        raise TypeError(
            "plan_date must be a datetime.date or a 'YYYY-MM-DD' string, "
            "not a datetime.datetime, so time-of-day information is not silently lost."
        )
    if isinstance(plan_date, date):
        return plan_date
    if isinstance(plan_date, str):
        try:
            return date.fromisoformat(plan_date)
        except ValueError as error:
            raise ValueError(
                f"'{plan_date}' is not a valid date. Use the format YYYY-MM-DD."
            ) from error
    raise TypeError(
        "plan_date must be a datetime.date or a 'YYYY-MM-DD' string, "
        f"but got {type(plan_date).__name__}."
    )


def calculate_reflection_minutes(available_minutes: int) -> int:
    """Return the reflection-time reserve for a session of this length."""
    if available_minutes >= config.MIN_SESSION_MINUTES_FOR_REFLECTION:
        return config.REFLECTION_MINUTES
    return 0


def find_due_reviews(
    roadmap: List[Dict[str, Any]],
    history: List[Dict[str, Any]],
    plan_date: Union[date, str],
) -> List[Dict[str, Any]]:
    """Return one dictionary per roadmap problem whose latest attempt is due for review."""
    curriculum.validate_roadmap(roadmap)
    curriculum.validate_history_for_curriculum(history)
    resolved_plan_date = parse_plan_date(plan_date)

    due_reviews = []

    for problem in sorted(roadmap, key=lambda item: item["roadmap_order"]):
        latest_attempt = curriculum.get_latest_attempt(history, problem["id"])
        if latest_attempt is None:
            continue

        next_review_date_value = latest_attempt.get("next_review_date")
        if not next_review_date_value:
            continue

        try:
            next_review_date = date.fromisoformat(next_review_date_value)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Problem '{problem['id']}' has an invalid stored next_review_date "
                f"'{next_review_date_value}'. Expected the format YYYY-MM-DD."
            ) from error

        if next_review_date > resolved_plan_date:
            continue

        days_overdue = (resolved_plan_date - next_review_date).days

        due_reviews.append(
            {
                "problem_id": problem["id"],
                "title": problem["title"],
                "topic": problem["topic"],
                "difficulty": problem["difficulty"],
                "roadmap_order": problem["roadmap_order"],
                "estimated_minutes": problem["estimated_minutes"],
                "next_review_date": next_review_date_value,
                "days_overdue": days_overdue,
                "latest_attempted_at": latest_attempt["attempted_at"],
                "latest_solved": latest_attempt["solved"],
                "latest_used_hint": latest_attempt["used_hint"],
                "latest_viewed_solution": latest_attempt["viewed_solution"],
                "latest_confidence": latest_attempt.get("confidence"),
            }
        )

    return due_reviews


def get_review_weakness_priority(due_review: Dict[str, Any]) -> int:
    """Return a smaller number for weaker latest performance (higher review priority).

    Order from highest priority (weakest) to lowest priority (strongest):
    0. Latest attempt not solved.
    1. Solved, but viewed the full solution.
    2. Solved, but used a hint.
    3. Solved independently with confidence 1 or 2.
    4. Solved independently with confidence 3 through 5.
    5. Solved independently, but confidence is missing.
    """
    if not due_review["latest_solved"]:
        return 0
    if due_review["latest_viewed_solution"]:
        return 1
    if due_review["latest_used_hint"]:
        return 2

    confidence = due_review["latest_confidence"]
    if confidence is None:
        return 5
    if confidence in (1, 2):
        return 3
    return 4


def sort_due_reviews(due_reviews: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort due reviews: most overdue first, then weakest performance, then roadmap order."""
    return sorted(
        due_reviews,
        key=lambda review: (
            -review["days_overdue"],
            get_review_weakness_priority(review),
            review["roadmap_order"],
        ),
    )


def find_unstarted_problems_in_order(
    roadmap: List[Dict[str, Any]], history: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Return copies of all not_started roadmap problems, in roadmap_order."""
    curriculum.validate_roadmap(roadmap)
    curriculum.validate_history_for_curriculum(history)

    return [
        dict(problem)
        for problem in sorted(roadmap, key=lambda item: item["roadmap_order"])
        if curriculum.get_problem_status(history, problem["id"]) == "not_started"
    ]


def _build_review_selection_reason(days_overdue: int) -> str:
    if days_overdue <= 0:
        return "Review due today."
    day_word = "day" if days_overdue == 1 else "days"
    return f"Review overdue by {days_overdue} {day_word}."


def _build_new_problem_selection_reason() -> str:
    return "Next unstarted problem in roadmap order."


def generate_daily_plan(
    available_minutes: int,
    roadmap: List[Dict[str, Any]],
    history: List[Dict[str, Any]],
    plan_date: Optional[Union[date, str]] = None,
) -> Dict[str, Any]:
    """Build a deterministic daily study plan from due reviews and new problems.

    Reviews are considered first (most overdue and weakest performance
    first), followed by never-attempted roadmap problems in roadmap
    order. An item is only added if it fits in the remaining problem-time
    budget; larger items that don't fit are skipped so smaller, later
    items still get a chance. Neither roadmap nor history is modified.
    """
    validate_available_minutes(available_minutes)
    curriculum.validate_roadmap(roadmap)
    curriculum.validate_history_for_curriculum(history)

    resolved_plan_date = parse_plan_date(plan_date) if plan_date is not None else date.today()

    reflection_minutes = calculate_reflection_minutes(available_minutes)
    remaining_problem_minutes = available_minutes - reflection_minutes

    due_reviews = sort_due_reviews(find_due_reviews(roadmap, history, resolved_plan_date))
    unstarted_problems = find_unstarted_problems_in_order(roadmap, history)

    items: List[Dict[str, Any]] = []
    used_problem_ids = set()

    for review in due_reviews:
        if review["problem_id"] in used_problem_ids:
            continue
        if review["estimated_minutes"] > remaining_problem_minutes:
            continue

        items.append(
            {
                "problem_id": review["problem_id"],
                "title": review["title"],
                "topic": review["topic"],
                "difficulty": review["difficulty"],
                "roadmap_order": review["roadmap_order"],
                "item_type": config.ITEM_TYPE_REVIEW,
                "estimated_minutes": review["estimated_minutes"],
                "selection_reason": _build_review_selection_reason(review["days_overdue"]),
                "next_review_date": review["next_review_date"],
                "days_overdue": review["days_overdue"],
            }
        )
        used_problem_ids.add(review["problem_id"])
        remaining_problem_minutes -= review["estimated_minutes"]

    for problem in unstarted_problems:
        if problem["id"] in used_problem_ids:
            continue
        if problem["estimated_minutes"] > remaining_problem_minutes:
            continue

        items.append(
            {
                "problem_id": problem["id"],
                "title": problem["title"],
                "topic": problem["topic"],
                "difficulty": problem["difficulty"],
                "roadmap_order": problem["roadmap_order"],
                "item_type": config.ITEM_TYPE_NEW,
                "estimated_minutes": problem["estimated_minutes"],
                "selection_reason": _build_new_problem_selection_reason(),
                "next_review_date": None,
                "days_overdue": None,
            }
        )
        used_problem_ids.add(problem["id"])
        remaining_problem_minutes -= problem["estimated_minutes"]

    problem_minutes = sum(item["estimated_minutes"] for item in items)
    total_planned_minutes = problem_minutes + reflection_minutes
    unused_minutes = available_minutes - total_planned_minutes

    return {
        "plan_date": resolved_plan_date.isoformat(),
        "available_minutes": available_minutes,
        "reflection_minutes": reflection_minutes,
        "problem_minutes": problem_minutes,
        "total_planned_minutes": total_planned_minutes,
        "unused_minutes": unused_minutes,
        "status": config.PLAN_STATUS_PLANNED,
        "items": items,
    }


def summarize_daily_plan(plan: Dict[str, Any]) -> str:
    """Return a short human-readable summary of a generated daily plan."""
    review_count = sum(1 for item in plan["items"] if item["item_type"] == config.ITEM_TYPE_REVIEW)
    new_count = sum(1 for item in plan["items"] if item["item_type"] == config.ITEM_TYPE_NEW)

    return (
        f"Plan for {plan['plan_date']}: {plan['available_minutes']} minute(s) available, "
        f"{review_count} review(s) and {new_count} new problem(s) selected, "
        f"{plan['reflection_minutes']} minute(s) reserved for reflection, "
        f"{plan['unused_minutes']} minute(s) unused."
    )


def run_manual_test() -> None:
    """Demonstrate a daily plan using the real (read-only) project data."""
    roadmap = storage.load_json("data/roadmap.json")
    history = storage.load_json("data/history.json")

    available_minutes = 60
    plan_date = "2026-07-20"

    plan = generate_daily_plan(available_minutes, roadmap, history, plan_date=plan_date)

    print("=== Scheduler Manual Demonstration ===")
    print(f"Plan date: {plan['plan_date']}")
    print(f"Available minutes: {plan['available_minutes']}\n")

    for index, item in enumerate(plan["items"], start=1):
        print(f"{index}. {item['title']}")
        print(f"   type: {item['item_type']}")
        print(f"   estimated minutes: {item['estimated_minutes']}")
        print(f"   reason: {item['selection_reason']}\n")

    print(f"Reflection: {plan['reflection_minutes']} minutes\n")
    print(f"problem_minutes: {plan['problem_minutes']}")
    print(f"total_planned_minutes: {plan['total_planned_minutes']}")
    print(f"unused_minutes: {plan['unused_minutes']}\n")

    print(summarize_daily_plan(plan))
    print("\nScheduler manual demonstration completed successfully!")


if __name__ == "__main__":
    run_manual_test()
