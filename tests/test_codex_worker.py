import time

from pentestagent.config import Settings
from pentestagent.graph.builder import build_graph
from pentestagent.observability import RunArtifacts
from pentestagent.schemas.findings import ReconReport, ServiceFinding
from pentestagent.schemas.tasks import SpawnAgentTask
from pentestagent.services.codex_worker import run_codex_exploit_fanout


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


def test_codex_parallel_graph_reports_after_decision_has_no_new_tasks(tmp_path):
    artifacts = RunArtifacts.create("10.10.10.10", tmp_path)
    settings = Settings(
        project_root=tmp_path,
        report_dir=tmp_path,
        exploit_dispatch="codex_parallel",
        decision_max_rounds=1,
        max_parallel_exploit_agents=2,
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
            "max_decision_rounds": 1,
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
