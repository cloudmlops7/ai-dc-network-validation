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
- `tests/` — connectivity, failure detection, OSPF, BGP, and RCA unit tests.
- `results/` — timestamped HTML reports, logs, and benchmark CSV files.
- `docs/` — topology documentation and diagrams.
- `diagnostics/` — evidence-based, rule-driven RCA findings.
- `.github/workflows/` — automated RCA unit tests on GitHub.
- `reports/` — interpreted benchmark reports.
- `bgp_timing.py` — BGP measurement helpers.
- `run_bgp_trials.py` — repeated route-convergence measurements.
- `run_bgp_traffic_impact.py` — continuous-probe failover experiment.
- `run_bgp_traffic_trials.py` — repeated traffic-impact trials.
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

## Current test status

The latest verified full regression run passed 21 tests, including 6 isolated RCA unit tests. Run `./run_tests.sh` after changes to verify the current status.

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
