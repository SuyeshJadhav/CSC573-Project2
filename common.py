import struct

DATA_PACKET_TYPE = 0x5555
ACK_PACKET_TYPE = 0xAAAA
EOF_PACKET_TYPE = 0xFFFF

HEADER_FORMAT = "!IHH"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)


def calculate_checksum(data: bytes) -> int:
    sum_val = 0
    length = len(data)
    i = 0
    
    while length > 1:
        # Big-endian read of 16-bit unsigned int (matches UDP checksum standard)
        word = (data[i] << 8) | data[i+1]
        sum_val += word
        i += 2
        length -= 2
        
    if length > 0:
        # Pad an odd trailing byte on the right, as in the UDP checksum.
        sum_val += data[i] << 8
        
    while sum_val >> 16:
        sum_val = (sum_val & 0xFFFF) + (sum_val >> 16)
        
    return (~sum_val) & 0xFFFF


def make_packet(seq_num: int, pkt_type: int, payload: bytes = b"") -> bytes:
    checksum = calculate_checksum(payload)
    return struct.pack(HEADER_FORMAT, seq_num, checksum, pkt_type) + payload


def make_ack(seq_num: int) -> bytes:
    return struct.pack(HEADER_FORMAT, seq_num, 0, ACK_PACKET_TYPE)
