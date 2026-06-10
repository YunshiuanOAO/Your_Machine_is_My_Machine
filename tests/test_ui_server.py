import json

import pytest

import pentestagent.ui.server as ui_server
from pentestagent.ui.server import build_dashboard_state, start_ui_server


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


def test_start_ui_server_does_not_fallback_to_next_port(tmp_path, monkeypatch):
    calls = []

    def raise_port_in_use(address, handler):
        calls.append((address, handler))
        raise OSError("address already in use")

    monkeypatch.setattr(ui_server, "ThreadingHTTPServer", raise_port_in_use)

    with pytest.raises(RuntimeError, match="127.0.0.1:8765"):
        start_ui_server(tmp_path, host="127.0.0.1", port=8765)

    assert len(calls) == 1
    assert calls[0][0] == ("127.0.0.1", 8765)
