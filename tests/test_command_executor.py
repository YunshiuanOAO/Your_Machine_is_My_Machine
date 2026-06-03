from pentestagent.observability import RunArtifacts
from pentestagent.config import Settings
from pentestagent.schemas.commands import CommandProposal
from pentestagent.services.executor import build_argv, execute_command


def test_build_argv_rejects_disallowed_tool():
    proposal = CommandProposal(
        task_id="task_1",
        action_type="enumerate",
        tool="bash",
        args=["-c", "id"],
        risk_level="high",
        reasoning="test",
        expected_success_signal="none",
    )

    try:
        build_argv(proposal, "127.0.0.1", Settings())
    except ValueError as exc:
        assert "allowlisted" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_execute_command_blocks_shell_metacharacters(tmp_path):
    proposal = CommandProposal(
        task_id="task_1",
        action_type="enumerate",
        tool="rustscan",
        args=["-a", "[TARGET_IP];id"],
        risk_level="high",
        reasoning="test",
        expected_success_signal="none",
    )
    artifacts = RunArtifacts.create("127.0.0.1", tmp_path)

    result = execute_command(proposal, "127.0.0.1", Settings(), artifacts)

    assert result.return_code is None
    assert "blocked" in result.summary.lower()


def test_build_argv_replaces_target_placeholder():
    proposal = CommandProposal(
        task_id="task_1",
        action_type="enumerate",
        tool="curl",
        args=["http://[TARGET_IP]/"],
        risk_level="low",
        reasoning="test",
        expected_success_signal="none",
    )

    argv = build_argv(
        proposal,
        "10.10.10.5",
        Settings(allowed_tools=("curl",)),
    )

    assert argv == ["curl", "http://10.10.10.5/"]
