# BGP Failover and Traffic-Impact Benchmark

**Date:** 2026-10-13
**Environment:** Ubuntu WSL2, Containerlab, Docker Engine, FRRouting
**Trials:** 5
**Source summary:** `results/bgp_traffic_trials_summary_20261013_101244.csv`

## 1. Objective

Evaluate BGP route convergence and preferred-route restoration when the direct R1–R3 link is taken down and subsequently restored. Continuous, discrete ICMP probes are used to observe reachability during each phase.

This is a software-lab proof of concept, not a hardware-switch performance benchmark.

## 2. Topology and test behavior

Three FRRouting routers use separate autonomous systems:

- R1: AS 65001
- R2: AS 65002
- R3: AS 65003

R1 has a direct link to R3 and an alternate path through R2. R3 advertises its loopback prefix, `3.3.3.3/32`.

Each trial observes these phases:

1. **Baseline:** confirm connectivity before the failure.
2. **Failover:** take R1's direct-link interface down and wait for R1's route to use next hop `10.0.12.2`.
3. **Restoration:** bring the interface back up and wait for the preferred next hop `10.0.13.2` to return.

The route timer starts immediately before the interface-state command. It does not measure from an independently captured physical or kernel link-state event.

## 3. Route convergence results

| Trial | Failover convergence | Preferred-route restoration |
|---:|---:|---:|
| 1 | 0.336 s | 1.640 s |
| 2 | 0.303 s | 1.566 s |
| 3 | 0.307 s | 1.609 s |
| 4 | 0.338 s | 1.622 s |
| 5 | 0.339 s | 1.651 s |
| **Minimum** | **0.303 s** | **1.566 s** |
| **Average** | **0.325 s** | **1.618 s** |
| **Maximum** | **0.339 s** | **1.651 s** |

### Interpretation

- The alternate route was observed in approximately 0.30–0.34 seconds in these trials.
- The preferred direct route returned in approximately 1.57–1.65 seconds.
- These are observed route-table convergence times under this test method. They should not be treated as universal BGP convergence guarantees.

## 4. Continuous-probe results

| Trial | Baseline | Failover probes | Failed failover probes | Restoration |
|---:|---:|---:|---:|---:|
| 1 | 5/5 success | 10/11 success | 1 | 17/17 success |
| 2 | 5/5 success | 10/10 success | 0 | 19/19 success |
| 3 | 5/5 success | 10/10 success | 0 | 19/19 success |
| 4 | 5/5 success | 10/10 success | 0 | 18/18 success |
| 5 | 5/5 success | 10/11 success | 1 | 18/18 success |
| **Total** | **25/25** | **50/52** | **2** | **91/91** |

Across the failover phase, 2 of 52 probes failed, approximately 3.85% of sampled probes. Two individual trials each had one failed probe, equivalent to 9.09% of probes in that trial.

Both failures reported:

`ping: sendto: Network unreachable`

This error is consistent with the local networking stack temporarily having no usable route during the transition. It differs from a probe that is sent successfully but receives no ICMP reply.

## 5. What the probe data does—and does not—show

The probe loop sends individual ping commands rather than a high-rate, continuous packet stream. A probe can take around 0.12–0.20 seconds, and the loop waits briefly between probes.

For the two failed probes:

- Trial 1: failed probe duration was approximately 0.131 seconds.
- Trial 5: failed probe duration was approximately 0.123 seconds.
- The gaps from the previous successful probe completion to the next successful probe start were approximately 231 ms and 225 ms, respectively.

These values describe the observation window and failed command duration; they are **not exact outage durations**. Probes that cross phase boundaries and the finite sampling interval also limit precision.

The other three trials had no failed probes in the sampled failover phase. This does not prove that every packet would have been delivered without loss.

## 6. Limitations

- The environment is virtualized WSL2/Containerlab/FRR, not production switching hardware.
- The interface command's start time is used as the measurement origin; actual interface-state transition timing is not independently captured.
- Route-table polling introduces sampling and scheduling effects.
- Discrete ICMP probes are not a substitute for high-rate traffic generation or packet capture.
- Probe counts are small, so percentages can change substantially with one additional failure.
- Restoration of the preferred route and restoration of basic reachability are different events. Reachability may return through the alternate route before the direct route becomes preferred.
- Results depend on software versions, host load, topology, timer settings, and test implementation.

## 7. Recommendations for the next iteration

1. Record the exact interface state transition and route-table change timestamps.
2. Capture per-probe start time, end time, exit status, and output.
3. Add a sustained traffic stream or higher-rate probe method and, where possible, packet capture.
4. Run more trials and report sample size alongside averages and ranges.
5. Add explicit assertions for baseline route, failover next hop, recovery next hop, and end-to-end reachability.
6. Preserve each run's raw CSV and log files so results can be independently reviewed.

## 8. Reproducibility

Run the five-trial benchmark from the project root:

```bash
cd ~/projects/ai-dc-validation
source .venv/bin/activate
python run_bgp_traffic_trials.py
```

The script creates new timestamped result files under `results/`. Do not overwrite the original source summary when comparing future runs.

## 9. Conclusion

The five observed trials showed alternate-route convergence averaging 0.325 seconds and preferred-route restoration averaging 1.618 seconds. Two trials recorded a probe error indicating that no usable route was available at probe time.

This provides a useful initial automated validation and measurement workflow. Further timestamp precision, sustained traffic testing, and more trials are needed before drawing stronger conclusions about interruption duration or performance under load.
