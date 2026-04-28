#include "common.h"

#ifdef _WIN32
#include <windows.h>
long long get_time_ms() {
    LARGE_INTEGER freq;
    LARGE_INTEGER time;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&time);
    return (long long)((time.QuadPart * 1000) / freq.QuadPart);
}
#else
#include <time.h>
long long get_time_ms() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long long)(ts.tv_sec * 1000 + ts.tv_nsec / 1000000);
}
#endif

#define TIMEOUT_MS 100

typedef struct {
    uint8_t *packet;
    size_t packet_len;
} window_slot_t;

int main(int argc, char *argv[]) {
    if (argc != 6) {
        fprintf(stderr, "Usage: %s <server-host-name> <server-port#> <file-name> <N> <MSS>\n", argv[0]);
        return EXIT_FAILURE;
    }

    const char *server_host = argv[1];
    int port = atoi(argv[2]);
    const char *file_name = argv[3];
    int N = atoi(argv[4]);
    int MSS = atoi(argv[5]);

    init_networking();

    int sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    if (sockfd < 0) {
        perror("Socket creation failed");
        cleanup_networking();
        return EXIT_FAILURE;
    }

    struct hostent *host = gethostbyname(server_host);
    if (!host) {
        fprintf(stderr, "Could not resolve hostname: %s\n", server_host);
        closesocket(sockfd);
        cleanup_networking();
        return EXIT_FAILURE;
    }

    struct sockaddr_in server_addr;
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    memcpy(&server_addr.sin_addr.s_addr, host->h_addr, host->h_length);
    server_addr.sin_port = htons(port);

    FILE *fp = fopen(file_name, "rb");
    if (!fp) {
        perror("Failed to open input file");
        closesocket(sockfd);
        cleanup_networking();
        return EXIT_FAILURE;
    }

    window_slot_t *window = (window_slot_t *)malloc(N * sizeof(window_slot_t));
    for (int i = 0; i < N; i++) {
        // Allocate space for header + MSS
        window[i].packet = (uint8_t *)malloc(sizeof(data_header_t) + MSS);
        window[i].packet_len = 0;
    }

    int base = 0;
    int nextseqnum = 0;
    
    uint8_t *file_buffer = (uint8_t *)malloc(MSS);
    size_t file_buffer_len = 0;
    int file_eof = 0;

    long long timer_start_ms = 0;
    long long transfer_start_time = get_time_ms();

    while (!file_eof || base < nextseqnum) {
        // 1. Buffer bytes from file using rdt_send() abstraction logic
        if (!file_eof && file_buffer_len < (size_t)MSS) {
            size_t bytes_to_read = MSS - file_buffer_len;
            size_t nread = fread(file_buffer + file_buffer_len, 1, bytes_to_read, fp);
            file_buffer_len += nread;
            if (nread < bytes_to_read) {
                file_eof = 1;
            }
        }

        // 2. Send packet if window is not full and we have enough data (or EOF reached)
        while (nextseqnum < base + N && (file_buffer_len == (size_t)MSS || (file_eof && file_buffer_len > 0))) {
            int slot = nextseqnum % N;
            size_t pkt_len = sizeof(data_header_t) + file_buffer_len;
            uint8_t *pkt = window[slot].packet;
            
            data_header_t *hdr = (data_header_t *)pkt;
            hdr->seq_num = htonl(nextseqnum);
            hdr->type = htons(DATA_PACKET_TYPE);
            hdr->checksum = 0;
            memcpy(pkt + sizeof(data_header_t), file_buffer, file_buffer_len);
            
            hdr->checksum = calculate_checksum(pkt, pkt_len);
            
            window[slot].packet_len = pkt_len;

            // Send packet
            sendto(sockfd, (const char *)pkt, pkt_len, 0, (struct sockaddr *)&server_addr, sizeof(server_addr));
            
            if (base == nextseqnum) {
                timer_start_ms = get_time_ms();
            }
            nextseqnum++;
            file_buffer_len = 0; // Buffer consumed
            
            // Re-read immediately if possible to fill next packet in window
            if (!file_eof) {
                size_t nread = fread(file_buffer, 1, MSS, fp);
                file_buffer_len = nread;
                if (nread < (size_t)MSS) {
                    file_eof = 1;
                }
            }
        }

        // 3. Handle Timers and ACKs
        struct timeval tv;
        if (base < nextseqnum) {
            long long now = get_time_ms();
            long long remaining_ms = TIMEOUT_MS - (now - timer_start_ms);
            
            if (remaining_ms <= 0) {
                printf("Timeout, sequence number = %d\n", base);
                // Retransmit all unacknowledged packets
                for (int i = base; i < nextseqnum; i++) {
                    int slot = i % N;
                    sendto(sockfd, (const char *)window[slot].packet, window[slot].packet_len, 0, 
                           (struct sockaddr *)&server_addr, sizeof(server_addr));
                }
                timer_start_ms = get_time_ms();
                remaining_ms = TIMEOUT_MS;
            }
            
            tv.tv_sec = (long)(remaining_ms / 1000);
            tv.tv_usec = (long)((remaining_ms % 1000) * 1000);
        } else {
            tv.tv_sec = 0;
            tv.tv_usec = 10000; // 10ms poll if waiting for EOF processing
        }

        fd_set readfds;
        FD_ZERO(&readfds);
        FD_SET(sockfd, &readfds);

        int ret = select(sockfd + 1, &readfds, NULL, NULL, &tv);
        if (ret > 0 && FD_ISSET(sockfd, &readfds)) {
            ack_header_t ack;
            struct sockaddr_in from;
            socklen_t fromlen = sizeof(from);
            ssize_t n = recvfrom(sockfd, (char *)&ack, sizeof(ack), 0, (struct sockaddr *)&from, &fromlen);
            
            if (n == sizeof(ack_header_t) && ntohs(ack.type) == ACK_PACKET_TYPE) {
                uint32_t ack_seq = ntohl(ack.seq_num);
                // Cumulative ACK validation
                if (ack_seq >= (uint32_t)base && ack_seq < (uint32_t)nextseqnum) {
                    base = ack_seq + 1;
                    if (base == nextseqnum) {
                        // All outstanding packets acknowledged
                    } else {
                        // Restart timer for remaining unacked packets
                        timer_start_ms = get_time_ms();
                    }
                }
            }
        }
    }

    // 4. Connection Teardown (EOF Signaling)
    data_header_t eof_hdr;
    eof_hdr.seq_num = htonl(nextseqnum);
    eof_hdr.type = htons(EOF_PACKET_TYPE);
    eof_hdr.checksum = 0;
    eof_hdr.checksum = calculate_checksum((uint8_t *)&eof_hdr, sizeof(eof_hdr));

    int eof_acked = 0;
    int eof_retries = 0;
    while (!eof_acked && eof_retries < 10) {
        sendto(sockfd, (const char *)&eof_hdr, sizeof(eof_hdr), 0, (struct sockaddr *)&server_addr, sizeof(server_addr));
        
        struct timeval tv;
        tv.tv_sec = 0;
        tv.tv_usec = TIMEOUT_MS * 1000;
        
        fd_set readfds;
        FD_ZERO(&readfds);
        FD_SET(sockfd, &readfds);
        
        int ret = select(sockfd + 1, &readfds, NULL, NULL, &tv);
        if (ret > 0) {
            ack_header_t ack;
            ssize_t n = recvfrom(sockfd, (char *)&ack, sizeof(ack), 0, NULL, NULL);
            if (n == sizeof(ack_header_t) && ntohs(ack.type) == ACK_PACKET_TYPE && ntohl(ack.seq_num) == (uint32_t)nextseqnum) {
                eof_acked = 1;
            }
        } else {
            eof_retries++;
        }
    }

    long long transfer_end_time = get_time_ms();
    printf("File transfer completed.\n");
    printf("Total transfer delay: %lld ms\n", (transfer_end_time - transfer_start_time));

    // Cleanup
    for (int i = 0; i < N; i++) {
        free(window[i].packet);
    }
    free(window);
    free(file_buffer);
    fclose(fp);
    closesocket(sockfd);
    cleanup_networking();

    return EXIT_SUCCESS;
}
