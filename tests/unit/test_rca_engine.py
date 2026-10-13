from diagnostics.rca_engine import analyze_evidence


def test_detects_bgp_neighbor_warning():
    findings = analyze_evidence(
        "show bgp ipv4 unicast summary\n10.0.13.2 Active"
    )
    assert findings[0]["rule_id"] == "BGP-NEIGHBOR-STATE"
    assert findings[0]["severity"] == "high"


def test_detects_non_full_ospf_neighbor():
    findings = analyze_evidence(
        "show ip ospf neighbor\n2.2.2.2 ExStart/- 10.0.12.2"
    )
    assert findings[0]["rule_id"] == "OSPF-NEIGHBOR-STATE"


def test_detects_unreachable_message():
    findings = analyze_evidence("ping: sendto: Network is unreachable")
    assert findings[0]["rule_id"] == "ROUTE-REACHABILITY"


def test_detects_complete_ping_loss():
    findings = analyze_evidence(
        "3 packets transmitted, 0 packets received, 100% packet loss"
    )
    assert findings[0]["rule_id"] == "PING-LOSS"


def test_unknown_evidence_does_not_guess():
    findings = analyze_evidence("Everything looks normal.")
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "INSUFFICIENT-EVIDENCE"
    assert "insufficient" in findings[0]["possible_cause"].lower()


def test_empty_evidence_is_handled():
    findings = analyze_evidence("")
    assert findings[0]["rule_id"] == "INSUFFICIENT-EVIDENCE"
