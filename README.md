# AI Personalized LeetCode Coach

## What is this?

AI Personalized LeetCode Coach is a project that will help someone practice
coding interview problems (like on LeetCode) in a smart, personalized way.
Eventually it will track which problems you've solved, remind you to review
problems using spaced repetition, and use AI (OpenAI/Claude) to give you
personalized coaching and hints.

## Current Milestone

**Milestone 1: Project foundation and safe JSON storage. (Complete)**

**Milestone 2: Deterministic spaced-repetition review engine. (Complete)**

**Milestone 3: Curriculum/roadmap progress tracking. (Complete)**

**Milestone 4: Deterministic daily Scheduler. (Complete)**

**Milestone 5: Local Streamlit browser MVP. (Complete)**

**Milestone 6: Stabilization, real-data integrity audit, and UI polish. (Complete)**

Milestone 1 set up the basic project structure and a small set of
functions for safely loading and saving JSON data files.

Milestone 2 added `review_engine.py`, which takes the result of one problem
attempt (did you solve it, did you use a hint or view the solution, how
confident were you) and calculates, using plain deterministic Python logic
(no AI model involved):

- the new review stage;
- how many days until the next review;
- a short, human-readable reason for the decision;
- the actual next review date.

### The five review rules

| # | Condition | New stage | Interval | Reason |
|---|-----------|-----------|----------|--------|
| 1 | Not solved | 0 | 1 day | `failed_to_solve` |
| 2 | Solved, but viewed the full solution | 0 | 1 day | `viewed_full_solution` |
| 3 | Solved independently, but used a hint | 1 | 3 days | `solved_with_hint` |
| 4 | Solved independently, no hint, confidence 1-2 | 1 | 3 days | `independent_low_confidence` |
| 5 | Solved independently, no hint, confidence 3-5 | advances one step (0/1→2, 2→3, 3→4, 4→4) | 7 / 14 / 30 days | `independent_success` |

Rules are checked in order 1 through 5, so a failure or a viewed solution
always resets progress, even if a hint was also used.

Milestone 3 added `curriculum.py`, which looks at the roadmap together with
attempt history and figures out progress — for each problem, each topic,
and the roadmap as a whole. It never decides what to study *today*; it just
answers "where do things currently stand?" The future Scheduler will use
these answers to make that decision.

### The four problem statuses

| Status | Meaning |
|--------|---------|
| `not_started` | No attempt exists for the problem yet. |
| `attempted_unsolved` | At least one attempt exists, but none solved it. |
| `solved_assisted` | Solved at least once, but every solve used a hint or viewed the solution. |
| `solved_independently` | Solved at least once with no hint and no solution viewing. |

A problem's status is its **highest achievement ever reached** — for
example, failing a review after an independent solve does not undo the
`solved_independently` status (that's what the review engine's own
retention tracking is for). A problem counts as "completed" for roadmap
purposes when its status is `solved_assisted` or `solved_independently`.

**Next unstarted vs. next incomplete problem:**
- The **next unstarted problem** is the earliest roadmap problem that has
  never been attempted at all — useful for introducing brand-new content.
- The **next incomplete problem** is the earliest roadmap problem that
  isn't completed yet, which includes problems you've tried and failed,
  not just ones you've never touched — useful for catching up on gaps.

Milestone 4 added `scheduler.py`, which builds a daily study plan out of
what Curriculum already knows. Every day it answers: which reviews are due
or overdue, which brand-new roadmap problems haven't been touched yet, and
which of those actually fit in the time available today.

- **Reviews come first.** Due and overdue reviews are always considered
  before any new problem, and among reviews the most overdue ones (and the
  ones with the weakest last performance) are prioritized first.
- **The plan never exceeds the available time.** A small reflection
  reserve (5 minutes, only for sessions of 15+ minutes) is set aside first,
  and every item is only added if it still fits in what's left — a big
  item that doesn't fit is skipped so a smaller, later item still gets a
  chance.
- **It is fully deterministic.** The same roadmap, history, available time,
  and date always produce the exact same plan. No AI model chooses or
  influences the schedule.
- **Topic prerequisites are not enforced yet.** `data/topics.json` (the
  NeetCode topic dependency graph — see
  `docs/NEETCODE_ROADMAP_REFERENCE.md`) still exists only as reference
  data; the Scheduler does not read it or use it to unlock topics.

