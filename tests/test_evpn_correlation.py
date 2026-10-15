import pytest
from failure_injection.evpn_correlation import (
    correlate_evpn_failure,
)


def test_evpn_failure_correlation():
    evidence = {
        "environment": {
            "failure_injection": "leaf1 eth1 down",
        },
        "trials": [
            {
                "trial": 1,
                "failure_detection": 1.30,
                "path_2_to_1": 1.60,
                "path_1_to_2": 1.50,
                "failed_probe_times_after_injection_seconds": [
                    1.18
                ],
            },
            {
                "trial": 2,
                "failure_detection": 1.25,
                "path_2_to_1": 1.55,
                "path_1_to_2": 1.60,
                "failed_probe_times_after_injection_seconds": [],
            },
        ],
        "aggregate": {
            "traffic": {
                "total_probes": 80,
                "passed": 79,
                "failed": 1,
                "success_rate_percent": 98.75,
            }
        },
    }

    result = correlate_evpn_failure(evidence)

    assert result["failure_stimulus"] == "leaf1 eth1 down"
    assert result["neighbor_failure_detected"] is True
    assert result["path_reduction_detected"] is True
    assert result["path_restoration_detected"] is True

    assert result["traffic_impact"] == "isolated_sampled_loss"
    assert result["failed_probes"] == 1
    assert result["traffic_success_rate_percent"] == 98.75

    correlation = result["packet_impact_correlation"]

    assert len(correlation) == 1
    assert correlation[0]["trial"] == 1
    assert correlation[0][
        "failed_probe_after_injection_seconds"
    ] == 1.18

    assert correlation[0][
        "delta_from_neighbor_detection_seconds"
    ] == pytest.approx(-0.12)

def test_evpn_failure_without_sampled_loss():
    evidence = {
        "environment": {
            "failure_injection": "leaf1 eth1 down",
        },
        "trials": [
            {
                "trial": 1,
                "failure_detection": 1.20,
                "path_2_to_1": 1.50,
                "path_1_to_2": 1.60,
                "failed_probe_times_after_injection_seconds": [],
            }
        ],
        "aggregate": {
            "traffic": {
                "total_probes": 40,
                "passed": 40,
                "failed": 0,
                "success_rate_percent": 100.0,
            }
        },
    }

    result = correlate_evpn_failure(evidence)

    assert result["neighbor_failure_detected"] is True
    assert result["path_reduction_detected"] is True
    assert result["path_restoration_detected"] is True

    assert result["traffic_impact"] == "no_sampled_loss"
    assert result["failed_probes"] == 0
    assert result["traffic_success_rate_percent"] == 100.0
    assert result["packet_impact_correlation"] == []

    assert (
        "No packet loss was observed by the traffic sampler."
        in result["conclusion"]
    )

