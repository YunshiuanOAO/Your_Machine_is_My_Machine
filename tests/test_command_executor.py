from pentestagent.observability import RunArtifacts
from pentestagent.config import Settings
from pentestagent.schemas.commands import CommandProposal
from pentestagent.services.executor import add_executor_artifact_args, build_argv, execute_command


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


def test_build_argv_rejects_interactive_when_disabled():
    proposal = CommandProposal(
        task_id="task_1",
        action_type="exploit",
        tool="nc",
        args=["-lvnp", "4444"],
        risk_level="medium",
        requires_interactive=True,
        reasoning="test",
        expected_success_signal="shell",
    )

    try:
        build_argv(proposal, "10.10.10.5", Settings(allowed_tools=("nc",), allow_interactive=False))
    except ValueError as exc:
        assert "allow_interactive" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_execute_interactive_command_starts_tmux_handoff(tmp_path, monkeypatch):
    proposal = CommandProposal(
        task_id="task_1",
        action_type="exploit",
        tool="nc",
        args=["-lvnp", "4444"],
        risk_level="medium",
        requires_interactive=True,
        reasoning="Start an authorized listener for shell handoff.",
        expected_success_signal="operator can attach to listener",
    )
    artifacts = RunArtifacts.create("127.0.0.1", tmp_path)
    seen = {}

    class Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        return Completed()

    monkeypatch.setattr("pentestagent.services.executor.shutil.which", lambda tool: "/usr/bin/tmux" if tool == "tmux" else None)
    monkeypatch.setattr("pentestagent.services.executor.subprocess.run", fake_run)

    result = execute_command(
        proposal,
        "127.0.0.1",
        Settings(allowed_tools=("nc",), allow_interactive=True),
        artifacts,
    )

    assert result.return_code == 0
    assert seen["argv"][:4] == ["/usr/bin/tmux", "new-session", "-d", "-s"]
    assert seen["argv"][-3:] == ["nc", "-lvnp", "4444"]
    assert result.evidence["shell_handoff"]["attach_command"].startswith("tmux attach -t pentest_task_1_")


def test_execute_interactive_command_auto_attaches_when_tty_available(tmp_path, monkeypatch):
    proposal = CommandProposal(
        task_id="task_1",
        action_type="exploit",
        tool="nc",
        args=["-lvnp", "4444"],
        risk_level="medium",
        requires_interactive=True,
        reasoning="Start an authorized listener for shell handoff.",
        expected_success_signal="operator can attach to listener",
    )
    artifacts = RunArtifacts.create("127.0.0.1", tmp_path)
    calls = []

    class Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    class Tty:
        def isatty(self):
            return True

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return Completed()

    monkeypatch.setattr("pentestagent.services.executor.shutil.which", lambda tool: "/usr/bin/tmux" if tool == "tmux" else None)
    monkeypatch.setattr("pentestagent.services.executor.subprocess.run", fake_run)
    monkeypatch.setattr("pentestagent.services.executor.sys.stdin", Tty())
    monkeypatch.setattr("pentestagent.services.executor.sys.stdout", Tty())
    monkeypatch.delenv("TMUX", raising=False)

    result = execute_command(
        proposal,
        "127.0.0.1",
        Settings(allowed_tools=("nc",), allow_interactive=True),
        artifacts,
    )

    assert calls[0][:4] == ["/usr/bin/tmux", "new-session", "-d", "-s"]
    assert calls[1][:3] == ["/usr/bin/tmux", "attach", "-t"]
    assert result.evidence["shell_handoff"]["auto_attached"] is True


def test_dirsearch_executor_adds_json_output_artifact(tmp_path):
    artifacts = RunArtifacts.create("127.0.0.1", tmp_path)
    proposal = CommandProposal(
        task_id="task_1",
        action_type="enumerate",
        tool="dirsearch",
        args=["-u", "http://[TARGET_IP]:3000", "-w", "common.txt"],
        risk_level="low",
        reasoning="test",
        expected_success_signal="json",
    )

    argv = add_executor_artifact_args(
        ["dirsearch", "-u", "http://127.0.0.1:3000", "-w", "common.txt"],
        proposal,
        "cmd_1",
        artifacts,
    )

    assert "--format=json" in argv
    assert "-o" in argv
    assert str(artifacts.run_dir / "commands" / "cmd_1.dirsearch.json") in argv
