# AI Data-Center Network Validation and Automated RCA

A hands-on network validation proof of concept using Containerlab, FRRouting (FRR), Linux containers, Python, and pytest.

## Project goals

- Validate IP connectivity and routing behavior through automated tests.
- Exercise OSPF adjacency, route installation, and alternate-path forwarding.
- Validate BGP neighbor establishment, route learning, failover, and recovery.
- Measure route convergence and observe probe behavior during failures.
- Validate a redundant leaf-spine EVPN/VXLAN fabric, including BGP EVPN sessions, VTEPs, VNIs, Type-2/Type-3 routes, remote MAC programming, and tenant forwarding.
- Validate EVPN multipath behavior during single-uplink failure and recovery.
- Validate jumbo-frame operation with a 9000-byte tenant MTU across the VXLAN overlay.
- Measure control-plane transitions and sampled traffic behavior during controlled failures.
- Correlate injected failures with network-state evidence using deterministic, rule-based analysis.
- Build toward AI data-center fabric validation, including RoCEv2/lossless-Ethernet concepts where they can be meaningfully demonstrated without specialized RDMA hardware.

## Environment

- Ubuntu 24.04 on WSL2
- Containerlab
- Docker Engine
- FRRouting containers
- Python virtual environment with pytest and pytest-html

## Repository layout

- `topology/` — Containerlab YAML files and FRR configurations.
- `tests/` — connectivity, OSPF, BGP, EVPN/VXLAN, failure-injection, correlation, MTU, and RCA tests.
- `tests/unit/` — isolated unit tests that do not require a running network lab.
- `failure_injection/` — reusable failure injection, evidence collection, scenario orchestration, and correlation components.
- `results/` — timestamped HTML reports, logs, and benchmark CSV files.
- `docs/` — topology documentation and diagrams.
- `diagnostics/` — evidence-based, rule-driven RCA findings.
- `.github/workflows/` — automated RCA unit tests on GitHub.
- `reports/` — interpreted benchmark reports.
- `bgp_timing.py` — BGP measurement helpers.
- `run_bgp_trials.py` — repeated route-convergence measurements.
- `run_bgp_traffic_impact.py` — continuous-probe failover experiment.
- `run_bgp_traffic_trials.py` — repeated traffic-impact trials.
- `run_failure_scenario.py` — controlled failure-injection and evidence-correlation scenario.
- `measure_evpn_failover.py` — single EVPN failure/recovery timing and continuous-traffic measurement.
- `benchmark_evpn_failover.py` — repeated EVPN resiliency trials with structured JSON evidence.
- `init_evpn_lab.sh` — initializes the EVPN/VXLAN underlay, overlay, and endpoint addressing.
- `run_tests.sh` — regression test runner.

## Run the regression tests

```bash
cd ~/projects/ai-dc-validation
source .venv/bin/activate
./run_tests.sh
```

The runner creates timestamped HTML and console-log files under `results/`.

To run individual suites:

```bash
pytest -v tests/test_basic_connectivity.py
pytest -v tests/test_ospf_validation.py
pytest -v tests/test_bgp_validation.py
pytest -v tests/test_bgp_timing.py
```

Some tests change interface state. Avoid running tests and benchmarks concurrently against the same lab.

## Run BGP benchmarks

Single traffic-impact experiment:

```bash
python run_bgp_traffic_impact.py
```

Five-trial experiment:

```bash
python run_bgp_traffic_trials.py
```

These commands create timestamped CSV files and logs in `results/`. Preserve existing result files to keep comparisons reproducible.

## Recorded BGP benchmark

Five trials were recorded on 2026-10-13.

| Metric | Minimum | Average | Maximum |
|---|---:|---:|---:|
| Failover route convergence | 0.303 s | 0.325 s | 0.339 s |
| Preferred-route restoration | 1.566 s | 1.618 s | 1.651 s |

Two of the five failover trials recorded one failed probe each. Both failures reported `ping: sendto: Network unreachable`. All recorded baseline and restoration probes succeeded.

These measurements describe this WSL2/Containerlab/FRR environment only. The convergence timer starts immediately before the interface-state command, not at an independently measured physical link event. Probes are discrete samples, so the results do not establish an exact packet-loss duration or prove that no other packets were lost.

Detailed methodology and trial results will be documented in `reports/bgp-failover-benchmark.md`.

## Failure injection and evidence correlation

The `failure_injection/` package provides reusable components for controlled network-failure experiments. It supports interface failure injection with automatic restoration, before/during/after evidence collection, condition-based route recovery detection, and scenario-level evidence correlation.

A verified BGP scenario disabled `clab-bgpline-r1:eth2`, the preferred R1-to-R3 path. The framework detected recovery through the backup R1-to-R2-to-R3 path, verified reachability during the stable failure state, restored the interface, and detected recovery of the preferred path.

