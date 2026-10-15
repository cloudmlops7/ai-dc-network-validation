import json
from pathlib import Path


def load_benchmark_evidence(file_path):
    """Load EVPN resiliency benchmark evidence from JSON."""

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Benchmark evidence not found: {path}"
        )

    with path.open("r") as f:
        evidence = json.load(f)

    return evidence

def correlate_packet_impact(trials):
    """Correlate failed traffic samples with EVPN failure detection."""

    correlations = []

    for trial in trials:
        detection_time = trial["failure_detection"]

        failed_times = trial.get(
            "failed_probe_times_after_injection_seconds",
            [],
        )

        for failed_time in failed_times:
            delta = failed_time - detection_time

            correlations.append(
                {
                    "trial": trial["trial"],
                    "failed_probe_after_injection_seconds":
                        failed_time,
                    "neighbor_detection_seconds":
                        detection_time,
                    "delta_from_neighbor_detection_seconds":
                        delta,
                }
            )

    return correlations

def correlate_evpn_failure(evidence):
    """Correlate EVPN benchmark evidence with the injected failure."""

    trials = evidence["trials"]
    traffic = evidence["aggregate"]["traffic"]
    packet_impact_correlation = correlate_packet_impact(
        trials
    )
    trials = evidence["trials"]
    traffic = evidence["aggregate"]["traffic"]

    neighbor_detected = all(
        trial["failure_detection"] is not None
        for trial in trials
    )

    path_reduced = all(
        trial["path_2_to_1"] is not None
        for trial in trials
    )

    path_restored = all(
        trial["path_1_to_2"] is not None
        for trial in trials
    )

    failed_probes = traffic["failed"]

    if failed_probes > 0:
        traffic_impact = "isolated_sampled_loss"
    else:
        traffic_impact = "no_sampled_loss"

    conclusion = (
        "Single leaf-spine uplink failure was detected. "
        "The EVPN fabric reduced from two paths to one while "
        "retaining the redundant path. "
    )

    if failed_probes > 0:
        conclusion += (
            "Isolated sampled packet loss was observed around "
            "the failure transition. "
        )
    else:
        conclusion += (
            "No packet loss was observed by the traffic sampler. "
        )

    if path_restored:
        conclusion += (
            "Two-path EVPN operation was restored after "
            "the failed uplink recovered."
        )

    return {
        "failure_stimulus":
            evidence["environment"]["failure_injection"],
        "neighbor_failure_detected": neighbor_detected,
        "path_reduction_detected": path_reduced,
        "path_restoration_detected": path_restored,
        "traffic_impact": traffic_impact,
        "failed_probes": failed_probes,
        "traffic_success_rate_percent":
            traffic["success_rate_percent"],
        "packet_impact_correlation":
            packet_impact_correlation,
        "conclusion": conclusion,
    }
