import sys
import socket
import time
import select
import struct
from common import DATA_PACKET_TYPE, ACK_PACKET_TYPE, EOF_PACKET_TYPE, HEADER_FORMAT, HEADER_SIZE, calculate_checksum

TIMEOUT_MS = 100

def get_time_ms():
    return int(time.perf_counter() * 1000)

def main():
    if len(sys.argv) != 6:
        print(f"Usage: {sys.argv[0]} <server-host-name> <server-port#> <file-name> <N> <MSS>", file=sys.stderr)
        sys.exit(1)

    server_host = sys.argv[1]
    port = int(sys.argv[2])
    file_name = sys.argv[3]
    N = int(sys.argv[4])
    MSS = int(sys.argv[5])

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    try:
        server_ip = socket.gethostbyname(server_host)
    except socket.gaierror:
        print(f"Could not resolve hostname: {server_host}", file=sys.stderr)
        sys.exit(1)

    server_addr = (server_ip, port)

    try:
        fp = open(file_name, "rb")
    except Exception as e:
        print(f"Failed to open input file: {e}", file=sys.stderr)
        sys.exit(1)

    window = [None] * N
    base = 0
    nextseqnum = 0
    
    file_buffer = bytearray()
    file_eof = False

    timer_start_ms = 0
    transfer_start_time = get_time_ms()

    while not file_eof or base < nextseqnum:
        # Send packets to fill the window (single file-read path)
        while nextseqnum < base + N:
            # Refill buffer if empty
            if len(file_buffer) == 0:
                if file_eof:
                    break
                data = fp.read(MSS)
                file_buffer = bytearray(data)
                if len(data) < MSS:
                    file_eof = True
                if len(file_buffer) == 0:
                    break

            slot = nextseqnum % N
            
            # Prepare packet — checksum over payload bytes only
            chksum = calculate_checksum(bytes(file_buffer))
            
            # Final packet
            pkt = struct.pack(HEADER_FORMAT, nextseqnum, chksum, DATA_PACKET_TYPE) + file_buffer
            window[slot] = pkt
            
            sock.sendto(pkt, server_addr)
            
            if base == nextseqnum:
                timer_start_ms = get_time_ms()
            
            nextseqnum += 1
            file_buffer = bytearray()

        # Handle timers and ACKs
        timeout = 0
        if base < nextseqnum:
            now = get_time_ms()
            remaining_ms = TIMEOUT_MS - (now - timer_start_ms)
            
            if remaining_ms <= 0:
                print(f"Timeout, sequence number = {base}")
                for i in range(base, nextseqnum):
                    slot = i % N
                    sock.sendto(window[slot], server_addr)
                timer_start_ms = get_time_ms()
                remaining_ms = TIMEOUT_MS
                
            timeout = max(0, remaining_ms) / 1000.0
        else:
            timeout = 0.01
            
        rlist, _, _ = select.select([sock], [], [], timeout)
        
        if rlist:
            try:
                ack_data, _ = sock.recvfrom(HEADER_SIZE)
                if len(ack_data) == HEADER_SIZE:
                    ack_seq, _, ack_type = struct.unpack(HEADER_FORMAT, ack_data)
                    if ack_type == ACK_PACKET_TYPE:
                        if base <= ack_seq < nextseqnum:
                            base = ack_seq + 1
                            if base != nextseqnum:
                                timer_start_ms = get_time_ms()
            except Exception:
                pass

    # EOF Signaling — checksum over payload only (empty, as EOF carries no data)
    eof_chksum = calculate_checksum(b"")
    eof_pkt = struct.pack(HEADER_FORMAT, nextseqnum, eof_chksum, EOF_PACKET_TYPE)

    eof_acked = False
    eof_retries = 0
    while not eof_acked and eof_retries < 10:
        sock.sendto(eof_pkt, server_addr)
        rlist, _, _ = select.select([sock], [], [], TIMEOUT_MS / 1000.0)
        
        if rlist:
            try:
                ack_data, _ = sock.recvfrom(HEADER_SIZE)
                if len(ack_data) == HEADER_SIZE:
                    ack_seq, _, ack_type = struct.unpack(HEADER_FORMAT, ack_data)
                    if ack_type == ACK_PACKET_TYPE and ack_seq == nextseqnum:
                        eof_acked = True
            except Exception:
                pass
        else:
            eof_retries += 1

    transfer_end_time = get_time_ms()
    print("File transfer completed.")
    print(f"Total transfer delay: {transfer_end_time - transfer_start_time} ms")

    fp.close()
    sock.close()

if __name__ == "__main__":
    main()
