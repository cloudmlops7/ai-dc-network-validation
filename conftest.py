from datetime import datetime
from pathlib import Path
import subprocess
import json

import pytest

from diagnostics.rca_engine import analyze_evidence

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def run_command(command, timeout=15):
    """Run a diagnostic command and return its output."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = result.stdout
        if result.stderr:
            output += "\nSTDERR:\n" + result.stderr
        return output or f"Exit code: {result.returncode}\n"
    except Exception as exc:
        return f"Diagnostic command failed: {exc}\n"


def collect_diagnostics():
    """Collect container, routing and FRR information."""
    sections = []
    containers_output = run_command([
        "docker", "ps", "-a", "--filter", "name=clab-",
        "--format", "{{.Names}} | {{.Status}}"
    ])

    sections.append("=== CONTAINER STATUS ===\n" + containers_output)

    names_output = run_command([
        "docker", "ps", "-a", "--filter", "name=clab-",
        "--format", "{{.Names}}"
    ])

    container_names = [
        line.strip() for line in names_output.splitlines() if line.strip()
    ]

    for name in container_names:
        sections.append(
            f"=== {name}: RECENT LOGS ===\n"
            + run_command(["docker", "logs", "--tail", "50", name])
        )

        if name.startswith("clab-") and any(
            f"-{router}" in name for router in ("r1", "r2", "r3")
        ):
            for command in (
                "show bgp ipv4 unicast summary",
                "show ip ospf neighbor",
                "show ip route",
            ):
                sections.append(
                    f"=== {name}: {command} ===\n"
                    + run_command([
                        "docker", "exec", name, "vtysh", "-c", command
                    ])
                )

    return "\n\n".join(sections)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if report.when != "call" or not report.failed:
        return

    # Unit tests should not trigger expensive network-wide diagnostics.
    if item.nodeid.replace("\\", "/").startswith("tests/unit/"):
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    diagnostics = collect_diagnostics()

    # Generate evidence-based findings; these are hypotheses, not
    # confirmed root causes.
    findings = analyze_evidence(diagnostics)
    rca_path = RESULTS_DIR / f"rca_{timestamp}_{item.name}.json"
    rca_path.write_text(
        json.dumps(findings, indent=2),
        encoding="utf-8",
    )
    rca_summary = json.dumps(findings, indent=2)

    log_path = RESULTS_DIR / (
        f"failure_{timestamp}_{item.name}.log"
    )
    log_path.write_text(diagnostics, encoding="utf-8")

    report.sections.append((
        "Network failure diagnostics",
        f"Saved to: {log_path}\n\n{diagnostics}",
    ))
    report.sections.append((
        "Rule-based RCA findings",
        f"Saved to: {rca_path}\n\n{rca_summary}",
    ))

    try:
        import pytest_html
        extras = getattr(report, "extras", [])
        extras.append(pytest_html.extras.text(
            diagnostics, name="Network failure diagnostics"
        ))
        extras.append(pytest_html.extras.text(
            rca_summary, name="Rule-based RCA findings"
        ))
        report.extras = extras
    except (ImportError, AttributeError):
        pass