The recorded scenario detected the backup-path condition in **0.163 s** and the preferred-path condition after restoration in **1.284 s**. These are single-run condition-detection times, not benchmark statistics or exact packet-loss-duration measurements.

The correlation reported `clab-bgpline-r1:eth2 link/path` as the probable failure domain. The current correlation and RCA implementation is **deterministic and rule-based**; it does not use an LLM or machine-learning model, and findings should be treated as evidence-based probable causes rather than independently proven root causes.

Run the controlled scenario with `python run_failure_scenario.py`. Structured scenario results are written under `results/`.

## Phase 6 — EVPN/VXLAN fabric validation and resiliency

Phase 6 adds a redundant leaf-spine EVPN/VXLAN fabric using FRRouting and Containerlab.

### Topology

```text
                 spine1          spine2
                   |\              /|
                   | \            / |
                   |  \          /  |
                 leaf1          leaf2
                   |              |
                 host1          host2
```

- `leaf1` and `leaf2` operate as VTEPs.
- Each leaf has an eBGP underlay connection to both spines.
- BGP EVPN provides the overlay control plane.
- L2 VNI `10100` provides tenant connectivity between the two hosts.
- The current Linux bridge implementation is VLAN-unaware; FRR reports the VNI on bridge default VLAN 1 rather than an explicitly configured VLAN 100.

### Validated behavior

Automated and manual validation covers:

- Underlay reachability and redundant paths between VTEP loopbacks.
- BGP EVPN neighbor establishment through both spines.
- EVPN Type-3 IMET route exchange and remote-VTEP discovery.
- EVPN Type-2 remote MAC route learning.
- Linux FDB programming of remote MAC entries with `extern_learn`.
- End-to-end tenant traffic across the VXLAN overlay.
- EVPN multipath through both spines.
- Single leaf-spine uplink failure with retention of the surviving EVPN path.
- Tenant forwarding after failure convergence.
- Restoration of two-path EVPN operation after link recovery.
- Persistent 9000-byte tenant MTU and end-to-end jumbo-frame validation.

A 9000-byte inner IPv4 packet was validated using an ICMP payload of 8972 bytes. A 9001-byte inner packet exceeded the configured overlay MTU during manual boundary testing. The underlay links use MTU 9500 to provide encapsulation headroom.

### EVPN resiliency benchmark

Five controlled `leaf1 eth1` failure/recovery trials were recorded in the Containerlab/FRR environment.

| Metric | Minimum | Average | Maximum |
|---|---:|---:|---:|
| EVPN neighbor-state detection | 1.133 s | 1.248 s | 1.305 s |
| EVPN path reduction, 2 → 1 | 1.453 s | 1.565 s | 1.645 s |
| EVPN path restoration, 1 → 2 | 1.392 s | 1.727 s | 2.506 s |

Continuous ICMP sampling across the five trials recorded:

- Total probes: **198**
- Successful probes: **194**
- Failed probes: **4**
- Observed success rate: **97.98%**

All stable post-convergence failure-window and recovery checks passed. The four failed continuous samples occurred close in time to the observed EVPN neighbor-state transition.

The benchmark evidence is stored in `results/evpn_failover_benchmark_20261015_180824.json`.

These timings are observations from a **WSL2/Containerlab/FRR software environment**. They are not hardware convergence specifications, SLA measurements, or exact packet-loss-duration measurements. Continuous traffic uses sampled ICMP probes rather than a precision traffic generator.

### EVPN failure evidence correlation

`failure_injection/evpn_correlation.py` consumes structured benchmark evidence and deterministically correlates:

- the injected leaf-spine link failure,
- EVPN neighbor-state transition,
- reduction from two EVPN paths to one,
- sampled traffic impact,
- and restoration of EVPN multipath.

This analysis is **deterministic and rule-based**. It is not an AI/ML or LLM-based RCA engine and does not claim that temporal correlation independently proves causality.

## Phase 7 — AI Fabric QoS, Congestion & ECN Validation (RoCEv2-Oriented)

Phase 7 extends the EVPN/VXLAN fabric with automated QoS, controlled congestion, and ECN validation using software-emulated traffic and Linux traffic control.

The goal is to validate networking behaviors relevant to AI/HPC Ethernet fabrics without claiming hardware RDMA or production RoCE capabilities that are not available in the current lab.

### Traffic profile

The experiment uses synthetic RoCEv2-oriented UDP traffic between the existing EVPN/VXLAN endpoints:

