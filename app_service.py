"""Persistence and integration logic for the AI LeetCode Coach browser app.

This module connects storage, review_engine, curriculum, and scheduler into
the operations the Streamlit interface needs: loading application data,
generating or loading a daily plan, submitting a structured problem result,
and building a dashboard summary. It never imports Streamlit, so it can be
tested without opening a browser.
"""

import copy
import os
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from zoneinfo import ZoneInfo

import config
import curriculum
import review_engine
import scheduler
import storage

ERROR_TYPE_OPTIONS = [
    "none",
    "concept",
    "pattern_recognition",
    "algorithm",
    "implementation",
    "boundary_condition",
    "complexity",
    "syntax",
    "other",
]
ALLOWED_ERROR_TYPES = set(ERROR_TYPE_OPTIONS)

REQUIRED_USER_FIELDS = [
    "id",
    "name",
    "timezone",
    "preferred_language",
    "default_study_minutes",
]


def get_default_data_dir() -> Path:
    """Return the data directory to use: AI_COACH_DATA_DIR if set, else 'data'."""
    return Path(os.environ.get("AI_COACH_DATA_DIR", "data"))


def get_data_file_paths(data_dir: Union[str, Path]) -> Dict[str, Path]:
    """Return the Path for each JSON data file inside a data directory."""
    data_dir = Path(data_dir)
    return {
        "roadmap": data_dir / "roadmap.json",
        "history": data_dir / "history.json",
        "daily_plans": data_dir / "daily_plans.json",
        "user": data_dir / "user.json",
        "topics": data_dir / "topics.json",
    }


def _normalize_topics(topics_data: Any, source_path: Any) -> List[Dict[str, Any]]:
    """Normalize topics.json into a plain list of topic dictionaries.

    Accepts either a top-level list of topic dictionaries, or a top-level
    dictionary containing a "topics" list (the shape used by the NeetCode
    roadmap reference data, which also carries "source"/"description"
    fields). Does not mutate the loaded object.
    """
    if isinstance(topics_data, list):
        return topics_data

    if isinstance(topics_data, dict):
        topics_list = topics_data.get("topics")
        if not isinstance(topics_list, list):
            raise ValueError(
                f"'{source_path}' is a dictionary but its 'topics' field is missing "
                f"or is not a list (found {type(topics_list).__name__})."
            )
        return topics_list

    raise TypeError(
        f"'{source_path}' must contain a list of topics, or a dictionary with a "
        f"'topics' list, but found {type(topics_data).__name__}."
    )


def load_application_data(data_dir: Union[str, Path]) -> Dict[str, Any]:
    """Load and validate all application data files from a data directory."""
    paths = get_data_file_paths(data_dir)

    roadmap = storage.load_json(paths["roadmap"])
    history = storage.load_json(paths["history"])
    daily_plans = storage.load_json(paths["daily_plans"])
    user = storage.load_json(paths["user"])
    topics = storage.load_json(paths["topics"])

    curriculum.validate_roadmap(roadmap)
    curriculum.validate_history_for_curriculum(history)

    if not isinstance(daily_plans, list):
        raise ValueError(
            f"'{paths['daily_plans']}' must contain a list, but found {type(daily_plans).__name__}."
        )

    if not isinstance(user, dict):
        raise ValueError(
            f"'{paths['user']}' must contain a dictionary, but found {type(user).__name__}."
        )
    for field in REQUIRED_USER_FIELDS:
        if field not in user:
            raise ValueError(f"'{paths['user']}' is missing the required field '{field}'.")

    topics = _normalize_topics(topics, paths["topics"])

    return {
        "roadmap": roadmap,
        "history": history,
        "daily_plans": daily_plans,
        "user": user,
        "topics": topics,
    }


def get_daily_plan_by_id(
    daily_plans: List[Dict[str, Any]], plan_id: str
) -> Optional[Dict[str, Any]]:
    """Return a copy of the daily plan with the given plan_id, or None."""
    for plan in daily_plans:
        if plan.get("plan_id") == plan_id:
            return copy.deepcopy(plan)
    return None


def get_latest_plan_for_date(
    daily_plans: List[Dict[str, Any]], user_id: str, plan_date: str
) -> Optional[Dict[str, Any]]:
    """Return a copy of the most recently created plan for a user and date, or None."""
    matches = [
        plan
        for plan in daily_plans
        if plan.get("user_id") == user_id and plan.get("plan_date") == plan_date
    ]
    if not matches:
        return None

    latest = max(matches, key=lambda plan: plan.get("created_at", ""))
    return copy.deepcopy(latest)


def _resolve_timezone(user: Dict[str, Any]) -> ZoneInfo:
    timezone_name = user.get("timezone")
    try:
        return ZoneInfo(timezone_name)
    except Exception as error:
        raise ValueError(
            f"user.json has an invalid or unsupported timezone '{timezone_name}': {error}"
        ) from error


