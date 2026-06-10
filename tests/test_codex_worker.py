import time

from pentestagent.config import Settings
from pentestagent.graph.builder import build_graph
from pentestagent.observability import RunArtifacts
from pentestagent.schemas.findings import ReconReport, ServiceFinding
from pentestagent.schemas.tasks import SpawnAgentTask
from pentestagent.services.codex_worker import RunningWorker, parse_worker_result, recover_completed_worker_stdout, run_codex_exploit_fanout


def test_codex_fanout_returns_blocked_report_when_worker_not_configured(tmp_path):
    artifacts = RunArtifacts.create("10.10.10.10", tmp_path)
    task = SpawnAgentTask(
        task_id="task_1",
        agent_kind="exploit",
        target_ip="10.10.10.10",
        objective="Validate HTTP exploit path",
        service_name="http",
        port=80,
    )

    results = run_codex_exploit_fanout(
        [task],
        {"target_ip": "10.10.10.10", "run_id": artifacts.run_id},
        Settings(exploit_dispatch="codex_parallel", codex_worker_command=None),
        artifacts,
    )

    assert len(results) == 1
    assert results[0].status == "blocked"
    assert (artifacts.run_dir / "agent_reports" / "task_1.json").exists()


def test_parse_worker_result_normalizes_key_value_memory_updates():
    task = SpawnAgentTask(
        task_id="task_1",
        agent_kind="exploit",
        target_ip="10.10.10.10",
        objective="Validate HTTP exploit path",
        service_name="http",
        port=80,
        memory_key="http:80",
    )
    stdout = """
{
  "task_id": "task_1",
  "agent_kind": "exploit",
  "status": "failed",
  "summary": "No exploit primitive found.",
  "evidence": {"checked": true},
  "memory_updates": [{"key": "http:80", "value": "No exposed admin route."}],
  "spawned_tasks": []
}
"""

    result = parse_worker_result(task, stdout, "", 0)

    assert result.status == "failed"
    assert result.summary == "No exploit primitive found."
    assert result.memory_updates[0].task_id == "http:80"
    assert result.memory_updates[0].summary == "No exposed admin route."


def test_parse_worker_result_downgrades_success_without_shell_handoff():
    task = SpawnAgentTask(
        task_id="web-fingerprint",
        agent_kind="exploit",
        target_ip="10.10.10.10",
        objective="Fingerprint web service",
        service_name="http",
        port=80,
    )
    stdout = """
{
  "task_id": "web-fingerprint",
  "agent_kind": "exploit",
  "status": "success",
  "summary": "HTTP service fingerprinted, but no RCE or shell path was proven.",
  "evidence": {"framework": "Next.js"},
  "memory_updates": [],
  "spawned_tasks": []
}
"""

    result = parse_worker_result(task, stdout, "", 0)

    assert result.status == "retry"
    assert result.evidence["success_downgraded"] is True
    assert "no RCE shell handoff" in result.summary


def test_recover_completed_worker_stdout_from_progress(tmp_path):
    task = SpawnAgentTask(
        task_id="web-fingerprint",
        agent_kind="exploit",
        target_ip="10.10.10.10",
        objective="Fingerprint web service",
        service_name="http",
        port=80,
    )
    progress_path = tmp_path / "worker.progress.jsonl"
    progress_path.write_text(
        "\n".join(
            [
                '{"item_type":"agent_message","status":"completed","summary":"{\\"task_id\\":\\"web-fingerprint\\",\\"agent_kind\\":\\"exploit\\",\\"status\\":\\"retry\\",\\"summary\\":\\"done\\",\\"evidence\\":{},\\"memory_updates\\":[],\\"spawned_tasks\\":[]}"}',
                '{"item_type":"turn","status":"completed","summary":"Codex turn completed"}',
            ]
        ),
        encoding="utf-8",
    )
    worker = RunningWorker(
        task=task,
        process=None,  # type: ignore[arg-type]
        stdout_path=tmp_path / "stdout.json",
        stderr_path=tmp_path / "stderr.txt",
        progress_path=progress_path,
        progress_offset=0,
        started_at=0,
        fanout_round=1,
    )

    recovered = recover_completed_worker_stdout(worker)

    assert recovered is not None
    assert parse_worker_result(task, recovered, "", 0).status == "retry"


def test_codex_parallel_graph_reports_after_decision_has_no_new_tasks(tmp_path):
    artifacts = RunArtifacts.create("10.10.10.10", tmp_path)
    settings = Settings(
        project_root=tmp_path,
        report_dir=tmp_path,
        exploit_dispatch="codex_parallel",
        use_llm=False,
    )
    graph = build_graph(settings=settings, artifacts=artifacts, auto_approve=True)
    final = graph.invoke(
        {
            "target_ip": "10.10.10.10",
            "run_id": artifacts.run_id,
            "run_started_at": time.time(),
            "run_timeout_seconds": 3600,
            "retry_count": 0,
            "max_retries": 1,
            "decision_round": 0,
            "skip_scan": True,
            "artifact_paths": {},
            "allowed_tools": ["searchsploit"],
            "agent_tasks": [],
            "pending_agent_tasks": [],
            "agent_memory": {},
            "agent_results": [],
            "recon_report": ReconReport(
                target_ip="10.10.10.10",
                services=[ServiceFinding(port=80, service_name="http", product="Apache", version="2.4")],
            ),
            "exploit_tasks": [],
            "command_results": [],
            "exploit_results": [],
            "final_report": None,
        }
    )

    assert final["decision_round"] == 2
    assert final["agent_results"]
    assert final["final_report"]["status"] == "failed_or_blocked"
