# AI Data-Center Network Validation and Automated RCA

A hands-on network validation proof of concept using Containerlab, FRRouting (FRR), Linux containers, Python, and pytest.

## Project goals

- Validate IP connectivity and routing behavior through automated tests.
- Exercise OSPF adjacency, route installation, and alternate-path forwarding.
- Validate BGP neighbor establishment, route learning, failover, and recovery.
- Measure route convergence and observe probe behavior during failures.
- Build a foundation for future AI data-center fabric validation and automated root-cause analysis.

## Environment

- Ubuntu 24.04 on WSL2
- Containerlab
- Docker Engine
- FRRouting containers
- Python virtual environment with pytest and pytest-html

## Repository layout

- `topology/` — Containerlab YAML files and FRR configurations.
- `tests/` — connectivity, failure detection, OSPF, BGP, failure-injection, correlation, and RCA tests.
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

## Current test status

The latest verified full regression run on 2026-10-15 passed **30 tests in 36.46 seconds**, including **15 isolated unit tests** covering the RCA engine and failure-injection/evidence-correlation framework. Run `./run_tests.sh` after changes to verify the current status.

## Future work

- Improve diagnostics and evidence-based failure reporting; current RCA findings are hypotheses, not confirmed root causes.
- Extend routing and convergence tests.
- Explore EVPN/VXLAN validation.
- Add RoCEv2-related scenarios for MTU, ECN, PFC, and congestion behavior where the lab supports them.
- Clearly distinguish software simulation from real RDMA hardware and data-center switch validation.

## Reproducibility notes

- Record the topology, environment, trial count, and measurement method with each benchmark.
- Do not overwrite historical results when rerunning experiments.
- Treat virtual-lab measurements as proof-of-concept observations, not hardware performance guarantees.
