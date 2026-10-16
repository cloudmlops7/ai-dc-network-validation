import argparse
import json
import socket
import time


def send_traffic(args):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    tos = (args.dscp << 2) | args.ecn
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, tos)
    sock.bind((args.source, 0))

    destination = (args.destination, args.port)
    payload = b"X" * args.payload

    sent_packets = 0
    start = time.monotonic()
    end = start + args.duration

    interval = 1.0 / args.pps
    next_send = start

    while time.monotonic() < end:
        sock.sendto(payload, destination)
        sent_packets += 1

        next_send += interval
        delay = next_send - time.monotonic()

        if delay > 0:
            time.sleep(delay)

    elapsed = time.monotonic() - start

    result = {
        "role": "sender",
        "source": args.source,
        "destination": args.destination,
        "destination_port": args.port,
        "payload_bytes": args.payload,
        "dscp": args.dscp,
        "ecn": args.ecn,
        "tos": tos,
        "sent_packets": sent_packets,
        "elapsed_seconds": round(elapsed, 3),
        "offered_payload_mbps": round(
            sent_packets * args.payload * 8 / elapsed / 1_000_000, 3
        ),
    }

    print(json.dumps(result))


def receive_traffic(args):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_RECVTOS, 1)
    sock.bind((args.destination, args.port))
    sock.settimeout(0.5)

    ecn_counts = {
        "not_ect": 0,
        "ect_1": 0,
        "ect_0": 0,
        "ce": 0,
    }

    dscp_counts = {}
    received_packets = 0
    received_bytes = 0

    start = time.monotonic()
    end = start + args.duration

    while time.monotonic() < end:
        try:
            data, ancillary, flags, address = sock.recvmsg(65535, 1024)
        except socket.timeout:
            continue

        tos = next(
            item[2][0]
            for item in ancillary
            if item[0] == socket.IPPROTO_IP
            and item[1] == socket.IP_TOS
        )

        dscp = tos >> 2
        ecn = tos & 3

        received_packets += 1
        received_bytes += len(data)

        dscp_counts[str(dscp)] = dscp_counts.get(str(dscp), 0) + 1

        if ecn == 0:
            ecn_counts["not_ect"] += 1
        elif ecn == 1:
            ecn_counts["ect_1"] += 1
        elif ecn == 2:
            ecn_counts["ect_0"] += 1
        elif ecn == 3:
            ecn_counts["ce"] += 1

    elapsed = time.monotonic() - start

    result = {
        "role": "receiver",
        "destination": args.destination,
        "destination_port": args.port,
        "received_packets": received_packets,
        "received_payload_bytes": received_bytes,
        "elapsed_seconds": round(elapsed, 3),
        "received_payload_mbps": round(
            received_bytes * 8 / elapsed / 1_000_000, 3
        ),
        "dscp_counts": dscp_counts,
        "ecn_counts": ecn_counts,
    }

    print(json.dumps(result))


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--source")
    parser.add_argument("--destination", required=True)
    parser.add_argument("--port", type=int, default=4791)
    parser.add_argument("--payload", type=int, default=1400)
    parser.add_argument("--duration", type=float, default=8)
    parser.add_argument("--pps", type=float, default=1000)
    parser.add_argument("--dscp", type=int, default=26)
    parser.add_argument("--ecn", type=int, default=2)
    parser.add_argument("--receive", action="store_true")

    args = parser.parse_args()

    if args.receive:
        receive_traffic(args)
    else:
        if not args.source:
            parser.error("--source is required when sending traffic")

        send_traffic(args)


if __name__ == "__main__":
    main()
