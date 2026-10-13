import subprocess
import time


def docker_exec(router, *commands):
    result = subprocess.run(
        ["docker", "exec", f"clab-bgpline-{router}",
         "vtysh", *sum((["-c", cmd] for cmd in commands), [])],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def ping(router, destination):
    result = subprocess.run(
        ["docker", "exec", f"clab-bgpline-{router}",
         "ping", "-c", "3", "-W", "2", destination],
        capture_output=True,
        text=True,
        timeout=15,
    )
    return result.returncode == 0


def wait_for_next_hop(expected, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        output = docker_exec("r1", "show ip route 3.3.3.3/32")
        if expected in output:
            return output
        time.sleep(1)
    raise AssertionError(
        f"Route did not converge to next hop {expected}"
    )


def test_bgp_neighbors_established():
    output = docker_exec("r1", "show bgp ipv4 unicast summary")
    assert "10.0.12.2" in output
    assert "10.0.13.2" in output
    assert "(Policy)" not in output
    assert "Active" not in output


def test_r1_learns_r3_loopback():
    output = docker_exec("r1", "show bgp ipv4 unicast")
    assert "3.3.3.3/32" in output
    assert "65003" in output


def test_baseline_connectivity():
    assert ping("r1", "3.3.3.3"), "R1 cannot reach R3 loopback"


def test_bgp_failover_and_recovery():
    try:
        # Fail the direct R1-R3 link.
        subprocess.run(
            ["docker", "exec", "clab-bgpline-r1",
             "ip", "link", "set", "eth2", "down"],
            check=True,
            timeout=10,
        )

        # Verify backup route and end-to-end reachability.
        wait_for_next_hop("10.0.12.2")
        assert ping("r1", "3.3.3.3"), (
            "Connectivity failed over the R1-R2-R3 path"
        )
    finally:
        # Always restore the direct link, even if an assertion fails.
        subprocess.run(
            ["docker", "exec", "clab-bgpline-r1",
             "ip", "link", "set", "eth2", "up"],
            check=True,
            timeout=10,
        )

    # Verify the direct path returns.
    wait_for_next_hop("10.0.13.2")
    assert ping("r1", "3.3.3.3"), (
        "Connectivity failed after direct-link recovery"
    )
