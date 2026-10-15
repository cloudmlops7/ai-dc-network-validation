from unittest.mock import patch

from failure_injection.scenarios import run_interface_failure_scenario


def snapshot(name):
    return {
        "container": "clab-bgpline-r1",
        "state": name,
    }


@patch("failure_injection.scenarios.time.sleep")
@patch("failure_injection.scenarios.wait_for_route")
@patch("failure_injection.scenarios.collect_snapshot")
@patch("failure_injection.scenarios.InterfaceFailure")
def test_interface_failure_scenario(
    mock_failure,
    mock_snapshot,
    mock_wait,
    mock_sleep,
):
    mock_snapshot.side_effect = [
        snapshot("before"),
        snapshot("during"),
        snapshot("after"),
    ]

    mock_wait.side_effect = [
        {
            "recovered": True,
            "elapsed_seconds": 0.2,
            "route": {
                "stdout": "via 10.0.12.2 dev eth1",
            },
        },
        {
            "recovered": True,
            "elapsed_seconds": 1.3,
            "route": {
                "stdout": "via 10.0.13.2 dev eth2",
            },
        },
    ]

    result = run_interface_failure_scenario(
        container="clab-bgpline-r1",
        interface="eth2",
        destination="3.3.3.3",
        backup_next_hop="10.0.12.2",
        preferred_next_hop="10.0.13.2",
    )

    assert result["scenario"] == "interface_failure"

    assert result["before"]["state"] == "before"
    assert result["during"]["state"] == "during"
    assert result["after"]["state"] == "after"

    assert result["backup_recovery"]["recovered"] is True
    assert result["preferred_recovery"]["recovered"] is True

    mock_failure.assert_called_once_with(
        "clab-bgpline-r1",
        "eth2",
    )

    assert mock_wait.call_count == 2
    assert mock_snapshot.call_count == 3
