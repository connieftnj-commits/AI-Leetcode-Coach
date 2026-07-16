"""Streamlit browser interface for the AI LeetCode Coach.

All persistence and integration logic lives in app_service.py, and all
display-formatting logic lives in ui_helpers.py. This file is only
responsible for layout and widgets.
"""

from datetime import date
from pathlib import Path

import streamlit as st

import app_service
import ui_helpers

st.set_page_config(page_title="AI Personalized LeetCode Coach", page_icon="🧠", layout="wide")

DATA_DIR = app_service.get_default_data_dir()

STATUS_BADGE_COLORS = {
    "planned": "#6b7280",
    "in_progress": "#b45309",
    "completed": "#15803d",
}


def render_badge(label: str, status_key: str) -> None:
    color = STATUS_BADGE_COLORS.get(status_key, "#6b7280")
    st.markdown(
        f"<span style='background-color:{color};color:white;padding:2px 10px;"
        f"border-radius:12px;font-size:0.85em;'>{label}</span>",
        unsafe_allow_html=True,
    )


st.title("🧠 AI Personalized LeetCode Coach")
st.caption(
    "A structured daily study coach powered by your roadmap, review history, "
    "and available time."
)

try:
    app_data = app_service.load_application_data(DATA_DIR)
    load_error = None
except Exception as error:
    app_data = None
    load_error = error

if load_error is not None:
    st.error(f"Could not load application data: {load_error}")
    with st.expander("Developer details"):
        st.code(f"{type(load_error).__name__}: {load_error}")
    st.stop()

user = app_data["user"]
roadmap = app_data["roadmap"]

try:
    health_report = app_service.build_data_health_report(DATA_DIR)
except Exception as error:
    health_report = None

with st.sidebar:
    st.header("AI LeetCode Coach")
    st.write(f"**User:** {user.get('name', '-')}")
    st.write(f"**Target role:** {user.get('target_role', '-')}")
    st.write(f"**Language:** {user.get('preferred_language', '-')}")
    st.write(f"**Default study minutes:** {user.get('default_study_minutes', '-')}")

    st.divider()
    st.subheader("Data Health")
    if health_report is None:
        st.warning("Could not run the data-health check.")
    elif health_report["healthy"] and health_report["warning_count"] == 0:
        st.success("No data issues detected.")
    elif health_report["healthy"]:
        st.warning(
            f"{health_report['warning_count']} minor note(s) found "
            f"(e.g. legacy or demonstration records)."
        )
    else:
        st.error(f"{health_report['error_count']} data integrity issue(s) found.")

    if health_report is not None and (health_report["errors"] or health_report["warnings"]):
        with st.expander("Details"):
            for message in health_report["errors"]:
                st.write(f"🔴 {message}")
            for message in health_report["warnings"]:
                st.write(f"🟡 {message}")
            if health_report["demo_record_count"] > 0:
                st.caption(
                    f"{health_report['demo_record_count']} demonstration record(s) "
                    "are included above and still count toward your progress metrics."
                )

    st.divider()
    st.caption("Local single-user MVP. Data is stored on this computer.")
    with st.expander("Developer info"):
        st.caption(f"Data directory: {DATA_DIR}")

tab_today, tab_progress, tab_roadmap, tab_history = st.tabs(
    ["📅 Today", "📈 Progress", "🗺️ Roadmap", "🕘 History"]
)

