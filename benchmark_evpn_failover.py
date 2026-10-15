import statistics
import subprocess
import threading
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
def continuous_probe(stop_event, probe_results, start_time):
    sequence = 1

    while not stop_event.is_set():
        probe_start = time.monotonic()

        success = probe_host2()

        elapsed = time.monotonic() - start_time

        probe_results.append(
            {
                "seq": sequence,
                "time": elapsed,
                "success": success,
            }
        )

        sequence += 1

        remaining = 0.2 - (
            time.monotonic() - probe_start
        )

        if remaining > 0:
            stop_event.wait(remaining)
def run_measurement(trial_number):

    print("\n" + "=" * 60)
    print(f"EVPN FAILOVER TRIAL {trial_number}")
    print("=" * 60)

    results = []
    control_plane_time = None
    multipath_time = None
    multipath_restore_time = None
    continuous_results = []
    stop_event = threading.Event()
    traffic_thread = None

    try:
        # -------------------------------------------------
        # Start continuous traffic before failure injection
        # -------------------------------------------------
        traffic_start = time.monotonic()

        traffic_thread = threading.Thread(
            target=continuous_probe,
            args=(
                stop_event,
                continuous_results,
                traffic_start,
            ),
        )

        traffic_thread.start()

        print("Continuous traffic started...")

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

        failure_offset = (
            failure_time - traffic_start
        )
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
        # Stop continuous traffic after recovery
        # -------------------------------------------------
        stop_event.set()

        if traffic_thread is not None:
            traffic_thread.join(timeout=3)

        print("Continuous traffic stopped.")

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
    # -------------------------------------------------
    # Continuous traffic summary
    # -------------------------------------------------
    continuous_total = len(continuous_results)

    continuous_failed = sum(
        1
        for probe in continuous_results
        if not probe["success"]
    )

    continuous_passed = (
        continuous_total - continuous_failed
    )

    print("\nContinuous traffic")
    print(
        f"Total probes           : "
        f"{continuous_total}"
    )
    print(
        f"Passed                 : "
        f"{continuous_passed}"
    )
    print(
        f"Failed                 : "
        f"{continuous_failed}"
    )

    print(
        f"Failure injected at    : "
        f"{failure_offset:.3f}s"
    )
    if continuous_failed > 0:
        failed_probes = [
            probe
            for probe in continuous_results
            if not probe["success"]
        ]

        first_failure = failed_probes[0]["time"]
        last_failure = failed_probes[-1]["time"]

        print(
            f"First failed probe     : "
            f"{first_failure:.3f}s"
        )
        print(
            f"Last failed probe      : "
            f"{last_failure:.3f}s"
        )
    else:
        print(
            "Observed packet impact : "
            "no failed probes"
        )

    return {
        "trial": trial_number,
        "failure_detection": control_plane_time,
        "path_2_to_1": multipath_time,
        "path_1_to_2": multipath_restore_time,
        "continuous_total": continuous_total,
        "continuous_passed": continuous_passed,
        "continuous_failed": continuous_failed,
    }

if __name__ == "__main__":
    all_results = []

    for trial in range(1, 6):
        result = run_measurement(trial)
        all_results.append(result)

        if trial < 5:
            print(
                "\nWaiting 5 seconds before next trial..."
            )
            time.sleep(5)

    # -------------------------------------------------
    # Aggregate benchmark results
    # -------------------------------------------------
    failure_times = [
        r["failure_detection"]
        for r in all_results
        if r["failure_detection"] is not None
    ]

    path_down_times = [
        r["path_2_to_1"]
        for r in all_results
        if r["path_2_to_1"] is not None
    ]

    path_restore_times = [
        r["path_1_to_2"]
        for r in all_results
        if r["path_1_to_2"] is not None
    ]

    total_probes = sum(
        r["continuous_total"]
        for r in all_results
    )

    total_passed = sum(
        r["continuous_passed"]
        for r in all_results
    )

    total_failed = sum(
        r["continuous_failed"]
        for r in all_results
    )

    print("\n" + "=" * 60)
    print("EVPN FAILOVER BENCHMARK SUMMARY")
    print("=" * 60)

    print("\nPer-trial results")

    for r in all_results:
        failure = (
            f"{r['failure_detection']:.3f}s"
            if r["failure_detection"] is not None
            else "timeout"
        )

        path_down = (
            f"{r['path_2_to_1']:.3f}s"
            if r["path_2_to_1"] is not None
            else "timeout"
        )

        path_restore = (
            f"{r['path_1_to_2']:.3f}s"
            if r["path_1_to_2"] is not None
            else "timeout"
        )

        print(
            f"Trial {r['trial']}: "
            f"neighbor={failure}, "
            f"2->1={path_down}, "
            f"1->2={path_restore}, "
            f"probes={r['continuous_total']}, "
            f"failed={r['continuous_failed']}"
        )

    print("\nAggregate timing")

    if failure_times:
        print(
            "Neighbor detection : "
            f"min={min(failure_times):.3f}s "
            f"avg={statistics.mean(failure_times):.3f}s "
            f"max={max(failure_times):.3f}s"
        )

    if path_down_times:
        print(
            "EVPN 2 -> 1       : "
            f"min={min(path_down_times):.3f}s "
            f"avg={statistics.mean(path_down_times):.3f}s "
            f"max={max(path_down_times):.3f}s"
        )

    if path_restore_times:
        print(
            "EVPN 1 -> 2       : "
            f"min={min(path_restore_times):.3f}s "
            f"avg={statistics.mean(path_restore_times):.3f}s "
            f"max={max(path_restore_times):.3f}s"
        )

    print("\nAggregate traffic")
    print(f"Total probes : {total_probes}")
    print(f"Passed       : {total_passed}")
    print(f"Failed       : {total_failed}")

    if total_probes > 0:
        success_rate = (
            total_passed / total_probes
        ) * 100

        print(
            f"Success rate : {success_rate:.2f}%"
        )
