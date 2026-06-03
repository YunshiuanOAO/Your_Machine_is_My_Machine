from auto_pentest.decision import DecisionEngine
from auto_pentest.models import AgentState, ReconReport, Service


def test_seed_tasks_from_common_services():
    state = AgentState(target="10.10.10.10", workdir="/tmp/run", created_at="now", max_turns=5)
    recon = ReconReport(
        target="10.10.10.10",
        scan_time="now",
        open_ports=[
            Service(port=80, service="http", product="Apache httpd", version="2.4.49"),
            Service(port=21, service="ftp"),
            Service(port=445, service="microsoft-ds"),
        ],
    )

    engine = DecisionEngine()
    engine.seed_tasks(state, recon)

    agents = [task.assigned_agent for task in state.tasks]
    assert "web" in agents
    assert "ftp" in agents
    assert "smb" in agents
    assert "cve" in agents


def test_choose_next_marks_task_running():
    state = AgentState(target="10.10.10.10", workdir="/tmp/run", created_at="now", max_turns=5)
    recon = ReconReport(target="10.10.10.10", scan_time="now", open_ports=[Service(port=80, service="http")])
    engine = DecisionEngine()
    engine.seed_tasks(state, recon)

    decision = engine.choose_next(state, turn=1)

    assert decision.selected_task is not None
    assert decision.selected_task.assigned_agent == "web"
    assert decision.selected_task.status == "running"
