from pentestagent.agents.decision_coordinator import build_history_rag_queries, build_heuristic_tasks, build_rag_queries
from pentestagent.config import Settings
from pentestagent.schemas.findings import ReconReport, ServiceFinding
from pentestagent.schemas.tasks import ExploitResult


def test_build_heuristic_tasks_prefers_versioned_web_services():
    report = ReconReport(
        target_ip="10.10.10.10",
        services=[
            ServiceFinding(port=22, service_name="ssh"),
            ServiceFinding(port=80, service_name="http", product="Apache", version="2.4.54"),
        ],
    )

    tasks = build_heuristic_tasks(report, ["context"], Settings(max_tasks=1))

    assert len(tasks) == 1
    assert tasks[0].port == 80
    assert tasks[0].context_snippets == ["context"]


def test_build_rag_queries_adds_spip_context():
    report = ReconReport(
        target_ip="10.10.10.10",
        services=[ServiceFinding(port=80, service_name="http", product="SPIP", version="4.2")],
    )

    queries = build_rag_queries(report)

    assert "SPIP CMS metasploit module exploitation checklist" in queries


def test_build_history_rag_queries_detects_root_progress():
    queries = build_history_rag_queries(
        {
            "exploit_results": [
                ExploitResult(task_id="task_1", status="retry", summary="Got uid=0 root output")
            ],
            "command_results": [],
        }
    )

    assert "linux post exploitation evidence collection after root shell" in queries
