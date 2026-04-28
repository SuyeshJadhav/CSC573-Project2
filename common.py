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
        # Simulate little-endian read of 16-bit unsigned int
        word = data[i] | (data[i+1] << 8)
        sum_val += word
        i += 2
        length -= 2
        
    if length > 0:
        sum_val += data[i]
        
    while sum_val >> 16:
        sum_val = (sum_val & 0xFFFF) + (sum_val >> 16)
        
    return (~sum_val) & 0xFFFF
