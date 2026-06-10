import time

from pentestagent.graph.routing import (
    route_after_aggregate,
    route_after_approval,
    route_after_codex_aggregate,
    route_after_codex_decision,
    route_after_decision,
    run_timed_out,
)
from pentestagent.schemas.tasks import ExploitResult


def test_route_after_decision_goes_to_report_without_pending_task():
    assert route_after_decision({"pending_task": None}) == "report"


def test_route_after_approval_requires_explicit_true():
    assert route_after_approval({"approved": True}) == "execute"
    assert route_after_approval({"approved": False}) == "aggregate"


def test_route_after_aggregate_reports_on_success():
    assert route_after_aggregate(
        {
            "exploit_results": [
                ExploitResult(
                    task_id="x",
                    status="success",
                    summary="shell",
                    evidence={"shell_handoff": {"attach_command": "tmux attach -t shell-x"}},
                )
            ]
        }
    ) == "report"


def test_route_after_aggregate_does_not_report_success_without_shell():
    assert route_after_aggregate({"exploit_results": [ExploitResult(task_id="x", status="success", summary="fingerprint only")]}) == "decision"


def test_route_after_aggregate_ignores_retry_limit_and_returns_to_decision():
    assert route_after_aggregate({"retry_count": 2, "max_retries": 2, "exploit_results": []}) == "decision"


def test_route_after_aggregate_returns_to_decision_when_all_tasks_exhausted():
    from pentestagent.schemas.tasks import ExploitTask

    tasks = [
        ExploitTask(task_id="task_1", target_ip="10.10.10.10", service_name="ssh", port=22, hypothesis="h", confidence_score=5),
        ExploitTask(task_id="task_2", target_ip="10.10.10.10", service_name="http", port=3000, hypothesis="h", confidence_score=8),
    ]

    assert route_after_aggregate(
        {
            "exploit_tasks": tasks,
            "exploit_results": [ExploitResult(task_id="task_1", status="retry", summary="retry")],
            "retry_count": 1,
            "max_retries": 1,
        }
    ) == "decision"
    assert route_after_aggregate(
        {
            "exploit_tasks": tasks,
            "exploit_results": [
                ExploitResult(task_id="task_1", status="retry", summary="retry"),
                ExploitResult(task_id="task_2", status="retry", summary="retry"),
            ],
            "retry_count": 2,
            "max_retries": 1,
        }
    ) == "decision"


def test_run_timeout_routes_to_report():
    state = {
        "run_started_at": time.time() - 10,
        "run_timeout_seconds": 1,
        "pending_task": object(),
    }

    assert run_timed_out(state) is True
    assert route_after_decision(state) == "report"
    assert route_after_approval({**state, "approved": True}) == "report"
    assert route_after_aggregate(state) == "report"


def test_codex_routes_fanout_until_success_or_decision_gives_up():
    assert route_after_codex_decision({"pending_agent_tasks": [object()]}) == "fanout"
    assert route_after_codex_decision({"pending_agent_tasks": []}) == "report"
    assert route_after_codex_aggregate({"agent_results": [], "decision_round": 1}) == "decision"
    assert route_after_codex_aggregate({"agent_results": [], "decision_round": 3}) == "decision"
    assert route_after_codex_aggregate({"agent_results": [ExploitResult(task_id="x", status="success", summary="fingerprint only")]}) == "decision"
    assert route_after_codex_aggregate(
        {
            "agent_results": [
                ExploitResult(
                    task_id="x",
                    status="success",
                    summary="shell",
                    evidence={"shell_handoff": {"attach_command": "tmux attach -t shell-x"}},
                )
            ]
        }
    ) == "report"
