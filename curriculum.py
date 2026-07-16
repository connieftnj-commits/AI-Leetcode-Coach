"""Deterministic curriculum/roadmap progress interpretation for the AI LeetCode Coach.

This module reads roadmap and history data (already loaded into Python
values) and answers questions about progress. It never reads or writes
files itself, never calls an AI model, and never calculates review dates -
that is review_engine.py's job.
"""

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import storage

REQUIRED_PROBLEM_FIELDS = [
    "id",
    "title",
    "topic",
    "difficulty",
    "estimated_minutes",
    "roadmap_order",
]

REQUIRED_ATTEMPT_FIELDS = [
    "problem_id",
    "solved",
    "used_hint",
    "viewed_solution",
    "attempted_at",
]


def _parse_attempted_at(value: str) -> datetime:
    """Parse an attempted_at string into a comparable, timezone-naive datetime.

    Accepts date-only strings ('2026-07-13') and timezone-aware ISO
    datetimes ('2026-07-13T10:00:00-04:00'). Timezone-aware values are
    converted to UTC and stripped of tzinfo, and date-only values are
    treated as midnight, so the results can always be compared to each
    other without Python's "naive vs. aware" comparison errors.
    """
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        pass
    try:
        parsed_date = date.fromisoformat(value)
        return datetime(parsed_date.year, parsed_date.month, parsed_date.day)
    except ValueError as error:
        raise ValueError(
            f"attempted_at '{value}' is not a valid date or datetime. "
            "Use 'YYYY-MM-DD' or an ISO datetime like '2026-07-13T10:00:00-04:00'."
        ) from error


def validate_roadmap(roadmap: Any) -> None:
    """Confirm that a roadmap is a well-formed list of unique problem dictionaries."""
    if not isinstance(roadmap, list):
        raise TypeError(f"roadmap must be a list, but got {type(roadmap).__name__}.")

    seen_ids = set()
    seen_orders = set()

    for index, problem in enumerate(roadmap):
        if not isinstance(problem, dict):
            raise TypeError(
                f"roadmap[{index}] must be a dictionary, but got {type(problem).__name__}."
            )

        for field in REQUIRED_PROBLEM_FIELDS:
            if field not in problem:
                raise ValueError(f"roadmap[{index}] is missing the required field '{field}'.")

        for field in ("id", "title", "topic", "difficulty"):
            value = problem[field]
            if not isinstance(value, str) or value.strip() == "":
                raise ValueError(f"roadmap[{index}]['{field}'] must be a non-empty string.")

        estimated_minutes = problem["estimated_minutes"]
        if isinstance(estimated_minutes, bool) or not isinstance(estimated_minutes, int):
            raise TypeError(
                f"roadmap[{index}]['estimated_minutes'] must be an integer, "
                f"but got {type(estimated_minutes).__name__}."
            )
        if estimated_minutes <= 0:
            raise ValueError(
                f"roadmap[{index}]['estimated_minutes'] must be positive, "
                f"but got {estimated_minutes}."
            )

        roadmap_order = problem["roadmap_order"]
        if isinstance(roadmap_order, bool) or not isinstance(roadmap_order, int):
            raise TypeError(
                f"roadmap[{index}]['roadmap_order'] must be an integer, "
                f"but got {type(roadmap_order).__name__}."
            )
        if roadmap_order <= 0:
            raise ValueError(
                f"roadmap[{index}]['roadmap_order'] must be positive, but got {roadmap_order}."
            )

        problem_id = problem["id"]
        if problem_id in seen_ids:
            raise ValueError(f"Duplicate roadmap problem id found: '{problem_id}'.")
        seen_ids.add(problem_id)

        if roadmap_order in seen_orders:
            raise ValueError(f"Duplicate roadmap_order value found: {roadmap_order}.")
        seen_orders.add(roadmap_order)

    return None


def validate_history_for_curriculum(history: Any) -> None:
    """Confirm that history is a well-formed list of attempt dictionaries."""
    if not isinstance(history, list):
        raise TypeError(f"history must be a list, but got {type(history).__name__}.")

    for index, attempt in enumerate(history):
        if not isinstance(attempt, dict):
            raise TypeError(
                f"history[{index}] must be a dictionary, but got {type(attempt).__name__}."
            )

        for field in REQUIRED_ATTEMPT_FIELDS:
            if field not in attempt:
                raise ValueError(f"history[{index}] is missing the required field '{field}'.")

        problem_id = attempt["problem_id"]
        if not isinstance(problem_id, str) or problem_id.strip() == "":
            raise ValueError(f"history[{index}]['problem_id'] must be a non-empty string.")

        for field in ("solved", "used_hint", "viewed_solution"):
            value = attempt[field]
            if not isinstance(value, bool):
                raise TypeError(
                    f"history[{index}]['{field}'] must be True or False, "
                    f"but got {type(value).__name__}."
                )

        attempted_at = attempt["attempted_at"]
        if not isinstance(attempted_at, str) or attempted_at.strip() == "":
            raise ValueError(f"history[{index}]['attempted_at'] must be a non-empty string.")
        _parse_attempted_at(attempted_at)

    return None


