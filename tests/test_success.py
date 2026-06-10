from types import SimpleNamespace

from pentestagent.services.success import extract_shell_handoff, result_satisfies_run_goal


def test_fifo_file_handoff_is_not_operator_attachable():
    evidence = {
        "shell_handoff": {
            "session_type": "reverse_shell_fifo_listener",
            "attach_command": "Read output with: tail -f /tmp/shell.out ; send commands with: printf 'id\\n' > /tmp/shell.in",
        }
    }

    assert extract_shell_handoff(evidence) is None
    assert not result_satisfies_run_goal(SimpleNamespace(status="success", evidence=evidence))


def test_tmux_handoff_is_operator_attachable():
    evidence = {
        "shell_handoff": {
            "session_type": "tmux",
            "attach_command": "tmux attach -t 2million-www-shell",
        }
    }

    assert extract_shell_handoff(evidence)["attach_command"] == "tmux attach -t 2million-www-shell"
    assert result_satisfies_run_goal(SimpleNamespace(status="success", evidence=evidence))
