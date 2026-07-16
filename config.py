"""Shared configuration values for the AI LeetCode Coach."""

REVIEW_INTERVALS = [1, 3, 7, 14, 30]
"""Days until next review for each review stage (index = stage)."""

MAX_REVIEW_STAGE = 4
"""Highest possible review stage (index into REVIEW_INTERVALS)."""

REFLECTION_MINUTES = 5
"""Minutes reserved for reflection at the end of a study session."""

MIN_SESSION_MINUTES_FOR_REFLECTION = 15
"""A session shorter than this reserves no reflection time."""

ITEM_TYPE_REVIEW = "review"
"""Daily plan item type for a due spaced-repetition review."""

ITEM_TYPE_NEW = "new"
"""Daily plan item type for a never-attempted roadmap problem."""

PLAN_STATUS_PLANNED = "planned"
"""Status value for a daily plan with no completed items yet."""

PLAN_STATUS_IN_PROGRESS = "in_progress"
"""Status value for a daily plan with some, but not all, items completed."""

PLAN_STATUS_COMPLETED = "completed"
"""Status value for a daily plan whose items are all completed."""
