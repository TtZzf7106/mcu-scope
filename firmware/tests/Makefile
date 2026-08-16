CC ?= gcc
CFLAGS = -std=c11 -Wall -Wextra -O2 -I../bridge

BRIDGE_SRC = ../bridge/bridge_protocol.c ../bridge/bridge_payloads.c

all: test_protocol_host.exe test_bridge_app.exe

test_protocol_host.exe: test_protocol_host.c $(BRIDGE_SRC)
	$(CC) $(CFLAGS) -o $@ $^

test_bridge_app.exe: test_bridge_app.c bridge_hal_mock.c ../bridge/bridge_app.c $(BRIDGE_SRC)
	$(CC) $(CFLAGS) -o $@ $^

.PHONY: clean
clean:
	rm -f test_protocol_host.exe test_bridge_app.exe
