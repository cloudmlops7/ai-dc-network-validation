import time

import bgp_timing as timing


def test_bgp_failover_convergence_timing():
    measurements = []
    link_was_taken_down = False

    try:
        # Confirm the baseline route and connectivity.
        assert "10.0.13.2" in timing.next_hop(), (
            "Expected direct R1-R3 route before failure"
        )
        assert timing.wait_ping() >= 0, "Baseline ping failed"

        # Start measuring before issuing the link-down command.
        failure_start = time.monotonic()
        timing.set_link("down")
        link_was_taken_down = True

        route_time = timing.wait_route("10.0.12.2", started_at=failure_start)
        ping_time = timing.wait_ping(started_at=failure_start)

        measurements.append(["failure", route_time, ping_time])

        assert "10.0.12.2" in timing.next_hop()
        print(
            f"\nBGP failover: route={route_time:.3f}s, "
            f"ping={ping_time:.3f}s"
        )

    finally:
        # Restore the link before checking the preferred path.
        restoration_start = time.monotonic()
        timing.set_link("up")

    # Confirm preferred route and connectivity return.
    restore_route_time = timing.wait_route(
        "10.0.13.2", started_at=restoration_start
    )
    restore_ping_time = timing.wait_ping(started_at=restoration_start)
    measurements.append([
        "restoration", restore_route_time, restore_ping_time
    ])

    timing.save_measurements(measurements)

    print(
        f"BGP restoration: route={restore_route_time:.3f}s, "
        f"ping={restore_ping_time:.3f}s"
    )
