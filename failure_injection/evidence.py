"""Evidence collection helpers for network failure scenarios."""

import subprocess
import time

def docker_command(container, command):
    """Execute a command inside a container and return its output."""
    result = subprocess.run(
        ["docker", "exec", container, *command],
        capture_output=True,
        text=True,
        timeout=10,
    )

    return {
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def collect_interface_state(container, interface):
    """Collect interface operational state."""
    return docker_command(
        container,
        ["ip", "-br", "link", "show", interface],
    )


def collect_bgp_summary(container):
    """Collect BGP IPv4 unicast neighbor state."""
    return docker_command(
        container,
        ["vtysh", "-c", "show bgp ipv4 unicast summary"],
    )


def collect_route(container, destination):
    """Collect the route selected for a destination."""
    return docker_command(
        container,
        ["ip", "route", "get", destination],
    )


def collect_ping(container, destination, count=3):
    """Collect basic reachability evidence."""
    return docker_command(
        container,
        [
            "ping",
            "-n",
            "-c",
            str(count),
            "-W",
            "1",
            destination,
        ],
    )


def collect_snapshot(container, interface, destination):
    """Collect a network evidence snapshot."""
    return {
        "container": container,
        "interface": collect_interface_state(
            container,
            interface,
        ),
        "bgp_summary": collect_bgp_summary(container),
        "route": collect_route(container, destination),
        "ping": collect_ping(container, destination),
    }

def wait_for_route(
    container,
    destination,
    expected_next_hop,
    timeout=10,
    interval=0.1,
):
    """Wait until the expected next hop is installed."""

    started = time.monotonic()

    while time.monotonic() - started < timeout:
        result = collect_route(container, destination)

        if (
            result["returncode"] == 0
            and expected_next_hop in result["stdout"]
        ):
            return {
                "recovered": True,
                "elapsed_seconds": round(
                    time.monotonic() - started,
                    3,
                ),
                "route": result,
            }

        time.sleep(interval)

    return {
        "recovered": False,
        "elapsed_seconds": round(
            time.monotonic() - started,
            3,
        ),
        "route": collect_route(container, destination),
    }
