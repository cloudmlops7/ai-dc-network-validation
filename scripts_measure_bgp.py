import csv
import subprocess
import time
from pathlib import Path

R1 = "clab-bgpline-r1"
LINK = "eth2"
DEST = "3.3.3.3/32"
PING_DEST = "3.3.3.3"


def run(args):
    return subprocess.run(
        args, capture_output=True, text=True, timeout=5
    )


def route_output():
    result = run([
        "docker", "exec", R1, "vtysh", "-c",
        f"show ip route {DEST}"
    ])
    return result.stdout + result.stderr


def wait_for_route(next_hop, timeout=30):
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if next_hop in route_output():
            return time.monotonic() - start
        time.sleep(0.1)
    raise TimeoutError(f"Route via {next_hop} not seen within {timeout}s")


def wait_for_ping(timeout=30):
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        result = run([
            "docker", "exec", R1, "ping",
            "-c", "1", "-W", "1", PING_DEST
        ])
        if result.returncode == 0:
            return time.monotonic() - start
        time.sleep(0.1)
    raise TimeoutError(f"Ping to {PING_DEST} did not recover")


def set_link(state):
    result = run([
        "docker", "exec", R1, "ip", "link",
        "set", LINK, state
    ])
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)


results = []

try:
    print("Checking baseline route and connectivity...")
    print(route_output())
    if run(["docker", "exec", R1, "ping", "-c", "1", "-W", "1",
            PING_DEST]).returncode != 0:
        raise RuntimeError("Baseline ping failed; fix the lab first.")

    print("\nTaking down R1 eth2...")
    start = time.monotonic()
    set_link("down")
    backup_route_s = wait_for_route("10.0.12.2")
    backup_ping_s = wait_for_ping()

    print(f"Backup route observed: {backup_route_s:.3f} seconds")
    print(f"Ping success observed: {backup_ping_s:.3f} seconds")
    results.append(["failure", backup_route_s, backup_ping_s])

finally:
    print("\nRestoring R1 eth2...")
    set_link("up")
    preferred_route_s = wait_for_route("10.0.13.2")
    preferred_ping_s = wait_for_ping()
    print(f"Preferred route observed: {preferred_route_s:.3f} seconds")
    print(f"Ping success observed: {preferred_ping_s:.3f} seconds")
    results.append(["restoration", preferred_route_s, preferred_ping_s])

    Path("results").mkdir(exist_ok=True)
    with open("results/bgp_convergence.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "event", "route_observation_seconds",
            "ping_success_observation_seconds"
        ])
        writer.writerows(results)

    print("\nSaved results/bgp_convergence.csv")
