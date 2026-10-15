"""Reusable network failure-injection scenarios."""

import time

from failure_injection.evidence import (
    collect_snapshot,
    wait_for_route,
)
from failure_injection.injector import InterfaceFailure


def run_interface_failure_scenario(
    container,
    interface,
    destination,
    backup_next_hop,
    preferred_next_hop,
    failure_hold_seconds=1.0,
    convergence_timeout=10,
):
    """Run an interface failure with condition-based path validation."""

    result = {
        "scenario": "interface_failure",
        "target": {
            "container": container,
            "interface": interface,
            "destination": destination,
        },
    }

    # Healthy baseline.
    result["before"] = collect_snapshot(
        container,
        interface,
        destination,
    )

    # Inject interface failure.
    with InterfaceFailure(container, interface):

        result["backup_recovery"] = wait_for_route(
            container,
            destination,
            backup_next_hop,
            timeout=convergence_timeout,
        )

        time.sleep(failure_hold_seconds)

        result["during"] = collect_snapshot(
            container,
            interface,
            destination,
        )

    # Interface has now been restored automatically.
    result["preferred_recovery"] = wait_for_route(
        container,
        destination,
        preferred_next_hop,
        timeout=convergence_timeout,
    )

    result["after"] = collect_snapshot(
        container,
        interface,
        destination,
    )

    return result
