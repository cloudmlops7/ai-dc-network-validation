import subprocess
import time

LAB_PREFIX = "clab-evpnvxlan"


def docker_exec(node, *command):
    result = subprocess.run(
        ["docker", "exec", f"{LAB_PREFIX}-{node}", *command],
        capture_output=True,
        text=True,
        timeout=15,
    )
    return result
def probe_host2():
    result = docker_exec(
        "host1",
        "ping",
        "-c", "1",
        "-W", "1",
        "192.168.10.12",
    )

    return result.returncode == 0

def evpn_spine1_is_down():
    result = docker_exec(
        "leaf1",
        "vtysh",
        "-c",
        "show bgp l2vpn evpn summary",
    )

    return "10.0.11.2" in result.stdout and "Active" in result.stdout

def evpn_multipath_removed():
    result = docker_exec(
        "leaf1",
        "vtysh",
        "-c",
        "show bgp l2vpn evpn",
    )

    output = result.stdout

    return (
        "[3]:[0]:[32]:[22.22.22.22]" in output
        and "*=" not in output
    )

def evpn_multipath_restored():
    result = docker_exec(
        "leaf1",
        "vtysh",
        "-c",
        "show bgp l2vpn evpn",
    )

    output = result.stdout

    return (
        "[3]:[0]:[32]:[22.22.22.22]" in output
        and "*=" in output
    )

def run_measurement():
    results = []
    control_plane_time = None
    multipath_time = None
    multipath_restore_time = None

    try:
        # -------------------------------------------------
        # 1. Baseline traffic
        # -------------------------------------------------
        print("Baseline probes...")

        for i in range(5):
            success = probe_host2()
            results.append(("baseline", i + 1, success))

            print(
                f"baseline {i + 1}: "
                f"{'PASS' if success else 'FAIL'}"
            )

            time.sleep(0.2)

        # -------------------------------------------------
        # 2. Inject Leaf1 -> Spine1 failure
        # -------------------------------------------------
        print("\nInjecting Leaf1 eth1 failure...")

        failure_time = time.monotonic()

        docker_exec(
            "leaf1",
            "ip", "link", "set", "eth1", "down",
        )

        # -------------------------------------------------
        # 3. Measure EVPN neighbor failure detection
        # -------------------------------------------------
        control_plane_start = time.monotonic()

        while True:
            if evpn_spine1_is_down():
                control_plane_time = (
                    time.monotonic() - control_plane_start
                )
                break

            if time.monotonic() - control_plane_start > 10:
                control_plane_time = None
                break

            time.sleep(0.05)

        if control_plane_time is not None:
            print(
                f"EVPN Spine1 failure detected: "
                f"{control_plane_time:.3f}s"
            )
        else:
            print(
                "EVPN Spine1 failure detection timed out"
            )

        # -------------------------------------------------
        # 4. Measure EVPN multipath reduction: 2 -> 1
        # -------------------------------------------------
        while True:
            if evpn_multipath_removed():
                multipath_time = (
                    time.monotonic() - failure_time
                )
                break

            if time.monotonic() - failure_time > 10:
                multipath_time = None
                break

            time.sleep(0.05)

        if multipath_time is not None:
            print(
                f"EVPN multipath reduced 2 -> 1: "
                f"{multipath_time:.3f}s after injection"
            )
        else:
            print(
                "EVPN multipath reduction timed out"
            )

        # -------------------------------------------------
        # 5. Traffic while failure is active
        # -------------------------------------------------
        print("\nFailure-window probes...")

        for i in range(10):
            success = probe_host2()

            elapsed = (
                time.monotonic() - failure_time
            )

            results.append(
                ("failure", i + 1, success)
            )

            print(
                f"failure {i + 1}: "
                f"{'PASS' if success else 'FAIL'} "
                f"({elapsed:.3f}s after injection)"
            )

            time.sleep(0.2)

    finally:
        # -------------------------------------------------
        # 6. Always restore Leaf1 -> Spine1 link
        # -------------------------------------------------
        print("\nRestoring Leaf1 eth1...")

        recovery_start = time.monotonic()

        docker_exec(
            "leaf1",
            "ip", "link", "set", "eth1", "up",
        )

        # -------------------------------------------------
        # Measure EVPN multipath restoration: 1 -> 2
        # -------------------------------------------------
        while True:
            if evpn_multipath_restored():
                multipath_restore_time = (
                    time.monotonic() - recovery_start
                )
                break

            if time.monotonic() - recovery_start > 15:
                multipath_restore_time = None
                break

            time.sleep(0.1)

        if multipath_restore_time is not None:
            print(
                f"EVPN multipath restored 1 -> 2: "
                f"{multipath_restore_time:.3f}s"
            )
        else:
            print(
                "EVPN multipath restoration timed out"
            )

    # -------------------------------------------------
    # 7. Recovery traffic
    # -------------------------------------------------
    print("\nRecovery probes...")

    for i in range(5):
        success = probe_host2()

        results.append(
            ("recovery", i + 1, success)
        )

        print(
            f"recovery {i + 1}: "
            f"{'PASS' if success else 'FAIL'}"
        )

        time.sleep(0.2)

    # -------------------------------------------------
    # 8. Summary
    # -------------------------------------------------
    failed = sum(
        1
        for _, _, success in results
        if not success
    )

    passed = len(results) - failed

    print("\nSummary")
    print(f"Total probes : {len(results)}")
    print(f"Passed       : {passed}")
    print(f"Failed       : {failed}")

    if control_plane_time is not None:
        print(
            f"EVPN failure detection : "
            f"{control_plane_time:.3f}s"
        )
    else:
        print(
            "EVPN failure detection : timeout"
        )

    if multipath_time is not None:
        print(
            f"EVPN 2 -> 1 path       : "
            f"{multipath_time:.3f}s"
        )
    else:
        print(
            "EVPN 2 -> 1 path       : timeout"
        )
    if multipath_restore_time is not None:
        print(
            f"EVPN 1 -> 2 path       : "
            f"{multipath_restore_time:.3f}s"
        )
    else:
        print(
            "EVPN 1 -> 2 path       : timeout"
        )


if __name__ == "__main__":
    run_measurement()
