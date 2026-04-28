# Project Plan: Simple-FTP with Go-back-N ARQ (C Language)

## 1. Overview
The goal of this project is to implement a reliable file transfer protocol (Simple-FTP) over UDP using the Go-back-N (GBN) Automatic Repeat reQuest (ARQ) scheme in C. The architecture consists of a Sender (Client) and a Receiver (Server).

## 2. Components

### 2.1 Simple-FTP Client (Sender)
*   **Responsibilities:**
    *   Implement the `rdt_send()` abstraction: read data from a file on a byte-by-byte basis and buffer it until at least one `MSS` worth of bytes is accumulated.
    *   Maintain the Go-back-N sliding window (size `N`).
    *   Encapsulate data into UDP packets with exactly `MSS` bytes of payload (except possibly the very last segment, which may be smaller to handle the end of the file).
    *   Handle ACK reception, advance the window, and retransmit unacknowledged packets on timeout. *Crucially, on timeout, the client must retransmit ALL outstanding, unacknowledged packets in the window (from `base` to `nextseqnum - 1`).*
*   **Packet Header Format:**
    *   `uint32_t seq_num`: 32-bit sequence number (starting at 0).
    *   `uint16_t checksum`: 16-bit checksum of the data part.
    *   `uint16_t type`: 16-bit field with value `0x5555` (0101010101010101 in binary) for data packets.
*   **Invocation:**
    ```bash
    ./Simple_ftp_client <server-host-name> <server-port#> <file-name> <N> <MSS>
    ```
    *(Note: The PDF mistakenly wrote `Simple_ftp_server` for the client invocation on page 2, but it is standard to name the client executable `Simple_ftp_client`)*
*   **Output Requirement:**
    *   On timeout: `Timeout, sequence number = Y`

### 2.2 Simple-FTP Server (Receiver)
*   **Responsibilities:**
    *   Listen for incoming UDP data packets. The port number is provided via command line but must always be `7735` for this project.
    *   Implement probabilistic packet loss using the parameter `p`.
    *   Verify the checksum and check if the sequence number is the expected in-order packet.
    *   If correct, send an ACK packet and write the data to the specified output file.
    *   **Out-of-Sequence Behavior:** If a packet is out-of-sequence or has a bad checksum, the server must strictly do *nothing* (discard silently), as explicitly stated in the PDF (unlike standard TCP/Kurose-Ross GBN which sends a duplicate cumulative ACK).
*   **ACK Header Format:**
    *   `uint32_t seq_num`: 32-bit sequence number being ACKed.
    *   `uint16_t zero_field`: 16-bit field that is all zeroes.
    *   `uint16_t type`: 16-bit field with value `0xAAAA` (1010101010101010 in binary) for ACK packets.
*   **Probabilistic Loss Service:**
    *   For every received packet, generate a random number `r` in `(0, 1)`. If `r <= p`, drop the packet and do not process it.
*   **Invocation:**
    ```bash
    ./Simple_ftp_server <port#> <file-name> <p>
    ```
*   **Output Requirement:**
    *   On packet drop: `Packet loss, sequence number = X`

## 3. Implementation Steps

1.  **Header Definitions & Endianness:** 
    *   Define C `struct` types for the Data Packet and ACK headers using `<stdint.h>` and `__attribute__((packed))`.
    *   **Critical:** Use `htonl()`, `ntohl()`, `htons()`, `ntohs()` when reading/writing `seq_num` and `type` fields to ensure network byte order across the wire.
2.  **Checksum Function:** Implement the 16-bit one's complement sum of the data payload.
3.  **UDP Sockets Initialization:** Write setup code for UDP sockets on both client and server (`socket`, `bind`, `recvfrom`, `sendto`).
4.  **Server Logic:**
    *   Implement random number generation for the loss service (using `drand48()` seeded properly).
    *   Handle incoming packets, checking `p`, checksum, and expected sequence number.
    *   Implement ACK response and file writing, strictly doing nothing for out-of-order packets.
5.  **Client Logic:**
    *   Implement the `rdt_send()` interface to buffer bytes.
    *   Set up an array or circular buffer to act as the Go-back-N sliding window buffer.
    *   Implement `select()` or `poll()` with a timeout mechanism. The timeout value should be chosen based on expected RTT (e.g., hardcoded to a reasonable value like 50-100ms for local/campus testing, or dynamically calculated).
    *   Handle incoming ACKs to slide the window forward.
    *   On timeout, retransmit *all* packets from `base` to `nextseqnum - 1`.
6.  **EOF / Connection Teardown Signaling:**
    *   Although the PDF says to omit connection teardown, the server still needs to know when to close the file. Implement an EOF signal, such as sending a packet with 0 bytes of payload and sequence number indicating the end, or a special `type` field value (e.g., `0xFFFF`), after the file transfer completes and all ACKs are received.
7.  **Timing Mechanism:**
    *   Use `clock_gettime(CLOCK_MONOTONIC, ...)` or `gettimeofday()` inside the client around the entire transfer process to accurately measure and log the total delay for the experiments.
8.  **Testing & Debugging:**
    *   Test locally (`127.0.0.1`) with varying `p`, `N`, and `MSS`.
    *   **File Integrity Verification:** Use `md5sum <original_file> <received_file>` or `diff` to rigorously verify that the files match exactly before running experiments.

## 4. Evaluation Tasks (Experiments)

**Pre-requisites:**
- [ ] Ensure the test file is >1MB.
- [ ] Run the client on your local machine (e.g., laptop).
- [ ] Run the server on a distinct remote host separated by multiple router hops (e.g., EOS campus machine).
- [ ] Record the Round-Trip Time (RTT) between client and server using `traceroute`. Include this in the report.

*   **Task 1: Effect of Window Size (N)**
    *   Fixed: `MSS = 500`, `p = 0.05`
    *   Vary `N`: 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024
    *   Action: Plot Average delay (over 5 runs) vs `N`
*   **Task 2: Effect of MSS**
    *   Fixed: `N = 64`, `p = 0.05`
    *   Vary `MSS`: 100 to 1000 (increments of 100)
    *   Action: Plot Average delay (over 5 runs) vs `MSS`
*   **Task 3: Effect of Loss Probability (p)**
    *   Fixed: `MSS = 500`, `N = 64`
    *   Vary `p`: 0.01 to 0.10 (increments of 0.01)
    *   Action: Plot Average delay (over 5 runs) vs `p`

## 5. Extra Credit (Optional - 10 points)
*   Implement Selective Repeat ARQ protocol.
*   Repeat Tasks 1-3 using the Selective Repeat implementation. (Ensure Go-back-N is completed first).
