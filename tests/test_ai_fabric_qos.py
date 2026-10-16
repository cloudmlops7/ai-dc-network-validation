import json
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = PROJECT_ROOT / "traffic" / "run_qos_ecn_experiment.py"
RESULT_DIR = PROJECT_ROOT / "results" / "phase7"


@pytest.fixture(scope="module")
def qos_ecn_evidence():
    before = set(RESULT_DIR.glob("qos_ecn_setup_*.json"))

    result = subprocess.run(
        ["python", str(EXPERIMENT)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, (
        result.stdout + result.stderr
    )

    after = set(RESULT_DIR.glob("qos_ecn_setup_*.json"))
    new_files = after - before

    assert len(new_files) == 1, (
        f"Expected one new evidence file, found {len(new_files)}"
    )

    evidence_file = new_files.pop()

    with evidence_file.open(encoding="utf-8") as file:
        return json.load(file)

def test_qos_ecn_overall_validation(qos_ecn_evidence):
    validation = qos_ecn_evidence["validation"]

    assert validation["overall"] == "PASS"


def test_dscp_preserved(qos_ecn_evidence):
    validation = qos_ecn_evidence["validation"]
    checks = validation["checks"]

    assert checks["dscp_26_observed"]
    assert checks["all_received_packets_preserved_dscp_26"]


def test_ecn_ce_marking_observed(qos_ecn_evidence):
    validation = qos_ecn_evidence["validation"]
    checks = validation["checks"]
    measurements = validation["measurements"]

    assert checks["ecn_capable_packets_observed"]
    assert checks["ce_observed"]
    assert measurements["ce_received"] > 0


def test_congestion_telemetry_observed(qos_ecn_evidence):
    validation = qos_ecn_evidence["validation"]
    checks = validation["checks"]
    measurements = validation["measurements"]

    assert checks["red_marking_observed"]
    assert checks["congestion_overlimits_observed"]

    assert measurements["red_marked"] > 0
    assert measurements["max_overlimits"] > 0


def test_qos_cleanup_restored(qos_ecn_evidence):
    validation = qos_ecn_evidence["validation"]

    assert validation["checks"]["cleanup_restored_noqueue"]