def generate_or_load_daily_plan(
    available_minutes: int,
    plan_date: Union[date, str],
    data_dir: Union[str, Path],
) -> Dict[str, Any]:
    """Return today's plan, generating and saving it only if one doesn't already exist."""
    data = load_application_data(data_dir)
    resolved_plan_date = scheduler.parse_plan_date(plan_date)
    plan_date_str = resolved_plan_date.isoformat()
    user_id = data["user"]["id"]

    existing_plan = get_latest_plan_for_date(data["daily_plans"], user_id, plan_date_str)
    if existing_plan is not None:
        return {"plan": existing_plan, "created": False}

    generated_plan = scheduler.generate_daily_plan(
        available_minutes, data["roadmap"], data["history"], plan_date=resolved_plan_date
    )

    timezone = _resolve_timezone(data["user"])
    created_at = datetime.now(timezone).isoformat()
    plan_id = str(uuid.uuid4())

    items_with_status = []
    for item in generated_plan["items"]:
        new_item = dict(item)
        new_item["completed"] = False
        new_item["attempt_id"] = None
        items_with_status.append(new_item)

    new_plan = dict(generated_plan)
    new_plan["plan_id"] = plan_id
    new_plan["user_id"] = user_id
    new_plan["created_at"] = created_at
    new_plan["items"] = items_with_status

    updated_daily_plans = data["daily_plans"] + [new_plan]
    paths = get_data_file_paths(data_dir)
    storage.save_json(paths["daily_plans"], updated_daily_plans)

    return {"plan": copy.deepcopy(new_plan), "created": True}


