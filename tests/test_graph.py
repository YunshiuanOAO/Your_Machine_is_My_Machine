from pentestagent.graph.routing import route_after_aggregate, route_after_approval, route_after_decision
from pentestagent.schemas.tasks import ExploitResult


def test_route_after_decision_goes_to_report_without_pending_task():
    assert route_after_decision({"pending_task": None}) == "report"


def test_route_after_approval_requires_explicit_true():
    assert route_after_approval({"approved": True}) == "execute"
    assert route_after_approval({"approved": False}) == "aggregate"


def test_route_after_aggregate_reports_on_success():
    assert route_after_aggregate({"exploit_results": [ExploitResult(task_id="x", status="success", summary="ok")]}) == "report"

