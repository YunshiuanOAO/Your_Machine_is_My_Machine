import pytest
from pydantic import ValidationError

from pentestagent.schemas.tasks import AgentRunResult, ExploitTask, SpawnAgentTask


def test_exploit_task_converts_to_spawn_task_with_memory_budget():
    task = ExploitTask(
        task_id="task_1",
        target_ip="10.10.10.10",
        service_name="http",
        port=80,
        cve_id="CVE-2024-1234",
        hypothesis="Apache version appears vulnerable.",
        confidence_score=8,
        context_snippets=["Apache CVE context"],
        max_steps=5,
    )

    spawned = task.to_spawn_task(["searchsploit", "msfconsole", "curl"])

    assert spawned.agent_kind == "exploit"
    assert spawned.objective == task.hypothesis
    assert spawned.cve_ids == ["CVE-2024-1234"]
    assert spawned.scope == ["http", "port:80"]
    assert spawned.allowed_tools == ["searchsploit", "msfconsole", "curl"]
    assert spawned.budget.max_steps == 5
    assert spawned.memory_key == "task_1"


def test_breadth_research_result_can_spawn_cve_scoped_exploit_task():
    exploit_task = SpawnAgentTask(
        task_id="exploit_cve_1",
        agent_kind="exploit",
        target_ip="10.10.10.10",
        objective="Validate CVE-2024-1234 against the HTTP service.",
        scope=["http", "port:80"],
        service_name="http",
        port=80,
        cve_ids=["CVE-2024-1234"],
        hypothesis="Observed version matches the vulnerable range.",
        allowed_tools=["searchsploit", "curl"],
        success_criteria=["Confirm exploitability or document why the CVE does not apply."],
    )

    result = AgentRunResult(
        task_id="breadth_1",
        agent_kind="breadth_research",
        status="success",
        summary="Found one version-matched CVE candidate.",
        spawned_tasks=[exploit_task],
    )

    assert result.spawned_tasks[0].agent_kind == "exploit"
    assert result.spawned_tasks[0].cve_ids == ["CVE-2024-1234"]


def test_spawn_agent_task_rejects_unknown_agent_kind():
    with pytest.raises(ValidationError):
        SpawnAgentTask(
            task_id="bad",
            agent_kind="scanner",
            target_ip="10.10.10.10",
            objective="unsupported",
        )
