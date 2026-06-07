from pentestagent.agents.decision_coordinator import (
    build_history_rag_queries,
    build_heuristic_tasks,
    build_rag_queries,
    run,
    select_pending_task,
)
from pentestagent.config import Settings
from pentestagent.schemas.findings import ReconReport, ServiceAnalysis, ServiceFinding
from pentestagent.schemas.tasks import ExploitResult
from pentestagent.services.llm import ClaudeJSONClient


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


def test_build_heuristic_tasks_uses_service_analysis_priority():
    report = ReconReport(
        target_ip="10.10.10.10",
        services=[
            ServiceFinding(port=22, service_name="ssh", product="OpenSSH", version="9.6"),
            ServiceFinding(port=3000, service_name="ppp"),
        ],
        service_analysis=[
            ServiceAnalysis(
                port=22,
                service_name="ssh",
                category="remote_access",
                priority=6,
                summary="SSH access surface.",
            ),
            ServiceAnalysis(
                port=3000,
                service_name="ppp",
                category="web",
                priority=8,
                summary="Likely web service needs follow-up.",
            ),
        ],
    )

    tasks = build_heuristic_tasks(report, [], Settings(max_tasks=2))

    assert [task.port for task in tasks] == [3000, 22]


def test_select_pending_task_rotates_to_unattempted_tasks_before_retries():
    tasks = build_heuristic_tasks(
        ReconReport(
            target_ip="10.10.10.10",
            services=[
                ServiceFinding(port=3000, service_name="http"),
                ServiceFinding(port=22, service_name="ssh"),
            ],
        ),
        [],
        Settings(max_tasks=2),
    )

    first = select_pending_task(tasks, [], retry_count=0, max_retries=2)
    second = select_pending_task(
        tasks,
        [ExploitResult(task_id=first.task_id, status="retry", summary="needs follow-up")],
        retry_count=1,
        max_retries=2,
    )

    assert second is not None
    assert second.task_id != first.task_id


def test_select_pending_task_skips_replan_requested_task():
    tasks = build_heuristic_tasks(
        ReconReport(
            target_ip="10.10.10.10",
            services=[
                ServiceFinding(port=3000, service_name="http"),
            ],
        ),
        [],
        Settings(max_tasks=1),
    )

    selected = select_pending_task(
        tasks,
        [
            ExploitResult(
                task_id=tasks[0].task_id,
                status="retry",
                summary="needs decision",
                evidence={"decision_replan": True},
            )
        ],
        retry_count=1,
        max_retries=1,
    )

    assert selected is None


def test_decision_replan_stops_after_no_progress_round_limit():
    tasks = build_heuristic_tasks(
        ReconReport(
            target_ip="10.10.10.10",
            services=[
                ServiceFinding(port=3000, service_name="http"),
            ],
        ),
        [],
        Settings(max_tasks=1),
    )
    settings = Settings(
        max_tasks=1,
        use_llm=False,
        decision_backend="codex",
        codex_decision_worker_command=None,
        decision_max_rounds=1,
    )

    result = run(
        {
            "recon_report": ReconReport(
                target_ip="10.10.10.10",
                services=[ServiceFinding(port=3000, service_name="http")],
            ),
            "exploit_tasks": tasks,
            "exploit_results": [
                ExploitResult(
                    task_id=tasks[0].task_id,
                    status="retry",
                    summary="needs decision",
                    evidence={"decision_replan": True},
                )
            ],
            "decision_round": 10,
            "max_decision_rounds": 1,
        },
        settings=settings,
        llm_client=ClaudeJSONClient(settings),
    )

    assert result["pending_task"] is None
    assert result["latest_exploit_result"].status == "blocked"
    assert "Decision stopped after repeated no-progress" in result["latest_exploit_result"].summary
    assert result["exploit_results"][-1].task_id == "decision:no-progress"


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
