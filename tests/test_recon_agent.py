from pentestagent.tools.dirsearch import normalize_dirsearch_json
from pentestagent.agents.service_analysis import analyze_services
from pentestagent.tools.parsers import parse_dirsearch_results, parse_nmap_service_results, parse_rustscan_results
from pentestagent.schemas.findings import ReconReport, ServiceFinding
from pentestagent.tools.rustscan import parse_open_ports
from pentestagent.tools.scan_runner import select_web_ports


def test_parse_rustscan_results_extracts_ports_from_raw_output():
    services, notes = parse_rustscan_results(
        """
        Open 10.10.10.10:22
        Open 10.10.10.10:80
        """
    )

    assert notes == []
    assert [service.port for service in services] == [22, 80]
    assert [service.service_name for service in services] == ["ssh", "http"]


def test_parse_rustscan_results_rejects_json_artifact():
    services, notes = parse_rustscan_results('{"ports": [80]}')

    assert services == []
    assert notes == ["RustScan artifact must be raw text in RustScan-only mode."]


def test_parse_dirsearch_results_keeps_interesting_paths():
    paths, notes = parse_dirsearch_results(
        [
            {"status": "404", "url": "http://target/missing"},
            {"status": "200", "url": "http://target/login"},
            {"status": "403", "url": "http://target/admin"},
        ]
    )

    assert len(paths) == 2
    assert "Admin-like paths were observed." in notes


def test_parse_dirsearch_results_accepts_native_json_object():
    paths, notes = parse_dirsearch_results(
        {
            "info": {"args": "dirsearch --format=json"},
            "results": [
                {"status": 200, "url": "http://target/login"},
                {"status": 404, "url": "http://target/missing"},
            ],
        }
    )

    assert len(paths) == 1
    assert paths[0]["url"] == "http://target/login"


def test_parse_nmap_service_results_extracts_product_and_version():
    services, notes = parse_nmap_service_results(
        """<?xml version="1.0"?>
<nmaprun>
  <host>
    <ports>
      <port protocol="tcp" portid="22">
        <state state="open"/>
        <service name="ssh" product="OpenSSH" version="8.9p1" extrainfo="Ubuntu Linux"/>
      </port>
      <port protocol="tcp" portid="3000">
        <state state="open"/>
        <service name="http" product="Node.js Express framework"/>
      </port>
    </ports>
  </host>
</nmaprun>
"""
    )

    assert notes == []
    assert [service.port for service in services] == [22, 3000]
    assert services[0].service_name == "ssh"
    assert services[0].product == "OpenSSH"
    assert services[0].version == "8.9p1"
    assert "Ubuntu Linux" in services[0].notes
    assert services[1].service_name == "http"
    assert services[1].product == "Node.js Express framework"


def test_normalize_dirsearch_json_accepts_native_results_object():
    assert normalize_dirsearch_json({"results": [{"status": 200}]}) == [{"status": 200}]


def test_parse_open_ports_from_rustscan_output():
    output = """
    Open 10.10.10.10:22
    Open 10.10.10.10:80
    Open 10.10.10.10:80
    """

    assert parse_open_ports(output) == [22, 80]


def test_select_web_ports_uses_service_name_and_common_ports():
    report = ReconReport(
        target_ip="10.10.10.10",
        services=[
            ServiceFinding(port=22, service_name="ssh"),
            ServiceFinding(port=80, service_name="http"),
            ServiceFinding(port=8443, service_name="unknown"),
        ],
    )

    assert select_web_ports(report) == [80, 8443]


def test_analyze_services_recommends_web_followup_for_nonstandard_http():
    report = ReconReport(
        target_ip="10.10.10.10",
        services=[ServiceFinding(port=3000, service_name="http", product="Node.js Express framework")],
        artifacts={"nmap_service_file": "scan/nmap_service.xml"},
    )

    analyzed = analyze_services(report)

    assert len(analyzed.service_analysis) == 1
    analysis = analyzed.service_analysis[0]
    assert analysis.port == 3000
    assert analysis.category == "web"
    assert "dirsearch" in analysis.recommended_tools
    assert any("path" in action.lower() for action in analysis.recommended_actions)
