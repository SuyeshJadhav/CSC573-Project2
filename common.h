#ifndef COMMON_H
#define COMMON_H

#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
    #include <winsock2.h>
    #include <ws2tcpip.h>
#else
    #include <sys/socket.h>
    #include <arpa/inet.h>
    #include <unistd.h>
    #include <sys/time.h>
    #define closesocket close
#endif

#define DATA_PACKET_TYPE 0x5555
#define ACK_PACKET_TYPE  0xAAAA
#define EOF_PACKET_TYPE  0xFFFF

// Use #pragma pack to ensure no padding
#pragma pack(push, 1)

// Data packet header (8 bytes)
typedef struct {
    uint32_t seq_num;
    uint16_t checksum;
    uint16_t type;
} data_header_t;

// ACK packet header (8 bytes)
typedef struct {
    uint32_t seq_num;
    uint16_t zero_field;
    uint16_t type;
} ack_header_t;

#pragma pack(pop)

// Compute the 16-bit one's complement sum
uint16_t calculate_checksum(const uint8_t *data, size_t length);

// Initialize networking (WSAStartup on Windows, no-op on POSIX)
void init_networking();

// Cleanup networking
void cleanup_networking();

#endif // COMMON_H
