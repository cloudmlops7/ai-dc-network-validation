import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


LEAF = "clab-evpnvxlan-leaf2"
INTERFACE = "eth3"

HTB_RATE = "5mbit"

RESULT_DIR = Path("results/phase7")


def run_command(command, check=True):
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=check,
    )

    return {
        "command": " ".join(command),
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def get_qdisc():
    return run_command(
        [
            "docker",
            "exec",
            LEAF,
            "tc",
            "-s",
            "qdisc",
            "show",
            "dev",
            INTERFACE,
        ]
    )

def get_class():
    return run_command(
        [
            "docker",
            "exec",
            LEAF,
            "tc",
            "-s",
            "class",
            "show",
            "dev",
            INTERFACE,
        ]
    )

def install_qos():
    run_command(
        [
            "docker",
            "exec",
            LEAF,
            "tc",
            "qdisc",
            "replace",
            "dev",
            INTERFACE,
            "root",
            "handle",
            "1:",
            "htb",
            "default",
            "10",
        ]
    )

    run_command(
        [
            "docker",
            "exec",
            LEAF,
            "tc",
            "class",
            "add",
            "dev",
            INTERFACE,
            "parent",
            "1:",
            "classid",
            "1:10",
            "htb",
            "rate",
            HTB_RATE,
            "ceil",
            HTB_RATE,
        ]
    )

    run_command(
        [
            "docker",
            "exec",
            LEAF,
            "tc",
            "qdisc",
            "add",
            "dev",
            INTERFACE,
            "parent",
            "1:10",
            "handle",
            "10:",
            "red",
            "limit",
            "100000",
            "min",
            "15000",
            "max",
            "45000",
            "avpkt",
            "1500",
            "burst",
            "20",
            "bandwidth",
            HTB_RATE,
            "probability",
            "0.1",
            "ecn",
        ]
    )


def cleanup_qos():
    subprocess.run(
        [
            "docker",
            "exec",
            LEAF,
            "tc",
            "qdisc",
            "del",
            "dev",
            INTERFACE,
            "root",
        ],
        text=True,
        capture_output=True,
    )


def main():
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    evidence = {
        "experiment": "phase7_qos_ecn",
        "timestamp_utc": timestamp,
        "leaf": LEAF,
        "interface": INTERFACE,
        "htb_rate": HTB_RATE,
    }

    try:
        evidence["before"] = get_qdisc()

        install_qos()

        evidence["configured"] = {
            "qdisc": get_qdisc(),
            "class": get_class(),
    }

    finally:
        cleanup_qos()
        evidence["after_cleanup"] = get_qdisc()

        output = RESULT_DIR / f"qos_ecn_setup_{timestamp}.json"

        output.write_text(
            json.dumps(evidence, indent=2),
            encoding="utf-8",
        )

        print(f"Evidence: {output}")


if __name__ == "__main__":
    main()