with tab_today:
    top_col1, top_col2, top_col3 = st.columns([1, 1, 1.4])
    with top_col1:
        plan_date_input = st.date_input("Plan date", value=date.today(), key="plan_date_input")
    with top_col2:
        available_minutes_input = st.number_input(
            "Available minutes today",
            min_value=1,
            value=int(user.get("default_study_minutes", 60)),
            step=5,
            key="available_minutes_input",
        )
    with top_col3:
        st.write("")
        st.write("")
        generate_clicked = st.button(
            "Generate or Load Today's Plan", key="generate_plan_button", type="primary"
        )

    if generate_clicked:
        try:
            result = app_service.generate_or_load_daily_plan(
                int(available_minutes_input), plan_date_input, DATA_DIR
            )
            st.session_state["current_plan"] = result["plan"]
            st.session_state["plan_created"] = result["created"]
            st.session_state["requested_minutes"] = int(available_minutes_input)
        except Exception as error:
            st.error(f"Could not generate or load today's plan: {error}")
            with st.expander("Developer details"):
                st.code(f"{type(error).__name__}: {error}")

    plan = st.session_state.get("current_plan")

    if plan is not None:
        status_key = plan.get("status", "planned")
        status_label = ui_helpers.format_status_label(status_key)

        if st.session_state.get("plan_created"):
            st.success(f"✅ New plan created for {plan['plan_date']}.")
        else:
            st.info(f"ℹ️ Loaded the existing plan for {plan['plan_date']}.")
            requested = st.session_state.get("requested_minutes")
            original_minutes = plan.get("available_minutes")
            if requested is not None and requested != original_minutes:
                st.warning(
                    f"An existing plan for this date was loaded. It was originally "
                    f"generated for **{original_minutes} minutes**, created at "
                    f"{ui_helpers.format_datetime_for_display(plan.get('created_at'))}. "
                    f"Your newly entered {requested} minutes were not used — this "
                    "milestone does not yet support regenerating an existing plan."
                )
            else:
                st.caption(
                    f"Originally created {ui_helpers.format_datetime_for_display(plan.get('created_at'))} "
                    f"for {original_minutes} minutes."
                )

        badge_col, _ = st.columns([1, 5])
        with badge_col:
            render_badge(status_label, status_key)

        review_count = sum(1 for item in plan["items"] if item["item_type"] == "review")
        new_count = sum(1 for item in plan["items"] if item["item_type"] == "new")

        metric_cols = st.columns(5)
        metric_cols[0].metric("Reviews", review_count)
        metric_cols[1].metric("New problems", new_count)
        metric_cols[2].metric("Reflection (min)", plan["reflection_minutes"])
        metric_cols[3].metric("Total planned (min)", plan["total_planned_minutes"])
        metric_cols[4].metric("Unused (min)", plan["unused_minutes"])

        st.write("")

        if not plan["items"]:
            st.info("No review or new problems were selected for this plan.")

        for item in plan["items"]:
            display_item = ui_helpers.prepare_plan_item_display(item)
            header = f"{display_item['title']} — {display_item['item_type_label']} ({display_item['status_label']})"
            with st.expander(header, expanded=not item.get("completed")):
                with st.container(border=True):
                    info_cols = st.columns(4)
                    info_cols[0].write(f"**Topic**\n\n{display_item['topic']}")
                    info_cols[1].write(f"**Difficulty**\n\n{display_item['difficulty']}")
                    info_cols[2].write(f"**Estimated time**\n\n{display_item['estimated_minutes']} min")
                    overdue_text = display_item["overdue_label"] or "—"
                    info_cols[3].write(f"**Review status**\n\n{overdue_text}")
                    st.caption(f"Reason selected: {display_item['selection_reason']}")

                if item.get("completed"):
                    st.success(
                        "✅ This item has already been submitted. "
                        f"Actual time: {item.get('actual_minutes', '—')} min."
                    )
                else:
                    form_key = f"form-{plan['plan_id']}-{item['problem_id']}"
                    with st.form(key=form_key):
                        row1 = st.columns(4)
                        with row1[0]:
                            solved = st.checkbox("Solved?", key=f"solved-{form_key}")
                        with row1[1]:
                            time_minutes = st.number_input(
                                "Time spent (min)",
                                min_value=1,
                                value=int(item["estimated_minutes"]),
                                step=1,
                                key=f"time-{form_key}",
                            )
                        with row1[2]:
                            attempt_count = st.number_input(
                                "Attempts",
                                min_value=1,
                                value=1,
                                step=1,
                                key=f"attempts-{form_key}",
                            )
                        with row1[3]:
                            confidence = st.slider(
                                "Confidence",
                                min_value=1,
                                max_value=5,
                                value=3,
                                key=f"confidence-{form_key}",
                            )

                        row2 = st.columns(3)
                        with row2[0]:
                            used_hint = st.checkbox("Used a hint?", key=f"hint-{form_key}")
                        with row2[1]:
                            viewed_solution = st.checkbox(
                                "Viewed the full solution?", key=f"viewed-{form_key}"
                            )
                        with row2[2]:
                            error_type = st.selectbox(
                                "Error type",
                                options=app_service.ERROR_TYPE_OPTIONS,
                                format_func=ui_helpers.format_error_type,
                                key=f"error-{form_key}",
                            )

                        notes = st.text_area("Notes", key=f"notes-{form_key}")

                        submitted = st.form_submit_button("Submit Result", type="primary")

                        if submitted:
                            form_data = {
                                "solved": solved,
                                "time_minutes": int(time_minutes),
                                "attempt_count": int(attempt_count),
                                "used_hint": used_hint,
                                "viewed_solution": viewed_solution,
                                "confidence": int(confidence),
                                "error_type": error_type,
                                "notes": notes,
                            }
                            try:
                                submit_result = app_service.submit_problem_result(
                                    plan["plan_id"], item["problem_id"], form_data, DATA_DIR
                                )
                                st.session_state["current_plan"] = submit_result["plan"]
                                attempt = submit_result["attempt"]
                                st.success(
                                    f"Saved! Next review: "
                                    f"{ui_helpers.format_date_for_display(attempt['next_review_date'])} "
                                    f"(stage {attempt['review_stage']}, "
                                    f"interval {attempt['interval_days']} day(s)). "
                                    f"Reason: {ui_helpers.format_status_label(attempt['review_reason'])}"
                                )
                                st.rerun()
                            except Exception as error:
                                st.error(f"Could not save this result: {error}")
                                with st.expander("Developer details"):
                                    st.code(f"{type(error).__name__}: {error}")
    else:
        st.info("👋 Click \"Generate or Load Today's Plan\" to get started.")

