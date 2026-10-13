import csv
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
TRIALS = 5

def extract(pattern, output):
    match = re.search(pattern, output)
    if not match:
        raise RuntimeError(f"Could not find expected output: {pattern}")
    return match.group(1)

def main():
    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    combined_detail = RESULTS / f"bgp_traffic_trials_detail_{stamp}.csv"
    trial_summary = RESULTS / f"bgp_traffic_trials_summary_{stamp}.csv"
    run_log = RESULTS / f"bgp_traffic_trials_{stamp}.log"

    all_detail = []
    summaries = []

    print(f"Starting {TRIALS} BGP traffic-impact trials")
    print("Allowing the existing benchmark to restore the link after each trial.")

    with run_log.open("w") as log:
        for trial in range(1, TRIALS + 1):
            print(f"\n{'=' * 18} TRIAL {trial}/{TRIALS} {'=' * 18}")
            result = subprocess.run(
                [sys.executable, str(ROOT / "run_bgp_traffic_impact.py")],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=90,
            )

            output = result.stdout + result.stderr
            print(output, end="")
            log.write(f"\n===== TRIAL {trial} =====\n{output}\n")
            log.flush()

            if result.returncode != 0:
                raise RuntimeError(
                    f"Trial {trial} failed with exit code {result.returncode}. "
                    f"Check {run_log} and ensure the lab is healthy."
                )

            failover = float(extract(
                r"Backup route observed in ([0-9.]+)s", output
            ))
            restoration = float(extract(
                r"Preferred route observed in ([0-9.]+)s", output
            ))
            detail_file = ROOT / extract(
                r"Detailed probes: (results/\S+)", output
            )
            phase_file = ROOT / extract(
                r"Phase summary: (results/\S+)", output
            )

            with detail_file.open(newline="") as f:
                for row in csv.DictReader(f):
                    row["trial"] = trial
                    all_detail.append(row)

            with phase_file.open(newline="") as f:
                phases = {row["phase"]: row for row in csv.DictReader(f)}

            summary = {
                "trial": trial,
                "failover_route_convergence_s": failover,
                "preferred_route_restoration_s": restoration,
            }

            for phase in ("baseline", "failover", "restoration"):
                row = phases.get(phase, {})
                summary[f"{phase}_probes"] = row.get("probes", "")
                summary[f"{phase}_successes"] = row.get("successful_probes", "")
                summary[f"{phase}_failures"] = row.get("failed_probes", "")
                summary[f"{phase}_failed_percent"] = row.get(
                    "failed_probe_percent", ""
                )
                summary[f"{phase}_largest_success_gap_s"] = row.get(
                    "largest_gap_between_successes_s", ""
                )

            summaries.append(summary)
            print(
                f"Trial {trial}: failover={failover:.3f}s, "
                f"restoration={restoration:.3f}s"
            )

            if trial < TRIALS:
                time.sleep(2)

    if all_detail:
        detail_fields = ["trial"] + [
            key for key in all_detail[0] if key != "trial"
        ]
        with combined_detail.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=detail_fields)
            writer.writeheader()
            writer.writerows(all_detail)

    summary_fields = list(summaries[0])
    with trial_summary.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows(summaries)

    failovers = [s["failover_route_convergence_s"] for s in summaries]
    restorations = [s["preferred_route_restoration_s"] for s in summaries]

    print("\n========== FIVE-TRIAL AGGREGATE ==========")
    for label, values in (
        ("Backup route convergence", failovers),
        ("Preferred route restoration", restorations),
    ):
        print(
            f"{label}: min={min(values):.3f}s, "
            f"avg={statistics.mean(values):.3f}s, "
            f"max={max(values):.3f}s"
        )

    print(f"\nCombined probe details: {combined_detail}")
    print(f"Per-trial summary:      {trial_summary}")
    print(f"Full run log:           {run_log}")

if __name__ == "__main__":
    main()
