import csv
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

import bgp_timing as timing

R1 = "clab-bgpline-r1"
DEST = "3.3.3.3"

records = []
lock = threading.Lock()
stop_monitor = threading.Event()


def probe_loop():
    while not stop_monitor.is_set():
        started = time.monotonic()
        try:
            result = subprocess.run(
                [
                    "docker", "exec", R1,
                    "ping", "-n", "-c", "1", "-W", "1", DEST,
                ],
                capture_output=True,
                text=True,
                timeout=2,
            )
            ended = time.monotonic()
            output = (result.stdout + result.stderr).strip()
            success = result.returncode == 0
            error = ""
        except subprocess.TimeoutExpired as exc:
            ended = time.monotonic()
            output = str(exc)
            success = False
            error = "probe_timeout"
        except Exception as exc:
            ended = time.monotonic()
            output = repr(exc)
            success = False
            error = "probe_exception"

        with lock:
            records.append({
                "start": started,
                "end": ended,
                "success": success,
                "output": output,
                "error": error,
            })

        # Short pause between probes; failed probes do not stop the loop.
        stop_monitor.wait(0.05)


def phase_at(timestamp, down_at, up_at):
    if timestamp < down_at:
        return "baseline"
    if timestamp < up_at:
        return "failover"
    return "restoration"


def main():
    if "10.0.13.2" not in timing.next_hop():
        raise RuntimeError("Preferred route missing before benchmark")

    monitor = threading.Thread(target=probe_loop, daemon=True)
    events = {}
    monitor.start()

    try:
        # Let the monitor collect baseline samples.
        time.sleep(1)

        events["link_down"] = time.monotonic()
        timing.set_link("down")
        failover_s = timing.wait_route(
            "10.0.12.2", timeout=20,
            started_at=events["link_down"],
        )
        print(f"Backup route observed in {failover_s:.3f}s")
        time.sleep(2)

        events["link_up"] = time.monotonic()
        timing.set_link("up")
        restore_s = timing.wait_route(
            "10.0.13.2", timeout=20,
            started_at=events["link_up"],
        )
        print(f"Preferred route observed in {restore_s:.3f}s")
        time.sleep(2)

    finally:
        # Restore the link before stopping the probe monitor.
        try:
            timing.set_link("up")
        except Exception as exc:
            print(f"WARNING: could not restore eth2: {exc}")

        stop_monitor.set()
        monitor.join(timeout=4)

    if "link_down" not in events or "link_up" not in events:
        raise RuntimeError("Benchmark did not complete both link transitions")

    with lock:
        captured = list(records)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("results")
    output_dir.mkdir(exist_ok=True)

    detail_path = output_dir / f"bgp_probe_detail_{stamp}.csv"
    summary_path = output_dir / f"bgp_probe_summary_{stamp}.csv"

    if not captured:
        raise RuntimeError("No probe results were captured")

    origin = captured[0]["start"]
    with detail_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "elapsed_start_s", "elapsed_end_s", "phase",
            "success", "duration_s", "error", "output",
        ])
        for item in captured:
            phase = phase_at(
                item["start"], events["link_down"], events["link_up"]
            )
            writer.writerow([
                round(item["start"] - origin, 6),
                round(item["end"] - origin, 6),
                phase,
                item["success"],
                round(item["end"] - item["start"], 6),
                item["error"],
                item["output"].replace("\n", " | "),
            ])

    summary = []
    for name in ("baseline", "failover", "restoration"):
        samples = [
            r for r in captured
            if phase_at(
                r["start"], events["link_down"], events["link_up"]
            ) == name
        ]
        successes = [r for r in samples if r["success"]]
        failures = len(samples) - len(successes)

        # Longest gap between successful probe completions in this phase.
        success_ends = [r["end"] for r in successes]
        intervals = [
            success_ends[i] - success_ends[i - 1]
            for i in range(1, len(success_ends))
        ]

        summary.append([
            name,
            len(samples),
            len(successes),
            failures,
            round(100 * failures / len(samples), 2) if samples else "",
            round(max(intervals), 3) if intervals else "",
        ])

    with summary_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "phase", "probes", "successful_probes", "failed_probes",
            "failed_probe_percent", "largest_gap_between_successes_s",
        ])
        writer.writerows(summary)

    print(f"\nDetailed probes: {detail_path}")
    print(f"Phase summary: {summary_path}")
    print("\nPhase summary:")
    for row in summary:
        print(
            f"{row[0]:12} probes={row[1]:3} "
            f"success={row[2]:3} failed={row[3]:3} "
            f"failed%={str(row[4]):>6} "
            f"largest_success_gap={str(row[5]):>6}s"
        )


if __name__ == "__main__":
    main()
