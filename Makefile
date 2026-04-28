CC = gcc
CFLAGS = -Wall -Wextra -O2

# Detect OS to link Winsock if on Windows
ifeq ($(OS),Windows_NT)
	LDFLAGS = -lws2_32
	EXE_EXT = .exe
else
	LDFLAGS =
	EXE_EXT =
endif

all: Simple_ftp_client$(EXE_EXT) Simple_ftp_server$(EXE_EXT)

Simple_ftp_client$(EXE_EXT): client.c common.c common.h
	$(CC) $(CFLAGS) -o $@ client.c common.c $(LDFLAGS)

Simple_ftp_server$(EXE_EXT): server.c common.c common.h
	$(CC) $(CFLAGS) -o $@ server.c common.c $(LDFLAGS)

clean:
	rm -f Simple_ftp_client$(EXE_EXT) Simple_ftp_server$(EXE_EXT) *.o