with tab_progress:
    st.subheader("Progress")
    try:
        summary = app_service.build_dashboard_summary(DATA_DIR)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Roadmap Completion", f"{summary['completion_percentage']}%")
        col2.metric("Independent Completion", f"{summary['independent_percentage']}%")
        col3.metric("Problems Started", summary["started_problems"])
        col4.metric("Reviews Due", summary["due_review_count"])

        st.write("**Overall completion**")
        st.progress(min(summary["completion_percentage"] / 100, 1.0))
        st.write("**Independent completion**")
        st.progress(min(summary["independent_percentage"] / 100, 1.0))

        st.write("### Topic Progress")
        if summary["topic_progress"]:
            st.table(ui_helpers.prepare_topic_progress_rows(summary["topic_progress"]))
        else:
            st.info("No topics found in the roadmap yet.")

        problem_lookup = ui_helpers.build_problem_lookup(roadmap)
        next_unstarted_id = summary["next_unstarted_problem_id"]
        next_incomplete_id = summary["next_incomplete_problem_id"]

        next_unstarted_label = (
            f"{ui_helpers.get_problem_title(problem_lookup, next_unstarted_id)} (#{next_unstarted_id})"
            if next_unstarted_id
            else "None — every roadmap problem has been attempted."
        )
        next_incomplete_label = (
            f"{ui_helpers.get_problem_title(problem_lookup, next_incomplete_id)} (#{next_incomplete_id})"
            if next_incomplete_id
            else "None — every roadmap problem is completed."
        )

        info_col1, info_col2 = st.columns(2)
        info_col1.write(f"**Next unstarted problem:** {next_unstarted_label}")
        info_col2.write(f"**Next incomplete problem:** {next_incomplete_label}")
    except Exception as error:
        st.error(f"Could not load progress data: {error}")
        with st.expander("Developer details"):
            st.code(f"{type(error).__name__}: {error}")

with tab_roadmap:
    st.subheader("Roadmap")

    image_path = Path("docs/assets/neetcode-roadmap.png")
    if image_path.exists():
        st.image(
            str(image_path),
            caption="NeetCode topic dependency graph — each arrow points from a "
            "prerequisite topic to the topic that builds on it.",
            width="stretch",
        )
    else:
        st.warning(
            "The roadmap image was not found at docs/assets/neetcode-roadmap.png."
        )

    st.info(
        "The current MVP contains five sample problems. The topic graph is "
        "complete, but full problem import and topic unlocking are future versions."
    )

    try:
        topics = app_data["topics"]
        if topics:
            st.write("### Topics and Prerequisites")
            table_rows = [
                {
                    "Topic": topic_row["topic"],
                    "Prerequisites": ", ".join(topic_row.get("prerequisites", [])) or "None",
                }
                for topic_row in topics
            ]
            st.table(table_rows)
    except Exception as error:
        st.warning(f"Could not display the topic table: {error}")

with tab_history:
    st.subheader("History")
    try:
        history = app_data["history"]

        if not history:
            st.info("No attempts recorded yet. Submit a result from the Today tab to get started.")
        else:
            rows = ui_helpers.prepare_history_rows(history, roadmap, limit=10)
            st.table(rows)
            demo_count = sum(1 for row in rows if row["Demo"] == "Yes")
            if demo_count > 0:
                st.caption(
                    f"ℹ️ {demo_count} of the rows above are demonstration/test records "
                    "(marked \"Demo\") and still count toward your progress metrics."
                )
    except Exception as error:
        st.error(f"Could not load history: {error}")
        with st.expander("Developer details"):
            st.code(f"{type(error).__name__}: {error}")
