#include "common.h"

uint16_t calculate_checksum(const uint8_t *data, size_t length) {
    uint32_t sum = 0;
    const uint16_t *ptr = (const uint16_t *)data;

    while (length > 1) {
        sum += *ptr++;
        length -= 2;
    }

    if (length > 0) {
        sum += *(const uint8_t *)ptr;
    }

    while (sum >> 16) {
        sum = (sum & 0xFFFF) + (sum >> 16);
    }

    return (uint16_t)(~sum);
}

void init_networking() {
#ifdef _WIN32
    WSADATA wsaData;
    if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
        fprintf(stderr, "WSAStartup failed.\n");
        exit(EXIT_FAILURE);
    }
#endif
}

void cleanup_networking() {
#ifdef _WIN32
    WSACleanup();
#endif
}
