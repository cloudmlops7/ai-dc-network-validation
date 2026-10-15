"""Correlate failure-injection evidence into scenario-level findings."""


def correlate_interface_failure(result):
    """Correlate an interface-failure scenario with observed recovery."""

    target = result["target"]
    during = result["during"]
    after = result["after"]

    interface_text = during["interface"]["stdout"].lower()
    bgp_text = during["bgp_summary"]["stdout"].lower()
    during_route = during["route"]["stdout"]
    during_ping_ok = during["ping"]["returncode"] == 0

    after_interface = after["interface"]["stdout"].lower()
    after_ping_ok = after["ping"]["returncode"] == 0

    backup = result["backup_recovery"]
    preferred = result["preferred_recovery"]

    findings = {
        "scenario": result["scenario"],
        "failure_target": (
            f'{target["container"]}:{target["interface"]}'
        ),
        "destination": target["destination"],
        "failure_observed": "down" in interface_text,
        "bgp_impact_observed": (
            "active" in bgp_text
            or "idle" in bgp_text
        ),
        "backup_path_recovered": backup["recovered"],
        "backup_route": during_route,
        "traffic_available_during_failure": during_ping_ok,
        "interface_restored": (
            "up" in after_interface
            and "lower_up" in after_interface
        ),
        "preferred_path_recovered": preferred["recovered"],
        "traffic_available_after_recovery": after_ping_ok,
    }

    if (
        findings["failure_observed"]
        and findings["bgp_impact_observed"]
        and findings["backup_path_recovered"]
    ):
        findings["probable_failure_domain"] = (
            f'{target["container"]}:{target["interface"]} '
            "link/path"
        )
    else:
        findings["probable_failure_domain"] = "undetermined"

    if (
        findings["backup_path_recovered"]
        and findings["traffic_available_during_failure"]
    ):
        findings["service_assessment"] = (
            "Traffic remained reachable through the alternate path."
        )
    else:
        findings["service_assessment"] = (
            "Traffic availability was impacted or backup recovery failed."
        )

    if (
        findings["interface_restored"]
        and findings["preferred_path_recovered"]
        and findings["traffic_available_after_recovery"]
    ):
        findings["recovery_assessment"] = (
            "Interface, preferred path, and reachability recovered."
        )
    else:
        findings["recovery_assessment"] = (
            "Recovery was incomplete or not fully observed."
        )

    return findings
