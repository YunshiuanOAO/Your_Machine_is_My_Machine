from pentestagent.agents.decision_coordinator import (
    build_history_rag_queries,
    build_heuristic_tasks,
    build_rag_queries,
    run,
    select_pending_task,
)
from pentestagent.config import Settings
from pentestagent.schemas.findings import ReconReport, ServiceAnalysis, ServiceFinding
from pentestagent.schemas.tasks import AgentRunResult, ExploitResult
from pentestagent.services.llm import ClaudeJSONClient


def test_build_heuristic_tasks_prefers_versioned_web_services():
    report = ReconReport(
        target_ip="10.10.10.10",
        services=[
            ServiceFinding(port=22, service_name="ssh"),
            ServiceFinding(port=80, service_name="http", product="Apache", version="2.4.54"),
        ],
    )

    tasks = build_heuristic_tasks(report, ["context"], Settings())

    assert len(tasks) == 2
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

    tasks = build_heuristic_tasks(report, ["generic context"], Settings(max_rag_snippets=3))

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

    tasks = build_heuristic_tasks(report, [], Settings())

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
        Settings(),
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
        Settings(),
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


def test_decision_replan_does_not_stop_on_round_limit():
    tasks = build_heuristic_tasks(
        ReconReport(
            target_ip="10.10.10.10",
            services=[
                ServiceFinding(port=3000, service_name="http"),
            ],
        ),
        [],
        Settings(),
    )
    settings = Settings(
        use_llm=False,
        decision_backend="codex",
        codex_decision_worker_command=None,
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
        },
        settings=settings,
        llm_client=ClaudeJSONClient(settings),
    )

    assert result["pending_task"] is None
    assert "latest_exploit_result" not in result
    assert result["decision_round"] == 11


def test_codex_parallel_dispatches_all_decision_tasks():
    settings = Settings(
        exploit_dispatch="codex_parallel",
        use_llm=False,
        decision_backend="codex",
        codex_decision_worker_command=None,
    )

    result = run(
        {
            "recon_report": ReconReport(
                target_ip="10.10.10.10",
                services=[
                    ServiceFinding(port=80, service_name="http"),
                    ServiceFinding(port=21, service_name="ftp"),
                    ServiceFinding(port=22, service_name="ssh"),
                ],
            ),
            "agent_results": [],
            "agent_tasks": [],
            "decision_round": 0,
        },
        settings=settings,
        llm_client=ClaudeJSONClient(settings),
    )

    assert len(result["agent_tasks"]) == 3
    assert len(result["pending_agent_tasks"]) == 3


def test_codex_parallel_runs_backlog_before_new_decision():
    settings = Settings(
        exploit_dispatch="codex_parallel",
        use_llm=False,
        decision_backend="codex",
        codex_decision_worker_command=None,
    )
    tasks = build_heuristic_tasks(
        ReconReport(
            target_ip="10.10.10.10",
            services=[
                ServiceFinding(port=80, service_name="http"),
                ServiceFinding(port=21, service_name="ftp"),
                ServiceFinding(port=22, service_name="ssh"),
            ],
        ),
        [],
        Settings(),
    )
    agent_tasks = [task.to_spawn_task([]) for task in tasks]

    result = run(
        {
            "recon_report": ReconReport(
                target_ip="10.10.10.10",
                services=[
                    ServiceFinding(port=80, service_name="http"),
                    ServiceFinding(port=21, service_name="ftp"),
                    ServiceFinding(port=22, service_name="ssh"),
                ],
            ),
            "agent_tasks": agent_tasks,
            "agent_results": [
                AgentRunResult(task_id=agent_tasks[0].task_id, agent_kind="exploit", status="failed", summary="no path"),
                AgentRunResult(task_id=agent_tasks[1].task_id, agent_kind="exploit", status="retry", summary="needs follow-up"),
            ],
            "decision_round": 1,
        },
        settings=settings,
        llm_client=ClaudeJSONClient(settings),
    )

    assert [task.task_id for task in result["pending_agent_tasks"]] == [agent_tasks[2].task_id]
    assert len(result["agent_tasks"]) == 3


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