def _validate_problem_id(problem_id: Any) -> None:
    if not isinstance(problem_id, str) or problem_id.strip() == "":
        raise ValueError(f"problem_id must be a non-empty string, but got {problem_id!r}.")


def get_problem_attempts(history: List[Dict[str, Any]], problem_id: str) -> List[Dict[str, Any]]:
    """Return copies of all attempts for one problem, in their original order."""
    validate_history_for_curriculum(history)
    _validate_problem_id(problem_id)

    return [dict(attempt) for attempt in history if attempt["problem_id"] == problem_id]


def get_latest_attempt(history: List[Dict[str, Any]], problem_id: str) -> Optional[Dict[str, Any]]:
    """Return a copy of the most recent attempt for a problem, or None if there are none."""
    attempts = get_problem_attempts(history, problem_id)
    if not attempts:
        return None

    latest = max(attempts, key=lambda attempt: _parse_attempted_at(attempt["attempted_at"]))
    return dict(latest)


def get_problem_status(history: List[Dict[str, Any]], problem_id: str) -> str:
    """Return the highest achievement ever reached for a problem."""
    attempts = get_problem_attempts(history, problem_id)

    if not attempts:
        return "not_started"

    has_independent_solve = any(
        attempt["solved"] and not attempt["used_hint"] and not attempt["viewed_solution"]
        for attempt in attempts
    )
    if has_independent_solve:
        return "solved_independently"

    has_assisted_solve = any(
        attempt["solved"] and (attempt["used_hint"] or attempt["viewed_solution"])
        for attempt in attempts
    )
    if has_assisted_solve:
        return "solved_assisted"

    return "attempted_unsolved"


def is_problem_completed(history: List[Dict[str, Any]], problem_id: str) -> bool:
    """Return True if a problem's status counts as roadmap completion."""
    status = get_problem_status(history, problem_id)
    return status in ("solved_assisted", "solved_independently")


