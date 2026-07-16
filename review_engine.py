"""Deterministic spaced-repetition review calculations for the AI LeetCode Coach.

This module only calculates review results. It never reads or writes files
and never calls an AI model - the rules below are plain Python logic.
"""

from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional, Union

import config


def validate_attempt_for_review(attempt: Any) -> None:
    """Confirm that an attempt dictionary has the fields review logic needs."""
    if not isinstance(attempt, dict):
        raise TypeError(f"attempt must be a dictionary, but got {type(attempt).__name__}.")

    required_fields = ["solved", "used_hint", "viewed_solution", "confidence"]
    for field in required_fields:
        if field not in attempt:
            raise ValueError(f"attempt is missing the required field '{field}'.")

    for field in ("solved", "used_hint", "viewed_solution"):
        value = attempt[field]
        if not isinstance(value, bool):
            raise TypeError(
                f"attempt['{field}'] must be True or False, but got {type(value).__name__}."
            )

    confidence = attempt["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, int):
        raise TypeError(
            "attempt['confidence'] must be an integer from 1 to 5, "
            f"but got {type(confidence).__name__}."
        )
    if confidence < 1 or confidence > 5:
        raise ValueError(f"attempt['confidence'] must be between 1 and 5, but got {confidence}.")

    return None


def validate_previous_review_stage(previous_review_stage: Any) -> None:
    """Confirm that a previous review stage is a valid integer stage."""
    if isinstance(previous_review_stage, bool) or not isinstance(previous_review_stage, int):
        raise TypeError(
            "previous_review_stage must be an integer, "
            f"but got {type(previous_review_stage).__name__}."
        )
    if previous_review_stage < 0 or previous_review_stage > config.MAX_REVIEW_STAGE:
        raise ValueError(
            f"previous_review_stage must be between 0 and {config.MAX_REVIEW_STAGE}, "
            f"but got {previous_review_stage}."
        )
    return None


def determine_review_result(attempt: Dict[str, Any], previous_review_stage: int = 0) -> Dict[str, Any]:
    """Apply the review rules and return the new stage, interval, and reason.

    This is a pure decision function: it never looks at the clock and never
    calculates a date. Rules are checked in this exact order:

    1. Failed to solve            -> stage 0
    2. Viewed the full solution   -> stage 0 (even if a hint was also used)
    3. Solved using a hint        -> stage 1
    4. Independent, low confidence -> stage 1
    5. Independent success        -> advances one step, capped at stage 4
    """
    validate_attempt_for_review(attempt)
    validate_previous_review_stage(previous_review_stage)

    solved = attempt["solved"]
    used_hint = attempt["used_hint"]
    viewed_solution = attempt["viewed_solution"]
    confidence = attempt["confidence"]

    # Rule 1 - Failed to solve.
    if not solved:
        return {
            "review_stage": 0,
            "interval_days": config.REVIEW_INTERVALS[0],
            "review_reason": "failed_to_solve",
        }

    # Rule 2 - Viewed the full solution (takes priority over hint use).
    if viewed_solution:
        return {
            "review_stage": 0,
            "interval_days": config.REVIEW_INTERVALS[0],
            "review_reason": "viewed_full_solution",
        }

    # Rule 3 - Solved using a hint.
    if used_hint:
        return {
            "review_stage": 1,
            "interval_days": config.REVIEW_INTERVALS[1],
            "review_reason": "solved_with_hint",
        }

    # Rule 4 - Independent solve with low confidence.
    if confidence in (1, 2):
        return {
            "review_stage": 1,
            "interval_days": config.REVIEW_INTERVALS[1],
            "review_reason": "independent_low_confidence",
        }

    # Rule 5 - Independent successful solve: advance one step, capped at MAX_REVIEW_STAGE.
    if previous_review_stage in (0, 1):
        new_stage = 2
    elif previous_review_stage == 2:
        new_stage = 3
    elif previous_review_stage == 3:
        new_stage = 4
    else:
        new_stage = config.MAX_REVIEW_STAGE

    return {
        "review_stage": new_stage,
        "interval_days": config.REVIEW_INTERVALS[new_stage],
        "review_reason": "independent_success",
    }


def calculate_next_review_date(base_date: Union[date, str], interval_days: int) -> str:
    """Add interval_days to base_date and return the result as an ISO date string.

    base_date may be a datetime.date or an ISO 'YYYY-MM-DD' string.
    This function never calls date.today() - the caller always supplies the date.
    """
    if isinstance(base_date, datetime):
        raise TypeError(
            "base_date must be a datetime.date or a 'YYYY-MM-DD' string, "
            "not a datetime.datetime, so time information is not silently lost."
        )

    if isinstance(base_date, str):
        try:
            parsed_date = date.fromisoformat(base_date)
        except ValueError as error:
            raise ValueError(
                f"'{base_date}' is not a valid date. Use the format YYYY-MM-DD."
            ) from error
    elif isinstance(base_date, date):
        parsed_date = base_date
    else:
        raise TypeError(
            "base_date must be a datetime.date or a 'YYYY-MM-DD' string, "
            f"but got {type(base_date).__name__}."
        )

    if isinstance(interval_days, bool) or not isinstance(interval_days, int):
        raise TypeError(
            f"interval_days must be an integer, but got {type(interval_days).__name__}."
        )
    if interval_days <= 0:
        raise ValueError(f"interval_days must be a positive integer, but got {interval_days}.")

    next_date = parsed_date + timedelta(days=interval_days)
    return next_date.isoformat()


def build_review_schedule(
    attempt: Dict[str, Any],
    previous_review_stage: int = 0,
    base_date: Optional[Union[date, str]] = None,
) -> Dict[str, Any]:
    """Classify an attempt and calculate its next review date.

    The base date is resolved in this order:
    1. The base_date argument, if provided.
    2. The date portion of attempt['attempted_at'], if present.
    3. date.today(), only if neither of the above is available.
    """
    result = determine_review_result(attempt, previous_review_stage)

    if base_date is not None:
        resolved_base_date: Union[date, str] = base_date
    else:
        attempted_at = attempt.get("attempted_at")
        if attempted_at:
            resolved_base_date = attempted_at.split("T")[0]
        else:
            resolved_base_date = date.today()

    next_review_date = calculate_next_review_date(resolved_base_date, result["interval_days"])

    return {
        "review_stage": result["review_stage"],
        "interval_days": result["interval_days"],
        "review_reason": result["review_reason"],
        "next_review_date": next_review_date,
    }


def apply_review_schedule(
    attempt: Dict[str, Any],
    previous_review_stage: int = 0,
    base_date: Optional[Union[date, str]] = None,
) -> Dict[str, Any]:
    """Return a new dictionary with the original attempt fields plus the review schedule.

    The original attempt dictionary is never modified.
    """
    schedule = build_review_schedule(attempt, previous_review_stage, base_date)
    updated_attempt = dict(attempt)
    updated_attempt.update(schedule)
    return updated_attempt


def run_manual_test() -> None:
    """Demonstrate five review scenarios using the fixed base date 2026-07-13."""
    base_date = date(2026, 7, 13)

    print("=== Review Engine Manual Demonstration ===")
    print(f"Base date: {base_date.isoformat()}\n")

    case_1 = {"solved": False, "used_hint": False, "viewed_solution": False, "confidence": 3}
    result_1 = build_review_schedule(case_1, previous_review_stage=0, base_date=base_date)
    print("Case 1: Failed attempt")
    print(f"  {result_1}\n")

    case_2 = {"solved": True, "used_hint": False, "viewed_solution": True, "confidence": 3}
    result_2 = build_review_schedule(case_2, previous_review_stage=0, base_date=base_date)
    print("Case 2: Viewed full solution")
    print(f"  {result_2}\n")

    case_3 = {"solved": True, "used_hint": True, "viewed_solution": False, "confidence": 3}
    result_3 = build_review_schedule(case_3, previous_review_stage=0, base_date=base_date)
    print("Case 3: Solved with hint")
    print(f"  {result_3}\n")

    case_4 = {"solved": True, "used_hint": False, "viewed_solution": False, "confidence": 2}
    result_4 = build_review_schedule(case_4, previous_review_stage=0, base_date=base_date)
    print("Case 4: Independent low-confidence solve")
    print(f"  {result_4}\n")

    case_5 = {"solved": True, "used_hint": False, "viewed_solution": False, "confidence": 5}
    result_5 = build_review_schedule(case_5, previous_review_stage=2, base_date=base_date)
    print("Case 5: Independent high-confidence solve (previous stage 2)")
    print(f"  {result_5}\n")

    print("Review engine manual demonstration completed successfully!")


if __name__ == "__main__":
    run_manual_test()