def validate_attempt_form_data(form_data: Any) -> None:
    """Confirm that a submitted problem-result form has valid, well-typed fields."""
    if not isinstance(form_data, dict):
        raise TypeError(f"form_data must be a dictionary, but got {type(form_data).__name__}.")

    required_fields = [
        "solved",
        "time_minutes",
        "attempt_count",
        "used_hint",
        "viewed_solution",
        "confidence",
        "error_type",
        "notes",
    ]
    for field in required_fields:
        if field not in form_data:
            raise ValueError(f"form_data is missing the required field '{field}'.")

    for field in ("solved", "used_hint", "viewed_solution"):
        value = form_data[field]
        if not isinstance(value, bool):
            raise TypeError(
                f"form_data['{field}'] must be True or False, but got {type(value).__name__}."
            )

    time_minutes = form_data["time_minutes"]
    if isinstance(time_minutes, bool) or not isinstance(time_minutes, int):
        raise TypeError(
            f"form_data['time_minutes'] must be an integer, but got {type(time_minutes).__name__}."
        )
    if time_minutes <= 0:
        raise ValueError(f"form_data['time_minutes'] must be positive, but got {time_minutes}.")

    attempt_count = form_data["attempt_count"]
    if isinstance(attempt_count, bool) or not isinstance(attempt_count, int):
        raise TypeError(
            f"form_data['attempt_count'] must be an integer, but got {type(attempt_count).__name__}."
        )
    if attempt_count <= 0:
        raise ValueError(
            f"form_data['attempt_count'] must be positive, but got {attempt_count}."
        )

    confidence = form_data["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, int):
        raise TypeError(
            "form_data['confidence'] must be an integer from 1 to 5, "
            f"but got {type(confidence).__name__}."
        )
    if confidence < 1 or confidence > 5:
        raise ValueError(
            f"form_data['confidence'] must be between 1 and 5, but got {confidence}."
        )

    error_type = form_data["error_type"]
    if not isinstance(error_type, str):
        raise TypeError(
            f"form_data['error_type'] must be a string, but got {type(error_type).__name__}."
        )
    if error_type not in ALLOWED_ERROR_TYPES:
        raise ValueError(
            f"form_data['error_type'] must be one of {ERROR_TYPE_OPTIONS}, but got '{error_type}'."
        )

    notes = form_data["notes"]
    if not isinstance(notes, str):
        raise TypeError(f"form_data['notes'] must be a string, but got {type(notes).__name__}.")

    return None


def get_previous_review_stage(history: List[Dict[str, Any]], problem_id: str) -> int:
    """Return the previous review stage for a problem, or 0 if there is none."""
    latest_attempt = curriculum.get_latest_attempt(history, problem_id)
    if latest_attempt is None:
        return 0

    stage = latest_attempt.get("review_stage")
    if stage is None:
        return 0

    if isinstance(stage, bool) or not isinstance(stage, int):
        raise ValueError(
            f"Stored review_stage for problem '{problem_id}' is corrupt: "
            f"expected an integer, got {type(stage).__name__}."
        )
    if stage < 0 or stage > config.MAX_REVIEW_STAGE:
        raise ValueError(
            f"Stored review_stage for problem '{problem_id}' is corrupt: "
            f"{stage} is out of the valid range 0-{config.MAX_REVIEW_STAGE}."
        )

    return stage


def _calculate_plan_status(items: List[Dict[str, Any]]) -> str:
    total_items = len(items)
    completed_items = sum(1 for item in items if item.get("completed"))

    if completed_items == 0:
        return config.PLAN_STATUS_PLANNED
    if completed_items < total_items:
        return config.PLAN_STATUS_IN_PROGRESS
    return config.PLAN_STATUS_COMPLETED


def submit_problem_result(
    plan_id: str,
    problem_id: str,
    form_data: Dict[str, Any],
    data_dir: Union[str, Path],
    submitted_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate and save one structured problem result, updating history and the plan.

    JSON files cannot provide true multi-file transaction safety. To reduce
    the risk of inconsistent files, this function keeps a copy of the
    original history and daily plans before saving, and if saving the
    second file (daily_plans.json) fails after history.json was already
    written, it attempts to restore history.json to its original contents
    and raises a clear error rather than silently claiming success.
    """
    data = load_application_data(data_dir)
    paths = get_data_file_paths(data_dir)

    plan = get_daily_plan_by_id(data["daily_plans"], plan_id)
    if plan is None:
        raise ValueError(f"No daily plan found with plan_id '{plan_id}'.")

    item_index = None
    for index, item in enumerate(plan["items"]):
        if item["problem_id"] == problem_id:
            item_index = index
            break
    if item_index is None:
        raise ValueError(f"Plan '{plan_id}' has no item for problem_id '{problem_id}'.")

    item = plan["items"][item_index]
    if item.get("completed"):
        raise ValueError(
            f"Problem '{problem_id}' in plan '{plan_id}' has already been completed."
        )

    validate_attempt_form_data(form_data)

    user = data["user"]
    if submitted_at is not None:
        attempted_at = submitted_at
    else:
        timezone = _resolve_timezone(user)
        attempted_at = datetime.now(timezone).isoformat()

    attempt_id = str(uuid.uuid4())

    attempt = {
        "attempt_id": attempt_id,
        "user_id": user["id"],
        "problem_id": problem_id,
        "daily_plan_id": plan_id,
        "attempted_at": attempted_at,
        "solved": form_data["solved"],
        "time_minutes": form_data["time_minutes"],
        "attempt_count": form_data["attempt_count"],
        "used_hint": form_data["used_hint"],
        "viewed_solution": form_data["viewed_solution"],
        "confidence": form_data["confidence"],
        "error_type": form_data["error_type"],
        "notes": form_data["notes"],
    }

    previous_stage = get_previous_review_stage(data["history"], problem_id)
    scheduled_attempt = review_engine.apply_review_schedule(
        attempt, previous_review_stage=previous_stage
    )

    updated_history = data["history"] + [scheduled_attempt]

    updated_item = dict(item)
    updated_item["completed"] = True
    updated_item["attempt_id"] = attempt_id
    updated_item["actual_minutes"] = form_data["time_minutes"]
    updated_item["completed_at"] = attempted_at

    updated_items = list(plan["items"])
    updated_items[item_index] = updated_item

    updated_plan = dict(plan)
    updated_plan["items"] = updated_items
    updated_plan["status"] = _calculate_plan_status(updated_items)

    updated_daily_plans = [
        updated_plan if existing_plan.get("plan_id") == plan_id else existing_plan
        for existing_plan in data["daily_plans"]
    ]

    original_history_backup = copy.deepcopy(data["history"])

    storage.save_json(paths["history"], updated_history)

    try:
        storage.save_json(paths["daily_plans"], updated_daily_plans)
    except Exception as error:
        try:
            storage.save_json(paths["history"], original_history_backup)
        except Exception:
            pass
        raise OSError(
            "Failed to save daily_plans.json after history.json had already been "
            "saved. Attempted to restore history.json to its previous contents. "
            "JSON files cannot provide full database-style transactions, so "
            f"please verify data/history.json manually. Original error: {error}"
        ) from error

    return {"attempt": copy.deepcopy(scheduled_attempt), "plan": copy.deepcopy(updated_plan)}


def build_data_health_report(data_dir: Union[str, Path]) -> Dict[str, Any]:
    """Read-only integrity check across roadmap, history, and daily_plans data.

    This never modifies any file. A legacy attempt with no daily_plan_id
    (such as the manual-test-001 demonstration record) is reported as a
    warning, not an error - it does not make the report unhealthy, and it
    is never removed or excluded from the data itself. Demonstration
    records currently still count toward displayed progress metrics.
    """
    errors: List[str] = []
    warnings: List[str] = []
    demo_record_count = 0

    try:
        data = load_application_data(data_dir)
    except Exception as error:
        return {
            "healthy": False,
            "error_count": 1,
            "warning_count": 0,
            "errors": [f"Could not load application data: {error}"],
            "warnings": [],
            "demo_record_count": 0,
        }

    roadmap = data["roadmap"]
    history = data["history"]
    daily_plans = data["daily_plans"]

    roadmap_ids = {problem["id"] for problem in roadmap}

    attempt_id_counts: Dict[str, int] = {}
    for attempt in history:
        attempt_id = attempt.get("attempt_id")
        if attempt_id is not None:
            attempt_id_counts[attempt_id] = attempt_id_counts.get(attempt_id, 0) + 1

        if attempt.get("problem_id") not in roadmap_ids:
            warnings.append(
                f"History attempt '{attempt.get('attempt_id', '?')}' references "
                f"unknown problem_id '{attempt.get('problem_id')}'."
            )

        if isinstance(attempt_id, str) and attempt_id.startswith("manual-test"):
            demo_record_count += 1

        if attempt.get("daily_plan_id") is None:
            warnings.append(
                f"Attempt '{attempt.get('attempt_id', '?')}' has no daily_plan_id "
                "(a legacy or manually created record)."
            )

    for attempt_id, count in attempt_id_counts.items():
        if count > 1:
            errors.append(f"Duplicate attempt_id '{attempt_id}' appears {count} times in history.")

    plan_ids = {plan.get("plan_id") for plan in daily_plans if plan.get("plan_id") is not None}
    for attempt in history:
        daily_plan_id = attempt.get("daily_plan_id")
        if daily_plan_id is not None and daily_plan_id not in plan_ids:
            errors.append(
                f"Attempt '{attempt.get('attempt_id', '?')}' references missing "
                f"daily_plan_id '{daily_plan_id}'."
            )

    plan_id_counts: Dict[str, int] = {}
    attempt_ids = {
        attempt.get("attempt_id") for attempt in history if attempt.get("attempt_id") is not None
    }

    for plan in daily_plans:
        plan_id = plan.get("plan_id")
        if plan_id is not None:
            plan_id_counts[plan_id] = plan_id_counts.get(plan_id, 0) + 1

        for item in plan.get("items", []):
            if item.get("problem_id") not in roadmap_ids:
                errors.append(
                    f"Plan '{plan_id}' has an item referencing unknown "
                    f"problem_id '{item.get('problem_id')}'."
                )

            item_attempt_id = item.get("attempt_id")
            if item.get("completed") and item_attempt_id is not None:
                if item_attempt_id not in attempt_ids:
                    errors.append(
                        f"Plan '{plan_id}' item for problem '{item.get('problem_id')}' "
                        f"references missing attempt_id '{item_attempt_id}'."
                    )

    for plan_id, count in plan_id_counts.items():
        if count > 1:
            errors.append(f"Duplicate plan_id '{plan_id}' appears {count} times in daily_plans.")

    return {
        "healthy": len(errors) == 0,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "demo_record_count": demo_record_count,
    }


def build_dashboard_summary(
    data_dir: Union[str, Path], dashboard_date: Optional[Union[date, str]] = None
) -> Dict[str, Any]:
    """Return roadmap-wide progress, due-review counts, and recent attempts."""
    data = load_application_data(data_dir)
    roadmap = data["roadmap"]
    history = data["history"]
    user = data["user"]

    overall = curriculum.build_overall_progress(roadmap, history)
    topic_progress = curriculum.build_topic_progress(roadmap, history)

    resolved_date = (
        scheduler.parse_plan_date(dashboard_date) if dashboard_date is not None else date.today()
    )
    due_reviews = scheduler.find_due_reviews(roadmap, history, resolved_date)

    sorted_history = sorted(
        history,
        key=lambda attempt: curriculum._parse_attempted_at(attempt["attempted_at"]),
        reverse=True,
    )
    recent_attempts = [copy.deepcopy(attempt) for attempt in sorted_history[:10]]

    return {
        "user_name": user["name"],
        "total_problems": overall["total_problems"],
        "started_problems": overall["started_problems"],
        "completed_problems": overall["completed_problems"],
        "independently_solved_problems": overall["independently_solved_problems"],
        "completion_percentage": overall["completion_percentage"],
        "independent_percentage": overall["independent_percentage"],
        "due_review_count": len(due_reviews),
        "next_unstarted_problem_id": overall["next_unstarted_problem_id"],
        "next_incomplete_problem_id": overall["next_incomplete_problem_id"],
        "topic_progress": topic_progress,
        "recent_attempts": recent_attempts,
    }
