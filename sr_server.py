import random
import socket
import struct
import sys

from common import (
    DATA_PACKET_TYPE,
    EOF_PACKET_TYPE,
    HEADER_FORMAT,
    HEADER_SIZE,
    calculate_checksum,
    make_ack,
)

MAX_UDP_PACKET_SIZE = 65535


def validate_args(port, loss_probability, window_size):
    if port <= 0 or port > 65535:
        raise ValueError("port must be in the range 1..65535")
    if loss_probability < 0.0 or loss_probability >= 1.0:
        raise ValueError("loss probability p must satisfy 0 <= p < 1")
    if window_size <= 0:
        raise ValueError("receiver window size N must be positive")


def main():
    if len(sys.argv) != 5:
        print(f"Usage: {sys.argv[0]} <port#> <file-name> <p> <N>", file=sys.stderr)
        sys.exit(1)

    port = int(sys.argv[1])
    file_name = sys.argv[2]
    loss_probability = float(sys.argv[3])
    window_size = int(sys.argv[4])

    try:
        validate_args(port, loss_probability, window_size)
    except ValueError as exc:
        print(f"Invalid argument: {exc}", file=sys.stderr)
        sys.exit(1)

    if port != 7735:
        print(f"Warning: Port is {port}, but project specifications strictly require 7735.")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", port))

    try:
        fp = open(file_name, "wb")
    except OSError as exc:
        print(f"Failed to open output file: {exc}", file=sys.stderr)
        sock.close()
        sys.exit(1)

    base = 0
    receive_buffer = {}
    eof_seq_num = None

    print(
        f"Selective Repeat server listening on port {port}... "
        f"(Loss probability: {loss_probability:.2f}, N: {window_size})"
    )

    try:
        while True:
            try:
                packet, client_addr = sock.recvfrom(MAX_UDP_PACKET_SIZE)
            except OSError as exc:
                print(f"recvfrom failed: {exc}", file=sys.stderr)
                continue

            if len(packet) < HEADER_SIZE:
                continue

            seq_num, received_checksum, pkt_type = struct.unpack(HEADER_FORMAT, packet[:HEADER_SIZE])

            if random.random() <= loss_probability:
                print(f"Packet loss, sequence number = {seq_num}")
                continue

            if pkt_type == DATA_PACKET_TYPE:
                payload = packet[HEADER_SIZE:]
                if received_checksum != calculate_checksum(payload):
                    continue

                if base <= seq_num < base + window_size:
                    sock.sendto(make_ack(seq_num), client_addr)
                    if seq_num not in receive_buffer:
                        receive_buffer[seq_num] = payload

                    while base in receive_buffer:
                        fp.write(receive_buffer.pop(base))
                        base += 1

                elif seq_num < base:
                    sock.sendto(make_ack(seq_num), client_addr)

            elif pkt_type == EOF_PACKET_TYPE:
                if received_checksum != calculate_checksum(b""):
                    continue

                if base <= seq_num < base + window_size:
                    sock.sendto(make_ack(seq_num), client_addr)
                    eof_seq_num = seq_num
                elif seq_num < base:
                    sock.sendto(make_ack(seq_num), client_addr)

            if eof_seq_num is not None and base == eof_seq_num:
                print("EOF packet received. Transfer complete.")
                break

    finally:
        fp.close()
        sock.close()


if __name__ == "__main__":
    main()