def _sorted_roadmap(roadmap: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return a new list of roadmap problems sorted by roadmap_order."""
    return sorted(roadmap, key=lambda problem: problem["roadmap_order"])


def get_completed_problem_ids(
    roadmap: List[Dict[str, Any]], history: List[Dict[str, Any]]
) -> List[str]:
    """Return the IDs of completed roadmap problems, in roadmap_order."""
    validate_roadmap(roadmap)
    validate_history_for_curriculum(history)

    return [
        problem["id"]
        for problem in _sorted_roadmap(roadmap)
        if is_problem_completed(history, problem["id"])
    ]


def find_next_unstarted_problem(
    roadmap: List[Dict[str, Any]], history: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Return a copy of the lowest-order roadmap problem with status not_started."""
    validate_roadmap(roadmap)
    validate_history_for_curriculum(history)

    for problem in _sorted_roadmap(roadmap):
        if get_problem_status(history, problem["id"]) == "not_started":
            return dict(problem)

    return None


def find_next_incomplete_problem(
    roadmap: List[Dict[str, Any]], history: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Return a copy of the lowest-order roadmap problem that is not yet completed."""
    validate_roadmap(roadmap)
    validate_history_for_curriculum(history)

    for problem in _sorted_roadmap(roadmap):
        if not is_problem_completed(history, problem["id"]):
            return dict(problem)

    return None


def build_problem_progress(
    roadmap: List[Dict[str, Any]], history: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Return one progress dictionary per roadmap problem, in roadmap_order."""
    validate_roadmap(roadmap)
    validate_history_for_curriculum(history)

    progress_rows = []

    for problem in _sorted_roadmap(roadmap):
        attempts = get_problem_attempts(history, problem["id"])
        status = get_problem_status(history, problem["id"])

        solved_attempt_count = sum(1 for attempt in attempts if attempt["solved"])
        independent_solve_count = sum(
            1
            for attempt in attempts
            if attempt["solved"] and not attempt["used_hint"] and not attempt["viewed_solution"]
        )
        assisted_solve_count = sum(
            1
            for attempt in attempts
            if attempt["solved"] and (attempt["used_hint"] or attempt["viewed_solution"])
        )

        latest_attempt = get_latest_attempt(history, problem["id"])
        latest_attempted_at = latest_attempt["attempted_at"] if latest_attempt else None

        progress_rows.append(
            {
                "problem_id": problem["id"],
                "title": problem["title"],
                "topic": problem["topic"],
                "difficulty": problem["difficulty"],
                "roadmap_order": problem["roadmap_order"],
                "status": status,
                "attempt_count": len(attempts),
                "solved_attempt_count": solved_attempt_count,
                "independent_solve_count": independent_solve_count,
                "assisted_solve_count": assisted_solve_count,
                "latest_attempted_at": latest_attempted_at,
                "completed": status in ("solved_assisted", "solved_independently"),
            }
        )

    return progress_rows


def _round_percentage(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)


def build_topic_progress(
    roadmap: List[Dict[str, Any]], history: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Return one progress dictionary per topic, in roadmap topic-appearance order."""
    validate_roadmap(roadmap)
    validate_history_for_curriculum(history)

    problem_progress = build_problem_progress(roadmap, history)

    topic_order: List[str] = []
    rows_by_topic: Dict[str, List[Dict[str, Any]]] = {}

    for row in problem_progress:
        topic = row["topic"]
        if topic not in rows_by_topic:
            rows_by_topic[topic] = []
            topic_order.append(topic)
        rows_by_topic[topic].append(row)

    topic_progress = []

    for topic in topic_order:
        rows = rows_by_topic[topic]
        total_problems = len(rows)
        not_started = sum(1 for row in rows if row["status"] == "not_started")
        attempted_unsolved = sum(1 for row in rows if row["status"] == "attempted_unsolved")
        assisted_only = sum(1 for row in rows if row["status"] == "solved_assisted")
        independently_solved = sum(
            1 for row in rows if row["status"] == "solved_independently"
        )
        completed = assisted_only + independently_solved
        started = total_problems - not_started

        topic_progress.append(
            {
                "topic": topic,
                "total_problems": total_problems,
                "started_problems": started,
                "completed_problems": completed,
                "independently_solved_problems": independently_solved,
                "assisted_only_problems": assisted_only,
                "attempted_unsolved_problems": attempted_unsolved,
                "not_started_problems": not_started,
                "completion_percentage": _round_percentage(completed, total_problems),
                "independent_percentage": _round_percentage(independently_solved, total_problems),
            }
        )

    return topic_progress


def build_overall_progress(
    roadmap: List[Dict[str, Any]], history: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Return roadmap-wide progress counts, percentages, and next-problem pointers."""
    validate_roadmap(roadmap)
    validate_history_for_curriculum(history)

    problem_progress = build_problem_progress(roadmap, history)

    total_problems = len(problem_progress)
    not_started = sum(1 for row in problem_progress if row["status"] == "not_started")
    attempted_unsolved = sum(
        1 for row in problem_progress if row["status"] == "attempted_unsolved"
    )
    assisted_only = sum(1 for row in problem_progress if row["status"] == "solved_assisted")
    independently_solved = sum(
        1 for row in problem_progress if row["status"] == "solved_independently"
    )
    completed = assisted_only + independently_solved
    started = total_problems - not_started

    next_unstarted = find_next_unstarted_problem(roadmap, history)
    next_incomplete = find_next_incomplete_problem(roadmap, history)

    return {
        "total_problems": total_problems,
        "started_problems": started,
        "completed_problems": completed,
        "independently_solved_problems": independently_solved,
        "assisted_only_problems": assisted_only,
        "attempted_unsolved_problems": attempted_unsolved,
        "not_started_problems": not_started,
        "completion_percentage": _round_percentage(completed, total_problems),
        "independent_percentage": _round_percentage(independently_solved, total_problems),
        "next_unstarted_problem_id": next_unstarted["id"] if next_unstarted else None,
        "next_incomplete_problem_id": next_incomplete["id"] if next_incomplete else None,
    }


def run_manual_test() -> None:
    """Demonstrate curriculum progress using the real (read-only) project data."""
    roadmap = storage.load_json("data/roadmap.json")
    history = storage.load_json("data/history.json")

    print("=== Curriculum Manual Demonstration ===")
    print(f"Loaded {len(roadmap)} roadmap problems.\n")

    two_sum_attempts = get_problem_attempts(history, "1")
    two_sum_status = get_problem_status(history, "1")
    print(f"Two Sum attempt count: {len(two_sum_attempts)}")
    print(f"Two Sum status: {two_sum_status}\n")

    next_unstarted = find_next_unstarted_problem(roadmap, history)
    next_incomplete = find_next_incomplete_problem(roadmap, history)
    print(f"Next unstarted problem: {next_unstarted['title'] if next_unstarted else None}")
    print(f"Next incomplete problem: {next_incomplete['title'] if next_incomplete else None}\n")

    overall = build_overall_progress(roadmap, history)
    print(
        f"Overall completion: {overall['completed_problems']}/{overall['total_problems']} "
        f"({overall['completion_percentage']}%)"
    )
    print(
        f"Overall independent completion: {overall['independently_solved_problems']}/"
        f"{overall['total_problems']} ({overall['independent_percentage']}%)"
    )

    print("\nCurriculum manual demonstration completed successfully!")


if __name__ == "__main__":
    run_manual_test()
