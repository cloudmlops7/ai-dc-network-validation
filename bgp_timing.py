import csv
import subprocess
import time
from datetime import datetime
from pathlib import Path

R1 = "clab-bgpline-r1"
DEST = "3.3.3.3"
ROUTE = "3.3.3.3/32"


def command(args):
    return subprocess.run(
        args, capture_output=True, text=True, timeout=5
    )


def next_hop():
    result = command([
        "docker", "exec", R1, "vtysh", "-c",
        f"show ip route {ROUTE}"
    ])
    if result.returncode != 0:
        return ""
    return result.stdout


def wait_route(expected, timeout=20, started_at=None):
    start = started_at if started_at is not None else time.monotonic()
    while time.monotonic() - start < timeout:
        if expected in next_hop():
            return time.monotonic() - start
        time.sleep(0.1)
    raise TimeoutError(f"Route via {expected} not observed")


def wait_ping(timeout=20, started_at=None):
    start = started_at if started_at is not None else time.monotonic()
    while time.monotonic() - start < timeout:
        result = command([
            "docker", "exec", R1, "ping",
            "-n", "-c", "1", "-W", "1", DEST
        ])
        if result.returncode == 0:
            return time.monotonic() - start
        time.sleep(0.1)
    raise TimeoutError(f"Ping to {DEST} did not recover")


def set_link(state):
    result = command([
        "docker", "exec", R1, "ip", "link",
        "set", "eth2", state
    ])
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)


def save_measurements(rows):
    Path("results").mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path("results") / f"bgp_timing_{stamp}.csv"

    with path.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([
            "event", "route_observation_seconds",
            "ping_observation_seconds"
        ])
        writer.writerows(rows)

    print(f"BGP timing results saved to {path}")
