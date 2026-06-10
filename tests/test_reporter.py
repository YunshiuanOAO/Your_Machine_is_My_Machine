from pentestagent.observability import RunArtifacts
from pentestagent.schemas.tasks import ExploitResult
from pentestagent.services.reporter import build_final_report


def test_success_report_includes_shell_handoff(tmp_path):
    artifacts = RunArtifacts(run_id="run-1", run_dir=tmp_path)
    result = ExploitResult(
        task_id="task-web",
        status="success",
        summary="Verified attachable shell session.",
        evidence={
            "shell_handoff": {
                "session_type": "tmux",
                "session_id": "shell-task-web",
                "attach_command": "tmux attach -t shell-task-web",
                "username": "www-data",
            }
        },
    )

    report = build_final_report(
        {
            "target_ip": "10.10.10.10",
            "run_id": "run-1",
            "exploit_results": [result],
        },
        artifacts,
    )

    assert report["status"] == "success"
    assert report["shell_access"]["available"] is True
    assert report["shell_access"]["handoffs"][0]["attach_command"] == "tmux attach -t shell-task-web"
    assert report["artifacts"]["skill"].endswith("success_skill/SKILL.md")
    assert (tmp_path / "success_skill" / "SKILL.md").exists()
    assert "## Shell Access" in (tmp_path / "final_report.md").read_text(encoding="utf-8")
    assert "tmux attach -t shell-task-web" in (tmp_path / "final_report.md").read_text(encoding="utf-8")
    assert "Success skill:" in (tmp_path / "final_report.md").read_text(encoding="utf-8")


def test_success_report_does_not_claim_shell_without_handoff(tmp_path):
    artifacts = RunArtifacts(run_id="run-1", run_dir=tmp_path)
    result = ExploitResult(
        task_id="task-web",
        status="success",
        summary="Exploitability marker was observed.",
    )

    report = build_final_report(
        {
            "target_ip": "10.10.10.10",
            "run_id": "run-1",
            "exploit_results": [result],
        },
        artifacts,
    )

    assert report["status"] == "failed_or_blocked"
    assert report["shell_access"]["available"] is False
    assert "skill" not in report["artifacts"]
    assert not (tmp_path / "success_skill" / "SKILL.md").exists()
    assert "No interactive shell handoff was recorded" in report["shell_access"]["note"]
