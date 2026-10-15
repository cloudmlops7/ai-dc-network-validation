"""Run a failure-injection scenario and generate a structured report."""

import json
from datetime import datetime
from pathlib import Path

from failure_injection.correlation import correlate_interface_failure
from failure_injection.scenarios import run_interface_failure_scenario


def main():
    scenario = run_interface_failure_scenario(
        container="clab-bgpline-r1",
        interface="eth2",
        destination="3.3.3.3",
        backup_next_hop="10.0.12.2",
        preferred_next_hop="10.0.13.2",
    )

    correlation = correlate_interface_failure(scenario)

    report = {
        "scenario_evidence": scenario,
        "correlation": correlation,
    }

    output_dir = Path("results")
    output_dir.mkdir(exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    report_path = (
        output_dir
        / f"failure_scenario_{stamp}.json"
    )

    with report_path.open("w") as file:
        json.dump(
            report,
            file,
            indent=2,
        )

    print("\n===== FAILURE SCENARIO RESULT =====")
    print(f"Failure target: {correlation['failure_target']}")
    print(
        "Backup recovered:",
        correlation["backup_path_recovered"],
    )
    print(
        "Traffic during failure:",
        correlation["traffic_available_during_failure"],
    )
    print(
        "Preferred path recovered:",
        correlation["preferred_path_recovered"],
    )
    print(
        "Probable failure domain:",
        correlation["probable_failure_domain"],
    )
    print(
        "Service assessment:",
        correlation["service_assessment"],
    )
    print(
        "Recovery assessment:",
        correlation["recovery_assessment"],
    )

    print(f"\nStructured report: {report_path}")


if __name__ == "__main__":
    main()
