from unittest.mock import patch

import pytest

from failure_injection.injector import InterfaceFailure, set_interface


@patch("failure_injection.injector.subprocess.run")
def test_set_interface_down(mock_run):
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = ""
    mock_run.return_value.stderr = ""

    set_interface("clab-bgpline-r1", "eth2", "down")

    mock_run.assert_called_once_with(
        [
            "docker",
            "exec",
            "clab-bgpline-r1",
            "ip",
            "link",
            "set",
            "eth2",
            "down",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )


@patch("failure_injection.injector.set_interface")
def test_interface_restored_after_success(mock_set):
    with InterfaceFailure("clab-bgpline-r1", "eth2"):
        pass

    assert mock_set.call_count == 2
    assert mock_set.call_args_list[0].args == (
        "clab-bgpline-r1",
        "eth2",
        "down",
    )
    assert mock_set.call_args_list[1].args == (
        "clab-bgpline-r1",
        "eth2",
        "up",
    )


@patch("failure_injection.injector.set_interface")
def test_interface_restored_after_exception(mock_set):
    with pytest.raises(RuntimeError):
        with InterfaceFailure("clab-bgpline-r1", "eth2"):
            raise RuntimeError("simulated test failure")

    assert mock_set.call_count == 2
    assert mock_set.call_args_list[0].args[-1] == "down"
    assert mock_set.call_args_list[1].args[-1] == "up"


def test_invalid_interface_state():
    with pytest.raises(ValueError):
        set_interface("clab-bgpline-r1", "eth2", "invalid")
