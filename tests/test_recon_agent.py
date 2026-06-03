from pentestagent.tools.parsers import parse_dirsearch_results, parse_rustscan_results
from pentestagent.schemas.findings import ReconReport, ServiceFinding
from pentestagent.tools.rustscan import parse_open_ports
from pentestagent.tools.scan_runner import select_web_ports


def test_parse_rustscan_results_extracts_single_service():
    data = {
        "nmaprun": {
            "host": {
                "ports": {
                    "port": {
                        "@portid": "80",
                        "service": {
                            "@name": "http",
                            "@product": "Apache httpd",
                            "@version": "2.4.54",
                        },
                    }
                }
            }
        }
    }

    services, notes = parse_rustscan_results(data)

    assert notes == []
    assert len(services) == 1
    assert services[0].port == 80
    assert services[0].display_name == "http Apache httpd 2.4.54"


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
