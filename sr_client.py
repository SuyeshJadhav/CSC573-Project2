import select
import socket
import struct
import sys
import time

from common import (
    ACK_PACKET_TYPE,
    DATA_PACKET_TYPE,
    EOF_PACKET_TYPE,
    HEADER_FORMAT,
    HEADER_SIZE,
    make_packet,
)

TIMEOUT_MS = 100


def get_time_ms():
    return int(time.perf_counter() * 1000)


def validate_args(window_size, mss):
    if window_size <= 0:
        raise ValueError("window size N must be positive")
    if mss <= 0:
        raise ValueError("MSS must be positive")


def drain_acks(sock, unacked_packets, sent_at_ms, base, next_seq_num):
    while True:
        ready, _, _ = select.select([sock], [], [], 0)
        if not ready:
            return base

        ack_data, _ = sock.recvfrom(HEADER_SIZE)
        if len(ack_data) < HEADER_SIZE:
            continue

        ack_seq, ack_zero, ack_type = struct.unpack(HEADER_FORMAT, ack_data[:HEADER_SIZE])
        if ack_type != ACK_PACKET_TYPE or ack_zero != 0:
            continue

        if ack_seq in unacked_packets:
            del unacked_packets[ack_seq]
            del sent_at_ms[ack_seq]

        while base < next_seq_num and base not in unacked_packets:
            base += 1


def retransmit_expired(sock, server_addr, unacked_packets, sent_at_ms):
    now = get_time_ms()
    for seq_num in sorted(unacked_packets):
        if now - sent_at_ms[seq_num] >= TIMEOUT_MS:
            print(f"Timeout, sequence number = {seq_num}")
            sock.sendto(unacked_packets[seq_num], server_addr)
            sent_at_ms[seq_num] = get_time_ms()


def seconds_until_next_timeout(sent_at_ms):
    if not sent_at_ms:
        return 0.01

    now = get_time_ms()
    remaining_ms = min(TIMEOUT_MS - (now - sent_time) for sent_time in sent_at_ms.values())
    return max(0, remaining_ms) / 1000.0


def main():
    if len(sys.argv) != 6:
        print(
            f"Usage: {sys.argv[0]} <server-host-name> <server-port#> <file-name> <N> <MSS>",
            file=sys.stderr,
        )
        sys.exit(1)

    server_host = sys.argv[1]
    port = int(sys.argv[2])
    file_name = sys.argv[3]
    window_size = int(sys.argv[4])
    mss = int(sys.argv[5])

    try:
        validate_args(window_size, mss)
    except ValueError as exc:
        print(f"Invalid argument: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        server_ip = socket.gethostbyname(server_host)
    except socket.gaierror:
        print(f"Could not resolve hostname: {server_host}", file=sys.stderr)
        sys.exit(1)

    server_addr = (server_ip, port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        fp = open(file_name, "rb")
    except OSError as exc:
        print(f"Failed to open input file: {exc}", file=sys.stderr)
        sock.close()
        sys.exit(1)

    base = 0
    next_seq_num = 0
    file_eof = False
    eof_seq_num = None
    unacked_packets = {}
    sent_at_ms = {}

    transfer_start_time = get_time_ms()

    try:
        while eof_seq_num is None or unacked_packets:
            while eof_seq_num is None and next_seq_num < base + window_size:
                payload = fp.read(mss)

                if payload:
                    pkt = make_packet(next_seq_num, DATA_PACKET_TYPE, payload)
                    sock.sendto(pkt, server_addr)
                    unacked_packets[next_seq_num] = pkt
                    sent_at_ms[next_seq_num] = get_time_ms()

                    next_seq_num += 1
                    if len(payload) < mss:
                        file_eof = True
                        break
                else:
                    file_eof = True
                    break

            if file_eof and eof_seq_num is None and next_seq_num < base + window_size:
                eof_seq_num = next_seq_num
                eof_pkt = make_packet(eof_seq_num, EOF_PACKET_TYPE)
                sock.sendto(eof_pkt, server_addr)
                unacked_packets[eof_seq_num] = eof_pkt
                sent_at_ms[eof_seq_num] = get_time_ms()
                next_seq_num += 1

            retransmit_expired(sock, server_addr, unacked_packets, sent_at_ms)

            timeout = seconds_until_next_timeout(sent_at_ms)
            ready, _, _ = select.select([sock], [], [], timeout)
            if ready:
                base = drain_acks(sock, unacked_packets, sent_at_ms, base, next_seq_num)

    finally:
        fp.close()
        sock.close()

    transfer_end_time = get_time_ms()
    print("Selective Repeat file transfer completed.")
    print(f"Total transfer delay: {transfer_end_time - transfer_start_time} ms")


if __name__ == "__main__":
    main()
