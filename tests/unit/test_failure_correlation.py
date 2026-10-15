from failure_injection.correlation import correlate_interface_failure


def make_result():
    return {
        "scenario": "interface_failure",
        "target": {
            "container": "clab-bgpline-r1",
            "interface": "eth2",
            "destination": "3.3.3.3",
        },
        "during": {
            "interface": {
                "stdout": "eth2 DOWN <BROADCAST,MULTICAST>",
            },
            "bgp_summary": {
                "stdout": "10.0.13.2 Active",
            },
            "route": {
                "stdout": "3.3.3.3 via 10.0.12.2 dev eth1",
            },
            "ping": {
                "returncode": 0,
            },
        },
        "after": {
            "interface": {
                "stdout": "eth2 UP <BROADCAST,MULTICAST,UP,LOWER_UP>",
            },
            "ping": {
                "returncode": 0,
            },
        },
        "backup_recovery": {
            "recovered": True,
        },
        "preferred_recovery": {
            "recovered": True,
        },
    }


def test_correlate_successful_failover_and_recovery():
    result = correlate_interface_failure(make_result())

    assert result["failure_observed"] is True
    assert result["bgp_impact_observed"] is True
    assert result["backup_path_recovered"] is True
    assert result["traffic_available_during_failure"] is True

    assert result["probable_failure_domain"] == (
        "clab-bgpline-r1:eth2 link/path"
    )

    assert result["interface_restored"] is True
    assert result["preferred_path_recovered"] is True
    assert result["traffic_available_after_recovery"] is True

    assert result["service_assessment"] == (
        "Traffic remained reachable through the alternate path."
    )

    assert result["recovery_assessment"] == (
        "Interface, preferred path, and reachability recovered."
    )


def test_correlate_failed_backup_recovery():
    scenario = make_result()

    scenario["backup_recovery"]["recovered"] = False
    scenario["during"]["ping"]["returncode"] = 1

    result = correlate_interface_failure(scenario)

    assert result["backup_path_recovered"] is False
    assert result["traffic_available_during_failure"] is False

    assert result["probable_failure_domain"] == "undetermined"

    assert result["service_assessment"] == (
        "Traffic availability was impacted or backup recovery failed."
    )