Milestone 5 connects everything built so far into a real, usable local
browser app using [Streamlit](https://streamlit.io/). This is no longer an
isolated backend piece — it's the full structured learning loop:

Open the app → see Connie's profile → enter today's available minutes →
generate or load today's plan → review and new problems are displayed →
fill in a structured result form for each problem (solved?, time spent,
attempts, hint used?, viewed solution?, confidence, error type, notes) →
submit → the review engine calculates the next review date → the attempt
is saved to `data/history.json` → the matching plan item is marked
completed in `data/daily_plans.json` → progress metrics update → close and
reopen the app and everything is still there.

- **`app_service.py`** holds all persistence and integration logic
  (loading data, generating/loading plans, validating and saving submitted
  results, building dashboard summaries) and can be fully tested without a
  browser. It never imports Streamlit.
- **`app.py`** holds only the Streamlit display code — four tabs (Today,
  Progress, Roadmap, History) — and calls into `app_service.py` for
  everything else.
- Natural-language feedback, OpenAI/Claude integration, authentication,
  multi-user support, and full topic-prerequisite enforcement are **not**
  part of this milestone.

There is still no AI integration, authentication, or database — just JSON
files, Python logic, and a browser on top of it.

Milestone 6 did not add new features — it stabilized the app after real
browser usage and made the interface easier to read.

**A real bug was found and fixed during this milestone:** `data/topics.json`
loads as `{"source": ..., "description": ..., "topics": [...]}`, but a
long-lived test in `test_scheduler.py` hardcoded expected results by
reading the *real, mutable* `data/roadmap.json`/`history.json` files. Once
real problems (Contains Duplicate, Valid Anagram) were actually solved
through the browser, that test broke — not because anything was wrong with
the Scheduler, but because the test itself assumed the real data would
never change. It was rewritten to use a frozen in-memory snapshot instead,
matching how every other test in the project already works.

**Data-health check:** `app_service.build_data_health_report()` is a
read-only integrity check (never modifies anything) that looks for real
problems — unknown problem IDs, duplicate attempt/plan IDs, plans or
attempts referencing records that no longer exist — and reports them
separately from harmless notes, like a legacy attempt with no linked daily
plan. It's shown as a small status in the sidebar: green when clean, a
warning for minor notes, red only for genuine integrity errors.

**Known demonstration record:** the original `manual-test-001` attempt
(created back in Milestone 1's storage test) has no `daily_plan_id`, since
it predates daily plans entirely. The data-health check flags this as a
warning, not an error, and it is never hidden or deleted automatically —
it still counts toward your progress metrics, and the History tab marks it
with a "Demo" indicator so it's easy to recognize.

**Interface polish:** `ui_helpers.py` now turns raw data into readable
text (Yes/No instead of `true`/`false`, "Boundary condition" instead of
`boundary_condition`, problem titles instead of bare IDs like `#49`), and
`app.py` gained a sidebar (profile + data-health status), progress bars,
clearer plan-status badges, a tidier multi-column result form, and an
explicit message when an existing plan is loaded for a date where you
entered a different number of minutes (the plan is not silently
recalculated).

## Project Structure

```
ai-leetcode-coach/
│
├── hello.py            # environment test script
├── main.py              # empty for now (future entry point)
├── app.py               # Streamlit browser interface (implemented)
├── app_service.py         # persistence/integration + data-health logic (implemented)
├── ui_helpers.py          # display-formatting helpers, no business logic (implemented)
├── scheduler.py          # deterministic daily plan generation (implemented)
├── review_engine.py       # deterministic review-date calculations (implemented)
├── curriculum.py          # roadmap/topic/overall progress tracking (implemented)
├── storage.py            # safe JSON load/save/append functions (implemented)
├── ai_coach.py           # empty for now (future AI integration)
├── config.py             # review/scheduling/plan-status constants (implemented)
│
├── data/
│   ├── roadmap.json      # sample list of practice problems (permanent data)
│   ├── history.json       # record of attempted problems (permanent data)
│   ├── daily_plans.json    # generated daily study plans (permanent data)
│   ├── topics.json        # NeetCode topic dependency graph (reference data only)
│   ├── user.json         # Connie's user profile (permanent data)
│   └── backups/
│       ├── milestone-5-before-interface/     # one-time backup made before the app's first write
│       └── milestone-6-before-stabilization/  # one-time backup made before this milestone
│
├── tests/
│   ├── test_storage.py    # automated tests for storage.py
│   ├── test_review_engine.py  # automated tests for review_engine.py
│   ├── test_curriculum.py   # automated tests for curriculum.py
│   ├── test_scheduler.py    # automated tests for scheduler.py
│   ├── test_app_service.py  # automated tests for app_service.py, incl. data health
│   ├── test_ui_helpers.py   # automated tests for ui_helpers.py
│   └── test_streamlit_app.py # Streamlit AppTest smoke tests for app.py
│
├── .env                 # empty, for future secrets (not committed to Git)
├── .gitignore
├── requirements.txt       # streamlit and tzdata, pinned to installed versions
└── README.md
```

## How to Activate the Virtual Environment (Windows)

A virtual environment (`.venv`) keeps this project's Python packages separate
from the rest of your computer. To activate it in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

You can also just run scripts directly with the venv's Python without
activating, like this:

```powershell
.\.venv\Scripts\python.exe storage.py
```

## How to Run storage.py

```powershell
.\.venv\Scripts\python.exe storage.py
```

This runs a manual test that loads all the data files, prints a short
summary, and adds one test attempt to `data/history.json` (only if it
isn't already there).

## How to Run the Automated Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

This runs every test in the `tests/` folder — `test_storage.py`,
`test_review_engine.py`, `test_curriculum.py`, `test_scheduler.py`,
`test_app_service.py`, `test_ui_helpers.py`, and `test_streamlit_app.py` —
using Python's built-in `unittest` module (the Streamlit tests use
Streamlit's own built-in `AppTest` API, so no extra test framework like
pytest is needed). All tests use temporary directories and never touch the
real `data/` files.

## How to Install Requirements

If you ever need to reinstall dependencies (for example, on a fresh clone):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

This installs Streamlit (the browser interface) and `tzdata` (needed so
Python's built-in `zoneinfo` module can resolve time zones like
`America/New_York` on Windows).

## How to Run the Review Engine Demonstration

```powershell
.\.venv\Scripts\python.exe review_engine.py
```

This prints five example scenarios (failed attempt, viewed solution, solved
with a hint, low-confidence solve, and a confident independent solve) and
shows the resulting review stage, interval, reason, and next review date
for each, using a fixed demonstration date so the output is repeatable.

## How to Run the Curriculum Demonstration

```powershell
.\.venv\Scripts\python.exe curriculum.py
```

This reads (but never modifies) the real `data/roadmap.json` and
`data/history.json` files and prints Two Sum's status, the next unstarted
and next incomplete problems, and overall roadmap completion percentages.

## How to Run the Scheduler Demonstration

```powershell
.\.venv\Scripts\python.exe scheduler.py
```

This reads (but never modifies or saves) the real `data/roadmap.json` and
`data/history.json` files and prints a sample 60-minute daily plan for
2026-07-20 — showing which review and new problems were selected, why,
and how the available time was used.

## How to Start the Browser App

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Streamlit will print a local URL (typically `http://localhost:8501`) and
should open it in your default browser automatically. If it doesn't open
on its own, copy the printed URL into your browser manually.

To stop the server, go back to the terminal running it and press **Ctrl+C**.

## Which Files Contain Permanent Data

- `data/roadmap.json` — the list of practice problems.
- `data/history.json` — every submitted problem attempt (this is your real
  learning history).
- `data/daily_plans.json` — every generated daily plan and its completion
  status.
- `data/user.json` — Connie's profile.
- `data/topics.json` — the NeetCode topic dependency graph (reference data
  only; not yet used to unlock topics).

Two one-time backups exist, each taken right before a milestone's changes
could touch real data:
`data/backups/milestone-5-before-interface/` and
`data/backups/milestone-6-before-stabilization/`.

## Data Health and Demonstration Records

Every time the app loads, it runs a read-only integrity check (never
modifies anything) and shows a small status in the sidebar:

- ✅ green — no issues found;
- 🟡 yellow — minor notes only (for example, a legacy attempt with no
  linked daily plan);
- 🔴 red — a genuine integrity problem (duplicate IDs, or a record that
  references something that no longer exists).

The original `manual-test-001` attempt (from Milestone 1's storage test)
has no linked daily plan and is flagged as a note, not an error. It is
never hidden, excluded, or deleted automatically, and it still counts
toward your progress numbers — the History tab marks it with a "Demo"
label so you can recognize it.

## Important Limitations

- **This is a single-user, local-only MVP.** There is no authentication,
  no multi-user support, and no cloud deployment — it runs on your machine
  and stores data in local JSON files.
- **Only five sample problems are currently loaded** in `data/roadmap.json`.
  The full NeetCode problem set has not been imported yet.
- **OpenAI and Claude APIs are not connected yet.** Every decision in this
  app (review dates, plan selection) is plain deterministic Python logic —
  no AI model is involved anywhere in this milestone.
- **Existing plans are not regenerated.** If you load an existing plan for
  a date and enter a different number of available minutes, the app tells
  you the plan's original minutes rather than silently recalculating it.

## What's Next

The next planned version adds natural-language feedback (so you can
describe how a problem went in your own words instead of filling out every
field) and an expanded Roadmap with the full NeetCode problem set and real
topic-prerequisite enforcement.
