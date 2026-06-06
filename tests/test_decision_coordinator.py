from pentestagent.agents.decision_coordinator import build_history_rag_queries, build_heuristic_tasks, build_rag_queries
from pentestagent.config import Settings
from pentestagent.schemas.findings import ReconReport, ServiceAnalysis, ServiceFinding
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
    assert tasks[0].objective
    assert tasks[0].success_criteria
    assert tasks[0].memory_key == tasks[0].task_id


def test_build_rag_queries_adds_spip_context():
    report = ReconReport(
        target_ip="10.10.10.10",
        services=[ServiceFinding(port=80, service_name="http", product="SPIP", version="4.2")],
    )

    queries = build_rag_queries(report)

    assert "SPIP CMS metasploit module exploitation checklist" in queries


def test_build_heuristic_tasks_includes_recon_service_analysis_context():
    report = ReconReport(
        target_ip="10.10.10.10",
        services=[ServiceFinding(port=3000, service_name="http", product="Node.js Express framework")],
        service_analysis=[
            ServiceAnalysis(
                port=3000,
                service_name="http",
                category="web",
                priority=9,
                summary="HTTP service needs path discovery.",
                evidence_refs=["scan/nmap_service.xml"],
                recommended_tools=["curl", "dirsearch"],
                recommended_actions=["Run path discovery against this one web service."],
                followup_questions=["Are admin or API paths exposed?"],
            )
        ],
    )

    tasks = build_heuristic_tasks(report, ["generic context"], Settings(max_tasks=1, max_rag_snippets=3))

    assert tasks[0].port == 3000
    assert "Recon service analysis for port 3000/http" in tasks[0].context_snippets[0]
    assert tasks[0].evidence_refs == ["scan/nmap_service.xml"]
    assert "dirsearch" in tasks[0].context_snippets[0]


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
