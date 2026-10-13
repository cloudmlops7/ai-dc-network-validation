import csv
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import bgp_timing as timing

TRIALS = 5
results = []


def measure_pair(route, started_at):
    with ThreadPoolExecutor(max_workers=2) as pool:
        route_future = pool.submit(
            timing.wait_route, route, started_at=started_at
        )
        ping_future = pool.submit(
            timing.wait_ping, started_at=started_at
        )
        return route_future.result(), ping_future.result()


try:
    for trial in range(1, TRIALS + 1):
        print(f"\n===== Trial {trial}/{TRIALS} =====")

        if "10.0.13.2" not in timing.next_hop():
            raise RuntimeError("Direct route missing before trial")

        if timing.wait_ping() < 0:
            raise RuntimeError("Baseline ping failed")

        try:
            started = time.monotonic()
            timing.set_link("down")
            route_s, ping_s = measure_pair("10.0.12.2", started)

            results.append([
                trial, "failure", route_s, ping_s
            ])
            print(
                f"Failover: route={route_s:.3f}s, "
                f"ping={ping_s:.3f}s"
            )
        finally:
            # Always attempt to restore the direct link.
            restore_started = time.monotonic()
            timing.set_link("up")

        route_s, ping_s = measure_pair(
            "10.0.13.2", restore_started
        )
        results.append([
            trial, "restoration", route_s, ping_s
        ])
        print(
            f"Restoration: route={route_s:.3f}s, "
            f"ping={ping_s:.3f}s"
        )

finally:
    # Best-effort cleanup if a trial exits unexpectedly.
    try:
        timing.set_link("up")
    except Exception as exc:
        print(f"WARNING: could not restore R1 eth2: {exc}")

if len(results) != TRIALS * 2:
    raise RuntimeError(
        f"Incomplete benchmark: recorded {len(results)} of "
        f"{TRIALS * 2} expected measurements"
    )

out = Path("results")
out.mkdir(exist_ok=True)
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
trial_file = out / f"bgp_trials_{stamp}.csv"
summary_file = out / f"bgp_summary_{stamp}.csv"

with trial_file.open("w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "trial", "event", "route_observation_seconds",
        "ping_observation_seconds"
    ])
    writer.writerows(results)

summary = []
for event in ("failure", "restoration"):
    for metric_index, metric in ((2, "route"), (3, "ping")):
        values = [
            row[metric_index] for row in results
            if row[1] == event
        ]
        summary.append([
            event, metric, min(values),
            statistics.mean(values), max(values)
        ])

with summary_file.open("w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "event", "metric", "minimum_seconds",
        "average_seconds", "maximum_seconds"
    ])
    writer.writerows(summary)

print(f"\nTrial results: {trial_file}")
print(f"Summary:       {summary_file}")
print("\nSummary (seconds):")
for event, metric, minimum, average, maximum in summary:
    print(
        f"{event:12} {metric:6} "
        f"min={minimum:.3f} avg={average:.3f} "
        f"max={maximum:.3f}"
    )
