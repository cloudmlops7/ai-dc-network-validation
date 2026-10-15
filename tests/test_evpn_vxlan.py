import subprocess


LAB_PREFIX = "clab-evpnvxlan"


def docker_exec(node, command, *args):
    result = subprocess.run(
        ["docker", "exec", f"{LAB_PREFIX}-{node}",
         command, *args],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def vtysh(node, command):
    return docker_exec(node, "vtysh", "-c", command)


def test_evpn_neighbors_established():
    output = vtysh("leaf1", "show bgp l2vpn evpn summary")

    assert "10.0.11.2" in output
    assert "10.0.12.2" in output

    assert "Active" not in output
    assert "Idle" not in output
    assert "NoNeg" not in output


def test_vni_and_remote_vtep():
    output = vtysh("leaf1", "show evpn vni")

    assert "10100" in output
    assert "vxlan10100" in output
    assert "br100" in output

    # Leaf1 should discover Leaf2 as a remote VTEP.
    assert "22.22.22.22" in vtysh(
        "leaf1", "show bgp l2vpn evpn"
    )


def test_type2_mac_route_present():
    # Generate traffic so host MAC learning is deterministic.
    docker_exec(
        "host1",
        "ping", "-c", "2", "-W", "2",
        "192.168.10.12",
    )

    host1_mac = docker_exec(
        "host1",
        "cat", "/sys/class/net/eth1/address",
    ).strip()

    output = vtysh("leaf2", "show bgp l2vpn evpn")

    assert "[2]:" in output
    assert host1_mac in output
    assert "11.11.11.11" in output


def test_remote_mac_programmed_in_fdb():
    host1_mac = docker_exec(
        "host1",
        "cat", "/sys/class/net/eth1/address",
    ).strip()

    output = docker_exec(
        "leaf2",
        "bridge", "fdb", "show",
        "dev", "vxlan10100",
    )

    assert host1_mac in output
    assert "dst 11.11.11.11" in output
    assert "extern_learn" in output


def test_overlay_connectivity():
    result = subprocess.run(
        [
            "docker", "exec",
            f"{LAB_PREFIX}-host1",
            "ping", "-c", "5", "-W", "2",
            "192.168.10.12",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "0% packet loss" in result.stdout

def wait_for_condition(check, timeout=20, interval=1):
    import time

    deadline = time.time() + timeout

    while time.time() < deadline:
        if check():
            return
        time.sleep(interval)

    raise AssertionError("Condition did not become true within timeout")


def test_evpn_single_uplink_failure_and_recovery():
    # Confirm baseline tenant connectivity.
    docker_exec(
        "host1",
        "ping", "-c", "3", "-W", "2",
        "192.168.10.12",
    )

    # Confirm baseline EVPN multipath.
    baseline = vtysh("leaf1", "show bgp l2vpn evpn")

    assert "[3]:[0]:[32]:[22.22.22.22]" in baseline
    assert "*=" in baseline

    try:
        # Inject Leaf1 -> Spine1 failure.
        docker_exec(
            "leaf1",
            "ip", "link", "set", "eth1", "down",
        )

        # Wait until the failed EVPN neighbor becomes Active.
        wait_for_condition(
            lambda: "Active" in vtysh(
                "leaf1",
                "show bgp l2vpn evpn summary",
            )
        )

        # Remote VTEP route must remain through Spine2,
        # but EVPN multipath should collapse to one path.
        evpn = vtysh("leaf1", "show bgp l2vpn evpn")

        assert "[3]:[0]:[32]:[22.22.22.22]" in evpn
        assert "22.22.22.22" in evpn
        assert "*=" not in evpn

        # Tenant forwarding must survive the single-uplink failure.
        docker_exec(
            "host1",
            "ping", "-c", "5", "-W", "2",
            "192.168.10.12",
        )

    finally:
        # Always restore the failed link.
        docker_exec(
            "leaf1",
            "ip", "link", "set", "eth1", "up",
        )

    # Wait for both EVPN peers to recover.
    wait_for_condition(
        lambda: (
            "Active" not in vtysh(
                "leaf1",
                "show bgp l2vpn evpn summary",
            )
            and "Idle" not in vtysh(
                "leaf1",
                "show bgp l2vpn evpn summary",
            )
        )
    )

    # Wait until EVPN multipath is restored.
    wait_for_condition(
        lambda: "*=" in vtysh(
            "leaf1",
            "show bgp l2vpn evpn",
        )
    )

    # Final forwarding validation after recovery.
    docker_exec(
        "host1",
        "ping", "-c", "3", "-W", "2",
        "192.168.10.12",
    )
