import subprocess
import time
from pathlib import Path

import pytest


LAB = "clab-ospftri"
DIAGNOSTICS = Path("results/ospf-diagnostics.log")


def run_command(*args):
    """Run a command and save its output for troubleshooting."""
    result = subprocess.run(
        args, capture_output=True, text=True, timeout=15
    )
    record = (
        f"\n$ {' '.join(args)}\n"
        f"Exit code: {result.returncode}\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}\n"
    )
    with DIAGNOSTICS.open("a", encoding="utf-8") as log:
        log.write(record)
    return result


def router_command(router, command):
    return run_command(
        "docker", "exec", f"{LAB}-{router}",
        "vtysh", "-c", command
    )


def wait_for_route(router, expected_next_hop, timeout=20):
    """Poll until the expected OSPF next hop is installed."""
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        result = router_command(
            router, "show ip route 3.3.3.3/32"
        )
        if (
            result.returncode == 0
            and 'Known via "ospf"' in result.stdout
            and expected_next_hop in result.stdout
        ):
            return result.stdout
        time.sleep(1)

    pytest.fail(
        f"{router}: route to 3.3.3.3/32 via "
        f"{expected_next_hop} not installed within {timeout}s"
    )


def test_ospf_neighbors_are_full():
    for router in ("r1", "r2", "r3"):
        result = router_command(router, "show ip ospf neighbor")
        assert result.returncode == 0, result.stderr

        full_count = sum(
            "Full/" in line for line in result.stdout.splitlines()
        )
        assert full_count == 2, (
            f"{router}: expected 2 Full neighbors, got {full_count}\n"
            f"{result.stdout}"
        )


def test_r1_has_ospf_route_to_r3_loopback():
    route = router_command("r1", "show ip route 3.3.3.3/32")
    assert route.returncode == 0, route.stderr
    assert 'Known via "ospf"' in route.stdout
    assert "10.0.13.2" in route.stdout


def test_r1_can_ping_r3_loopback():
    result = run_command(
        "docker", "exec", f"{LAB}-r1",
        "ping", "-c", "3", "-W", "2", "3.3.3.3"
    )
    assert result.returncode == 0, (
        f"Ping failed\n{result.stdout}\n{result.stderr}"
    )
    assert "0% packet loss" in result.stdout


def test_link_failure_reconverges_via_r2():
    # R1 eth2 connects directly to R3. Disable it to force
    # traffic over R1 -> R2 -> R3.
    down = run_command(
        "docker", "exec", f"{LAB}-r1",
        "ip", "link", "set", "eth2", "down"
    )
    assert down.returncode == 0, down.stderr

    try:
        route = wait_for_route("r1", "10.0.12.2", timeout=25)
        assert "eth1" in route

        ping = run_command(
            "docker", "exec", f"{LAB}-r1",
            "ping", "-c", "3", "-W", "2", "3.3.3.3"
        )
        assert ping.returncode == 0, (
            f"Ping failed after failover\n"
            f"{ping.stdout}\n{ping.stderr}"
        )
        assert "0% packet loss" in ping.stdout

    finally:
        # Restore the topology even if an assertion fails.
        run_command(
            "docker", "exec", f"{LAB}-r1",
            "ip", "link", "set", "eth2", "up"
        )

    # Verify recovery to the original direct route.
    wait_for_route("r1", "10.0.13.2", timeout=30)


def test_unassigned_loopback_is_unreachable():
    result = run_command(
        "docker", "exec", f"{LAB}-r1",
        "ping", "-c", "2", "-W", "2", "9.9.9.9"
    )
    assert result.returncode != 0, (
        "Unexpectedly reached unassigned destination 9.9.9.9"
    )
