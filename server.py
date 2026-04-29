import sys
import socket
import random
import struct
from common import DATA_PACKET_TYPE, ACK_PACKET_TYPE, EOF_PACKET_TYPE, HEADER_FORMAT, HEADER_SIZE, calculate_checksum

MAX_PAYLOAD_SIZE = 2048

def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <port#> <file-name> <p>", file=sys.stderr)
        sys.exit(1)

    port = int(sys.argv[1])
    file_name = sys.argv[2]
    p = float(sys.argv[3])

    if port != 7735:
        print(f"Warning: Port is {port}, but project specifications strictly require 7735.")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', port))

    try:
        fp = open(file_name, "wb")
    except Exception as e:
        print(f"Failed to open output file: {e}", file=sys.stderr)
        sys.exit(1)

    expected_seq_num = 0

    print(f"Server listening on port {port}... (Loss probability: {p:.2f})")

    while True:
        try:
            buffer, client_addr = sock.recvfrom(MAX_PAYLOAD_SIZE)
        except Exception as e:
            print(f"recvfrom failed: {e}", file=sys.stderr)
            continue

        if len(buffer) < HEADER_SIZE:
            continue

        # Extract fields
        seq_num, received_checksum, pkt_type = struct.unpack(HEADER_FORMAT, buffer[:HEADER_SIZE])

        # Probabilistic loss service
        r = random.random()
        if r <= p:
            print(f"Packet loss, sequence number = {seq_num}")
            continue

        if pkt_type == EOF_PACKET_TYPE:
            ack_pkt = struct.pack(HEADER_FORMAT, seq_num, 0, ACK_PACKET_TYPE)
            sock.sendto(ack_pkt, client_addr)
            print("EOF packet received. Transfer complete.")
            break

        if pkt_type != DATA_PACKET_TYPE:
            continue

        # Verify checksum over payload bytes only (mirrors client-side computation)
        payload = buffer[HEADER_SIZE:]
        calculated_checksum = calculate_checksum(payload)

        if received_checksum != calculated_checksum:
            continue

        if seq_num == expected_seq_num:
            payload = buffer[HEADER_SIZE:]
            if payload:
                fp.write(payload)

            ack_pkt = struct.pack(HEADER_FORMAT, expected_seq_num, 0, ACK_PACKET_TYPE)
            sock.sendto(ack_pkt, client_addr)

            expected_seq_num += 1

    fp.close()
    sock.close()

if __name__ == "__main__":
    main()
