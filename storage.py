"""Safe JSON loading and saving helpers for the AI LeetCode Coach."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def load_json(file_path: Any) -> Any:
    """Load and parse a JSON file, raising beginner-friendly errors."""
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Could not find the file '{path}'. "
            "Check the path and make sure the file exists."
        )

    if not path.is_file():
        raise IsADirectoryError(
            f"Expected a file but found a folder at '{path}'. "
            "Please point to a JSON file instead."
        )

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise OSError(
            f"Could not read the file '{path}' because of a system error: {error}"
        ) from error

    if raw_text.strip() == "":
        raise ValueError(
            f"The file '{path}' is empty. It must contain valid JSON, "
            "such as [] for an empty list or {} for an empty object."
        )

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"The file '{path}' does not contain valid JSON. "
            f"Problem at line {error.lineno}, column {error.colno}: {error.msg}"
        ) from error


def save_json(file_path: Any, data: Any) -> None:
    """Save Python data to a JSON file safely using a temp-file-then-replace strategy."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    except TypeError as error:
        raise TypeError(
            f"Could not convert the given data to JSON: {error}. "
            "Make sure it only contains basic types like dict, list, str, "
            "int, float, bool, or None."
        ) from error

    temp_file = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=path.name + ".",
        suffix=".tmp",
        delete=False,
    )
    temp_path = Path(temp_file.name)

    try:
        temp_file.write(text)
        temp_file.close()
        os.replace(temp_path, path)
    except OSError as error:
        if temp_path.exists():
            temp_path.unlink()
        raise OSError(
            f"Could not save the file '{path}' because of a system error: {error}"
        ) from error


def append_json_item(file_path: Any, new_item: dict) -> None:
    """Append a dictionary to a JSON file that stores a list, preserving existing items."""
    if not isinstance(new_item, dict):
        raise TypeError(
            f"new_item must be a dictionary, but got {type(new_item).__name__}."
        )

    existing_data = load_json(file_path)

    if not isinstance(existing_data, list):
        raise ValueError(
            f"Expected '{file_path}' to contain a JSON list, "
            f"but it contains a {type(existing_data).__name__} instead."
        )

    existing_data.append(new_item)
    save_json(file_path, existing_data)


def run_manual_test() -> None:
    """Manually exercise the storage functions against the real data files."""
    data_dir = Path("data")
    roadmap_path = data_dir / "roadmap.json"
    history_path = data_dir / "history.json"
    daily_plans_path = data_dir / "daily_plans.json"
    user_path = data_dir / "user.json"

    roadmap = load_json(roadmap_path)
    history = load_json(history_path)
    daily_plans = load_json(daily_plans_path)
    user = load_json(user_path)

    print(f"Loaded {len(roadmap)} roadmap problems.")
    print(f"Loaded {len(history)} attempts.")
    print(f"Loaded {len(daily_plans)} daily plans.")
    print(f"User name: {user['name']}")

    test_attempt = {
        "attempt_id": "manual-test-001",
        "user_id": "user-001",
        "problem_id": "1",
        "attempted_at": "2026-07-13T10:00:00-04:00",
        "solved": True,
        "time_minutes": 18,
        "attempt_count": 1,
        "used_hint": False,
        "viewed_solution": False,
        "confidence": 4,
        "error_type": "none",
        "notes": "Manual storage test.",
        "next_review_date": "2026-07-20",
    }

    already_exists = any(
        attempt.get("attempt_id") == test_attempt["attempt_id"] for attempt in history
    )

    if already_exists:
        print("Attempt 'manual-test-001' already exists. Skipping append.")
    else:
        append_json_item(history_path, test_attempt)
        print("Attempt 'manual-test-001' added.")

    reloaded_history = load_json(history_path)
    print(f"Final history count: {len(reloaded_history)}")
    print("Storage manual test completed successfully!")


if __name__ == "__main__":
    run_manual_test()
