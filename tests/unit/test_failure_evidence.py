from unittest.mock import patch

from failure_injection.evidence import wait_for_route


@patch("failure_injection.evidence.collect_route")
def test_wait_for_route_success(mock_route):
    mock_route.return_value = {
        "returncode": 0,
        "stdout": "3.3.3.3 via 10.0.13.2 dev eth2",
        "stderr": "",
    }

    result = wait_for_route(
        "clab-bgpline-r1",
        "3.3.3.3",
        "10.0.13.2",
        timeout=1,
    )

    assert result["recovered"] is True
    assert "10.0.13.2" in result["route"]["stdout"]


@patch("failure_injection.evidence.time.sleep")
@patch("failure_injection.evidence.time.monotonic")
@patch("failure_injection.evidence.collect_route")
def test_wait_for_route_timeout(mock_route, mock_monotonic, mock_sleep):
    mock_route.return_value = {
        "returncode": 0,
        "stdout": "3.3.3.3 via 10.0.12.2 dev eth1",
        "stderr": "",
    }

    mock_monotonic.side_effect = [
        0.0,
        0.1,
        0.5,
        1.1,
        1.2,
    ]

    result = wait_for_route(
        "clab-bgpline-r1",
        "3.3.3.3",
        "10.0.13.2",
        timeout=1,
    )

    assert result["recovered"] is False
    assert "10.0.12.2" in result["route"]["stdout"]
