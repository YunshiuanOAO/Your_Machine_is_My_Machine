import json

from pentestagent.ui.server import build_dashboard_state


def test_build_dashboard_state_reads_events_and_report(tmp_path):
    (tmp_path / "events.jsonl").write_text(
        json.dumps({"ts": "now", "event": "decision_tasks_created", "tasks": [{"task_id": "task_1"}]})
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "final_report.json").write_text('{"status": "success"}', encoding="utf-8")
    (tmp_path / "final_report.md").write_text("# Done\n", encoding="utf-8")

    state = build_dashboard_state(tmp_path)

    assert state["stage"] == "complete"
    assert state["events"][0]["event"] == "decision_tasks_created"
    assert state["final_report"]["status"] == "success"
    assert state["final_markdown"] == "# Done\n"
