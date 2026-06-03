import termios

from pentestagent.services import approval


class FakeStdin:
    def isatty(self):
        return True

    def fileno(self):
        return 123


def test_restore_terminal_echo_reenables_echo(monkeypatch):
    calls = []

    monkeypatch.setattr(approval.sys, "stdin", FakeStdin())
    monkeypatch.setattr(approval.termios, "tcgetattr", lambda fd: [0, 0, 0, 0, 0, 0, []])
    monkeypatch.setattr(approval.termios, "tcsetattr", lambda fd, when, attrs: calls.append((fd, when, attrs)))

    approval.restore_terminal_echo()

    assert calls == [(123, termios.TCSADRAIN, [0, 0, 0, termios.ECHO, 0, 0, []])]


def test_restore_terminal_echo_leaves_non_tty_alone(monkeypatch):
    class NonTtyStdin:
        def isatty(self):
            return False

    monkeypatch.setattr(approval.sys, "stdin", NonTtyStdin())
    monkeypatch.setattr(
        approval.termios,
        "tcgetattr",
        lambda fd: (_ for _ in ()).throw(AssertionError("tcgetattr should not be called")),
    )

    approval.restore_terminal_echo()
