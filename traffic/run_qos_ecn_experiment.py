import json
import subprocess
import sys
import time
import re
from datetime import datetime, timezone
from pathlib import Path


LEAF = "clab-evpnvxlan-leaf2"
INTERFACE = "eth3"

HOST1 = "clab-evpnvxlan-host1"
HOST2 = "clab-evpnvxlan-host2"

SOURCE_IP = "192.168.10.11"
DESTINATION_IP = "192.168.10.12"
PORT = 4791

DSCP = 26
ECN = 2
PAYLOAD = 1400
PPS = 1000

SENDER_DURATION = 8
RECEIVER_DURATION = 10

HTB_RATE = "5mbit"

RESULT_DIR = Path("results/phase7")
TRAFFIC_SCRIPT = Path("traffic/qos_traffic.py")

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

def run_traffic():
    script = TRAFFIC_SCRIPT.read_text(encoding="utf-8")

    receiver_command = [
        "docker",
        "exec",
        "-i",
        HOST2,
        "python3",
        "-",
        "--destination",
        DESTINATION_IP,
        "--port",
        str(PORT),
        "--duration",
        str(RECEIVER_DURATION),
        "--receive",
    ]

    sender_command = [
        "docker",
        "exec",
        "-i",
        HOST1,
        "python3",
        "-",
        "--source",
        SOURCE_IP,
        "--destination",
        DESTINATION_IP,
        "--port",
        str(PORT),
        "--payload",
        str(PAYLOAD),
        "--duration",
        str(SENDER_DURATION),
        "--pps",
        str(PPS),
        "--dscp",
        str(DSCP),
        "--ecn",
        str(ECN),
    ]

    receiver = subprocess.Popen(
        receiver_command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    receiver.stdin.write(script)
    receiver.stdin.close()
    receiver.stdin = None

    time.sleep(1)

    sender = subprocess.run(
        sender_command,
        input=script,
        text=True,
        capture_output=True,
        check=True,
    )

    receiver_stdout, receiver_stderr = receiver.communicate()

    if receiver.returncode != 0:
        raise RuntimeError(
            f"Receiver failed: {receiver_stderr}"
        )

    return {
        "sender": json.loads(sender.stdout),
        "receiver": json.loads(receiver_stdout),
    }

def validate_experiment(traffic, after_traffic, after_cleanup):
    sender = traffic["sender"]
    receiver = traffic["receiver"]

    dscp_26 = receiver["dscp_counts"].get(str(DSCP), 0)
    ecn_counts = receiver["ecn_counts"]

    received = receiver["received_packets"]
    ect0 = ecn_counts["ect_0"]
    ce = ecn_counts["ce"]

    qdisc_output = after_traffic["qdisc"]["stdout"]
    cleanup_output = after_cleanup["stdout"]

    marked_values = [
        int(value)
        for value in re.findall(r"\bmarked\s+(\d+)", qdisc_output)
    ]

    overlimit_values = [
        int(value)
        for value in re.findall(r"\boverlimits\s+(\d+)", qdisc_output)
    ]

    red_marked = max(marked_values, default=0)
    max_overlimits = max(overlimit_values, default=0)

    checks = {
        "traffic_generated": sender["sent_packets"] > 0,
        "traffic_received": received > 0,
        "dscp_26_observed": dscp_26 > 0,
        "all_received_packets_preserved_dscp_26": dscp_26 == received,
        "ecn_capable_packets_observed": (ect0 + ce) > 0,
        "ce_observed": ce > 0,
        "red_marking_observed": red_marked > 0,
        "congestion_overlimits_observed": max_overlimits > 0,
        "cleanup_restored_noqueue": "qdisc noqueue" in cleanup_output,
    }

    return {
        "checks": checks,
        "measurements": {
            "red_marked": red_marked,
            "max_overlimits": max_overlimits,
            "received_packets": received,
            "ect0_received": ect0,
            "ce_received": ce,
        },
        "overall": "PASS" if all(checks.values()) else "FAIL",
        "ce_fraction_of_received": (
            round(ce / received, 4) if received else 0
        ),
    }

def main():
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    evidence = {
        "experiment": "phase7_qos_ecn",
        "timestamp_utc": timestamp,
        "leaf": LEAF,
        "interface": INTERFACE,
        "htb_rate": HTB_RATE,
        "traffic_profile": {
            "description": "Synthetic RoCEv2-oriented UDP traffic",
            "protocol": "UDP",
            "destination_port": PORT,
            "source_ip": SOURCE_IP,
            "destination_ip": DESTINATION_IP,
            "dscp": DSCP,
            "ecn_initial": "ECT(0)",
            "ecn_value": ECN,
            "payload_bytes": PAYLOAD,
            "pps": PPS,
            "note": "Software-emulated traffic; not real RDMA/RoCE NIC traffic",
        },
    }
    try:
        evidence["before"] = get_qdisc()

        install_qos()

        evidence["configured"] = {
            "qdisc": get_qdisc(),
            "class": get_class(),
        }
        evidence["traffic"] = run_traffic()

        evidence["after_traffic"] = {
            "qdisc": get_qdisc(),
            "class": get_class(),
        }

    finally:
        cleanup_qos()
        evidence["after_cleanup"] = get_qdisc()

        if "traffic" in evidence and "after_traffic" in evidence:
            evidence["validation"] = validate_experiment(
                evidence["traffic"],
                evidence["after_traffic"],
                evidence["after_cleanup"],
            )

        output = RESULT_DIR / f"qos_ecn_setup_{timestamp}.json"

        output.write_text(
            json.dumps(evidence, indent=2),
            encoding="utf-8",
        )

        print(f"Evidence: {output}")


if __name__ == "__main__":
    main()
