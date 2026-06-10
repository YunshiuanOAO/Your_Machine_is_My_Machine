import subprocess

from pentestagent import main as main_module
from pentestagent.main import (
    attach_interactive_shell,
    extract_relay_output,
    first_tmux_handoff,
    run_tmux_interactive,
    sh_single_quote,
    tmux_session_from_attach,
)


def test_tmux_session_from_attach_command():
    assert tmux_session_from_attach("tmux attach -t web-shell") == "web-shell"
    assert tmux_session_from_attach("tmux attach-session -t web-shell") == "web-shell"
    assert tmux_session_from_attach("ssh user@host") is None


def test_first_tmux_handoff_prefers_recorded_session_id():
    shell_access = {
        "handoffs": [
            {"task_id": "web", "session_id": "recorded-session", "attach_command": "tmux attach -t other"},
        ]
    }

    assert first_tmux_handoff(shell_access) == {"task_id": "web", "session": "recorded-session"}


def test_attach_interactive_shell_uses_selected_tmux_session(monkeypatch):
    calls = []

    monkeypatch.setattr(main_module.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(main_module.sys.stdout, "isatty", lambda: True)

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(main_module.subprocess, "run", fake_run)
    monkeypatch.setattr(main_module, "run_tmux_interactive", lambda session: calls.append((["interactive", session], {})))

    attach_interactive_shell({"handoffs": [{"task_id": "web", "session_id": "web80_2million_rce"}]})

    assert calls[0][0] == ["tmux", "has-session", "-t", "web80_2million_rce"]
    assert calls[1][0] == ["interactive", "web80_2million_rce"]


def test_run_tmux_interactive_spawns_pty_for_tmux_attach(monkeypatch):
    calls = []

    monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.setattr(main_module.pty, "spawn", lambda argv: calls.append(argv) or 0)

    run_tmux_interactive("http_nginx_rce")

    assert calls == [["tmux", "attach-session", "-t", "http_nginx_rce"]]


def test_extract_relay_output_returns_only_current_command_output():
    pane = """
old command
old output
printf '__PENTEST_RELAY_START_abc'
__PENTEST_RELAY_START_abc
id
uid=33(www-data) gid=33(www-data)
printf '__PENTEST_RELAY_END_def'
__PENTEST_RELAY_END_def
prompt$
"""

    assert extract_relay_output(pane, "__PENTEST_RELAY_START_abc", "__PENTEST_RELAY_END_def") == (
        "id\nuid=33(www-data) gid=33(www-data)"
    )


def test_sh_single_quote_escapes_embedded_quotes():
    assert sh_single_quote("printf 'x'") == "'printf '\"'\"'x'\"'\"''"
