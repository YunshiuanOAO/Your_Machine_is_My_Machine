import json

from pentestagent.config import Settings
from pentestagent.observability import JsonlLogger
from pentestagent.schemas.findings import ReconReport, ServiceFinding
from pentestagent.services.codex_decision import (
    build_decision_payload,
    enrich_tasks_with_vulnerability_candidates,
    parse_json_object,
    parse_searchsploit_output,
    run_codex_decision,
)


def test_build_codex_decision_payload_contains_recon_and_constraints():
    report = ReconReport(
        target_ip="10.10.10.10",
        services=[ServiceFinding(port=3000, service_name="http")],
    )

    payload = build_decision_payload(report, ["context"], Settings(max_tasks=2), {"exploit_results": []})

    assert payload["target_ip"] == "10.10.10.10"
    assert payload["recon_report"]["services"][0]["port"] == 3000
    assert payload["context_snippets"] == ["context"]
    assert payload["max_tasks"] == 2
    assert "vulnerability_candidates" in payload


def test_parse_searchsploit_output_extracts_cve_and_path():
    output = """
Exploit Title                                      |  Path
-------------------------------------------------- ---------------------------------
Next.js Middleware 15.2.2 CVE-2025-29927 - Auth Bypass | multiple/webapps/52124.txt
"""

    parsed = parse_searchsploit_output(output)

    assert parsed == [
        {
            "title": "Next.js Middleware 15.2.2 CVE-2025-29927 - Auth Bypass",
            "path": "multiple/webapps/52124.txt",
            "cve_ids": ["CVE-2025-29927"],
        }
    ]


def test_enrich_tasks_with_vulnerability_candidates_adds_cve_context():
    from pentestagent.schemas.tasks import ExploitTask

    task = ExploitTask(
        task_id="web3000-chain",
        target_ip="10.10.10.10",
        service_name="http",
        port=3000,
        hypothesis="Test Next.js middleware bypass",
        confidence_score=8,
    )
    candidates = [
        {
            "source": "searchsploit",
            "query": "Next.js 15.2.2",
            "service_name": "http",
            "port": 3000,
            "title": "Next.js Middleware 15.2.2 CVE-2025-29927 - Auth Bypass",
            "path": "multiple/webapps/52124.txt",
            "cve_ids": ["CVE-2025-29927"],
        }
    ]

    enriched = enrich_tasks_with_vulnerability_candidates([task], candidates)[0]

    assert enriched.cve_ids == ["CVE-2025-29927"]
    assert "searchsploit:Next.js 15.2.2:multiple/webapps/52124.txt" in enriched.evidence_refs
    assert "CVE-2025-29927" in enriched.context_snippets[0]


def test_parse_json_object_accepts_fenced_json():
    parsed = parse_json_object('```json\n{"tasks": []}\n```')

    assert parsed == {"tasks": []}


def test_run_codex_decision_returns_none_when_not_configured():
    report = ReconReport(
        target_ip="10.10.10.10",
        services=[ServiceFinding(port=80, service_name="http")],
    )

    tasks = run_codex_decision(
        report,
        [],
        Settings(decision_backend="codex", codex_decision_worker_command=None),
        {},
    )

    assert tasks is None


def test_run_codex_decision_validates_worker_tasks(tmp_path):
    worker = tmp_path / "worker.py"
    worker.write_text(
        "import json, sys\n"
        "json.load(sys.stdin)\n"
        "print(json.dumps({'tasks': [{'task_id': 'task_1', 'target_ip': '10.10.10.10', "
        "'service_name': 'http', 'port': 80, 'hypothesis': 'web service needs follow-up', "
        "'confidence_score': 7}]}))\n",
        encoding="utf-8",
    )
    report = ReconReport(target_ip="10.10.10.10", services=[ServiceFinding(port=80, service_name="http")])

    tasks = run_codex_decision(
        report,
        [],
        Settings(
            project_root=tmp_path,
            decision_backend="codex",
            codex_decision_worker_command=f"python {worker}",
        ),
        {},
    )

    assert tasks is not None
    assert len(tasks) == 1
    assert tasks[0].task_id == "task_1"


def test_run_codex_decision_worker_failure_falls_back(tmp_path):
    worker = tmp_path / "worker.py"
    worker.write_text(
        "import json, sys\n"
        "json.load(sys.stdin)\n"
        "print(json.dumps({'status': 'failed', 'summary': 'codex unavailable', 'tasks': [], "
        "'evidence': {'error': 'read-only file system'}}))\n",
        encoding="utf-8",
    )
    report = ReconReport(target_ip="10.10.10.10", services=[ServiceFinding(port=80, service_name="http")])
    logger = JsonlLogger(tmp_path / "run" / "events.jsonl")

    tasks = run_codex_decision(
        report,
        [],
        Settings(
            project_root=tmp_path,
            decision_backend="codex",
            codex_decision_worker_command=f"python {worker}",
        ),
        {},
        logger=logger,
    )

    events = (tmp_path / "run" / "events.jsonl").read_text(encoding="utf-8")
    assert tasks is None
    assert "codex_decision_worker_reported_failure" in events
    assert (tmp_path / "run" / "codex_decision" / "stdout.txt").exists()
