# Simple-FTP with Go-Back-N ARQ

A reliable file transfer protocol (Simple-FTP) implemented over UDP using the **Go-Back-N (GBN) Automatic Repeat reQuest** scheme in Python.

Built for **CSC/ECE 573 – Internet Protocols, Spring 2026**.

---

## Overview

Simple-FTP transfers a file from a **client (sender)** to a **server (receiver)** over UDP. Since UDP is unreliable, reliability is achieved through the Go-Back-N ARQ protocol, which handles:

- Sliding window flow control
- Packet loss detection via timeout and retransmission
- Checksum verification
- Probabilistic packet loss simulation on the server

---

## Files

| File | Description |
|---|---|
| `client.py` | Simple-FTP sender — reads a file and transfers it using GBN |
| `server.py` | Simple-FTP receiver — receives packets and writes to file |
| `sr_client.py` | Extra-credit Selective Repeat sender |
| `sr_server.py` | Extra-credit Selective Repeat receiver |
| `common.py` | Shared constants, packet format definitions, and checksum function |

---

## Requirements

- Python 3.8+
- No external dependencies (uses only stdlib: `socket`, `struct`, `select`, `random`)

---

## Usage

### 1. Start the Server

```bash
python server.py <port#> <output-file> <loss-probability>
```

**Example:**
```bash
python server.py 7735 received_file.dat 0.05
```

> ⚠️ Port must be `7735` per project specification.

**Output on packet drop:**
```
Packet loss, sequence number = X
```

---

### 2. Run the Client

```bash
python client.py <server-host> <port#> <input-file> <N> <MSS>
```

**Example:**
```bash
python client.py 127.0.0.1 7735 test_1mb.dat 64 500
```

| Argument | Description |
|---|---|
| `server-host` | Hostname or IP of the server |
| `port#` | Server port (use `7735`) |
| `input-file` | File to transfer |
| `N` | Go-Back-N window size |
| `MSS` | Maximum Segment Size in bytes |

**Output on timeout:**
```
Timeout, sequence number = Y
```

**Output on completion:**
```
File transfer completed.
Total transfer delay: XXXX ms
```

---

## Packet Format

### Data Packet Header (8 bytes)

| Field | Size | Value |
|---|---|---|
| `seq_num` | 32-bit | Sequence number (starts at 0) |
| `checksum` | 16-bit | One's complement checksum of full packet |
| `type` | 16-bit | `0x5555` for data packets |

### ACK Packet Header (8 bytes)

| Field | Size | Value |
|---|---|---|
| `seq_num` | 32-bit | Sequence number being ACKed |
| `zero_field` | 16-bit | `0x0000` |
| `type` | 16-bit | `0xAAAA` for ACK packets |

All fields are in **network byte order (big-endian)**.

---

## Local Testing

Open two terminals in the project directory:

**Terminal 1 — Server:**
```bash
python server.py 7735 received.dat 0.05
```

**Terminal 2 — Client:**
```bash
python client.py 127.0.0.1 7735 test_1mb.dat 64 500
```

**Verify file integrity after transfer:**
```powershell
Get-FileHash test_1mb.dat -Algorithm MD5
Get-FileHash received.dat -Algorithm MD5
```

Both MD5 hashes must match.

---

## Extra Credit: Selective Repeat ARQ

The extra-credit implementation is provided in separate files so the original Go-Back-N commands remain unchanged.

### Start the Selective Repeat Server

```bash
python sr_server.py <port#> <output-file> <loss-probability> <N>
```

Example:

```bash
python sr_server.py 7735 sr_received_file.dat 0.05 64
```

The final `N` is the Selective Repeat receiver window size. Use the same `N` as the client during the extra-credit experiments.

### Run the Selective Repeat Client

```bash
python sr_client.py <server-host> <port#> <input-file> <N> <MSS>
```

Example:

```bash
python sr_client.py 127.0.0.1 7735 test_1mb.dat 64 500
```

### Selective Repeat Behavior

- **Sender:** Maintains one timer per unACKed packet. On timeout, it retransmits only that expired packet and prints `Timeout, sequence number = Y`.
- **Receiver:** Accepts and ACKs valid packets inside the receive window, buffers out-of-order packets, writes buffered data once missing earlier packets arrive, and ACKs duplicates for packets already delivered.
- **Loss service:** The SR server uses the same probabilistic packet drop behavior and prints `Packet loss, sequence number = X`.

For the extra-credit report, repeat Tasks 1-3 using `sr_client.py` and `sr_server.py`, then compare the SR curves against the GBN curves.

---

## GBN Protocol Behavior

- **Sender:** Maintains a sliding window of size `N`. Starts a timer when the first unACKed packet is sent. On timeout, retransmits **all** outstanding packets in the window.
- **Receiver:** Only accepts in-order packets. Out-of-order or corrupt packets are **silently discarded** (no duplicate ACK sent). Probabilistically drops packets based on loss parameter `p`.
- **Timeout:** 100ms (hardcoded, suitable for local and campus-network testing).

---

## Experiment Tasks

| Task | Fixed Params | Variable | Range |
|---|---|---|---|
| Task 1: Window Size | MSS=500, p=0.05 | N | 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024 |
| Task 2: MSS | N=64, p=0.05 | MSS | 100 to 1000 (step 100) |
| Task 3: Loss Probability | N=64, MSS=500 | p | 0.01 to 0.10 (step 0.01) |

Each configuration is run **5 times** and the average delay is plotted.
