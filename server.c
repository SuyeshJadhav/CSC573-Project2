#include "common.h"
#include <time.h>

#define MAX_PAYLOAD_SIZE 2048 // Maximum expected UDP packet size for this project

int main(int argc, char *argv[]) {
    if (argc != 4) {
        fprintf(stderr, "Usage: %s <port#> <file-name> <p>\n", argv[0]);
        return EXIT_FAILURE;
    }

    int port = atoi(argv[1]);
    const char *file_name = argv[2];
    double p = atof(argv[3]);

    if (port != 7735) {
        printf("Warning: Port is %d, but project specifications strictly require 7735.\n", port);
    }

    // Seed the random number generator for probabilistic loss
    srand((unsigned int)time(NULL));

    init_networking();

    // Create UDP socket
    int sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    if (sockfd < 0) {
        perror("Socket creation failed");
        cleanup_networking();
        return EXIT_FAILURE;
    }

    struct sockaddr_in server_addr, client_addr;
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = INADDR_ANY;
    server_addr.sin_port = htons(port);

    if (bind(sockfd, (const struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        perror("Bind failed");
        closesocket(sockfd);
        cleanup_networking();
        return EXIT_FAILURE;
    }

    FILE *fp = fopen(file_name, "wb");
    if (!fp) {
        perror("Failed to open output file");
        closesocket(sockfd);
        cleanup_networking();
        return EXIT_FAILURE;
    }

    uint32_t expected_seq_num = 0;
    uint8_t buffer[MAX_PAYLOAD_SIZE];

    printf("Server listening on port %d... (Loss probability: %.2f)\n", port, p);

    while (1) {
        socklen_t client_len = sizeof(client_addr);
        ssize_t n = recvfrom(sockfd, (char *)buffer, MAX_PAYLOAD_SIZE, 0,
                             (struct sockaddr *)&client_addr, &client_len);
        if (n < 0) {
            perror("recvfrom failed");
            continue;
        }

        if (n < (ssize_t)sizeof(data_header_t)) {
            continue; // Packet too small to contain header
        }

        data_header_t *header = (data_header_t *)buffer;
        
        // Extract fields in network byte order
        uint16_t type = ntohs(header->type);
        uint32_t seq_num = ntohl(header->seq_num);

        // Probabilistic loss service: generate random r in [0, 1]
        double r = (double)rand() / RAND_MAX;
        if (r <= p) {
            printf("Packet loss, sequence number = %u\n", seq_num);
            continue; // Drop packet and do nothing
        }

        if (type == EOF_PACKET_TYPE) {
            // Acknowledge the EOF packet symmetrically
            ack_header_t ack;
            ack.seq_num = htonl(seq_num);
            ack.zero_field = 0;
            ack.type = htons(ACK_PACKET_TYPE);

            sendto(sockfd, (const char *)&ack, sizeof(ack), 0,
                   (const struct sockaddr *)&client_addr, client_len);
            
            printf("EOF packet received. Transfer complete.\n");
            break;
        }

        if (type != DATA_PACKET_TYPE) {
            continue; // Ignore unknown packet types
        }

        // Verify checksum
        // To verify, we set the header's checksum field to 0, calculate, and compare
        uint16_t received_checksum = header->checksum;
        header->checksum = 0;
        uint16_t calculated_checksum = calculate_checksum(buffer, n);

        if (received_checksum != calculated_checksum) {
            // Checksum failed, discard silently per instructions
            continue;
        }

        // Check sequence number for Go-back-N Receiver behavior
        if (seq_num == expected_seq_num) {
            // In sequence: Write payload to file
            size_t payload_size = n - sizeof(data_header_t);
            if (payload_size > 0) {
                fwrite(buffer + sizeof(data_header_t), 1, payload_size, fp);
            }

            // Send ACK
            ack_header_t ack;
            ack.seq_num = htonl(expected_seq_num);
            ack.zero_field = 0;
            ack.type = htons(ACK_PACKET_TYPE);

            sendto(sockfd, (const char *)&ack, sizeof(ack), 0,
                   (const struct sockaddr *)&client_addr, client_len);

            expected_seq_num++;
        }
        // Out of sequence: do nothing (discard silently)
    }

    fclose(fp);
    closesocket(sockfd);
    cleanup_networking();

    return EXIT_SUCCESS;
}
