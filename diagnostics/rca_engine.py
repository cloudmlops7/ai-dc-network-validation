"""Evidence-based, rule-driven RCA for network validation failures."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    summary: str
    evidence: str
    possible_cause: str
    recommendation: str


def analyze_evidence(evidence: str) -> list[dict]:
    """Return possible causes supported by diagnostic text.

    This is a lightweight rule engine, not an AI model or a definitive
    root-cause detector. Findings depend on the supplied evidence.
    """
    text = evidence or ""
    lower = text.lower()
    findings: list[Finding] = []

    def add(rule_id, severity, summary, matched_evidence, cause, recommendation):
        findings.append(Finding(
            rule_id=rule_id,
            severity=severity,
            summary=summary,
            evidence=matched_evidence,
            possible_cause=cause,
            recommendation=recommendation,
        ))

    if "show bgp" in lower and (
        "active" in lower or "(policy)" in lower or "idle" in lower
    ):
        add(
            "BGP-NEIGHBOR-STATE",
            "high",
            "BGP output may indicate a neighbor that is not established.",
            "BGP output contains Active, Idle, or (Policy).",
            "Peer reachability, configuration, address-family, or policy issue.",
            "Check peer IP/AS, TCP port 179 reachability, BGP logs, and policies.",
        )

    if "show ip ospf neighbor" in lower and (
        "init/" in lower or "exstart/" in lower or "exchange/" in lower
        or "loading/" in lower or "down/" in lower
    ):
        add(
            "OSPF-NEIGHBOR-STATE",
            "high",
            "OSPF neighbor output may show an adjacency that is not Full.",
            "OSPF neighbor output contains a non-Full state.",
            "Possible interface, area, timer, MTU, authentication, or adjacency issue.",
            "Inspect both peers, interface state, area settings, timers, and MTU.",
        )

    if (
        "network is unreachable" in lower
        or "destination host unreachable" in lower
        or "no route to host" in lower
    ):
        add(
            "ROUTE-REACHABILITY",
            "high",
            "The captured output reports a network or host reachability error.",
            "Diagnostic output contains an unreachable/no-route message.",
            "A route may be missing, withdrawn, or not yet converged.",
            "Inspect the route table, next hop, interface state, and convergence timeline.",
        )

    if (
        "100% packet loss" in lower
        or "0 packets received" in lower
    ):
        add(
            "PING-LOSS",
            "high",
            "The captured ping result indicates complete packet loss.",
            "Ping summary reports 100% loss or zero replies.",
            "Possible forwarding, routing, destination, or return-path failure.",
            "Check forward and return routes, interface counters, and destination reachability.",
        )

    if not findings:
        add(
            "INSUFFICIENT-EVIDENCE",
            "info",
            "No recognized failure signature was found in the supplied evidence.",
            "No configured rule matched the diagnostic text.",
            "The available evidence is insufficient to suggest a specific cause.",
            "Collect relevant neighbor state, route output, interface state, and ping results.",
        )

    return [asdict(finding) for finding in findings]