```text
host1 (192.168.10.11)
        |
        | UDP/4791
        | DSCP 26 + ECT(0)
        v
      leaf1
        |
   EVPN/VXLAN fabric
        |
      leaf2
        |
   HTB + RED/ECN
        |
        v
host2 (192.168.10.12)

```
The lab policy uses:
- UDP destination port 4791.
- DSCP 26.
- ECN ECT(0) at the sender.
- 1400-byte UDP payload.
- 1000 packets per second for 8 seconds.
- Approximately 11.2 Mbps offered payload traffic.
- A controlled 5 Mbps bottleneck on leaf2 eth3.
DSCP 26 is an explicit lab policy for this experiment and is not presented as a universal RoCEv2 DSCP assignment.

### Congestion and ECN experiment

Linux traffic control is used on leaf2 eth3 to create a reproducible software bottleneck.
An HTB class limits the egress path to 5 Mbit/s. A RED qdisc with ECN enabled is attached below the HTB class.
The automated experiment performs the following sequence:
1. Capture the original qdisc state.
2. Install the 5 Mbps HTB bottleneck.
3. Install RED with ECN enabled.
4. Start an ECN-aware UDP receiver on host2.
5. Generate DSCP 26 / ECT(0) traffic from host1.
6. Collect destination DSCP/ECN observations.
7. Collect qdisc congestion and marking counters.
8. Validate the experiment automatically.
9. Remove the temporary qdisc configuration.
10. Verify restoration of the original noqueue state.
11. Store structured JSON evidence.

### Validated behavior

The automated Phase 7 validation confirms:
- Synthetic UDP/4791 forwarding across the EVPN/VXLAN overlay.
- End-to-end preservation of DSCP 26.
- End-to-end preservation of ECN-capable ECT(0) traffic before congestion marking.
- Controlled congestion using a 5 Mbps HTB bottleneck.
- Linux RED congestion-management behavior with ECN enabled.
- Observation of CE-marked packets at the destination.
- RED marking activity and congestion overlimit telemetry.
- Automatic cleanup and restoration of the original qdisc state.
The representative evidence artifact is:
results/phase7/qos_ecn_setup_20261016_174048.json
That run recorded:
- Received packets: 3538
- ECT(0) packets received: 70
- CE packets received: 3468
- CE fraction among received packets: 98.02%
- RED marked counter: 7930
- Maximum observed overlimits counter: 7933
- Overall automated validation: PASS
The destination CE count and RED marking counter are observations from different points in the experiment and are not expected to be numerically identical.

### Automation

traffic/qos_traffic.py provides the reusable UDP sender/receiver and supports explicit DSCP and ECN values.
traffic/run_qos_ecn_experiment.py orchestrates traffic generation, congestion setup, telemetry collection, validation, cleanup, and JSON evidence generation.
tests/test_ai_fabric_qos.py adds five integration tests covering:
- overall experiment validation,
- DSCP preservation,
- ECN/CE observation,
- congestion telemetry,
- and qdisc cleanup.
All 5 Phase 7 integration tests passed.

### Scope and limitations

This phase validates real Linux IP QoS and ECN behavior inside a software-emulated EVPN/VXLAN fabric, but the generated workload is synthetic RoCEv2-oriented UDP traffic, not real RDMA/RoCE NIC traffic.
The experiment does not claim validation of:
- RDMA verbs, Queue Pairs, Memory Regions, or Completion Queues.
- Hardware Priority Flow Control (PFC / IEEE 802.1Qbb).
- DCQCN hardware congestion control.
- RDMA NIC or switch ASIC counters.
- Real RoCEv2 throughput or latency.
- GPU collective communication performance.
- Production lossless-Ethernet behavior.
The congestion experiment intentionally creates severe oversubscription and observes both ECN marking and packet drops. It therefore must not be interpreted as demonstrating a lossless fabric.


## Current test status

The latest verified full regression run on 2026-10-16 passed **44 tests in 70.09 seconds**.

The regression includes basic connectivity, BGP convergence and failover, OSPF reconvergence, EVPN/VXLAN control-plane and forwarding validation, jumbo MTU, failure injection, evidence correlation, deterministic RCA, and Phase 7 QoS/congestion/ECN validation.

Run `./run_tests.sh` after changes to verify the current status.

## Future work

Future hardware-backed validation can extend the project toward:

- Real RoCEv2 traffic using RDMA-capable NICs.
- RDMA verbs, Queue Pairs, Memory Regions, and Completion Queues.
- Priority Flow Control (PFC / IEEE 802.1Qbb).
- DCQCN congestion control.
- NIC and switch hardware congestion counters.
- GPU collective traffic and AI workload behavior.
- Hardware-backed throughput, latency, congestion, and failure validation.

These capabilities will only be reported as validated when suitable hardware or an environment that genuinely exposes those behaviors is available.

## Reproducibility notes

- Record the topology, environment, trial count, and measurement method with each benchmark.
- Do not overwrite historical results when rerunning experiments.
- Treat virtual-lab measurements as proof-of-concept observations, not hardware performance guarantees.
