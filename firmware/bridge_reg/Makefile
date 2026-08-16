# 桥接固件（寄存器级）构建
# 复用 ../target_m1 的 startup/linker，链接 ../bridge 的协议/调度器。
TC_BIN ?= B:/stm32cube/cubeide/STM32CubeIDE_1.14.0/STM32CubeIDE/plugins/com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.11.3.rel1.win32_1.1.100.202309141235/tools/bin

PREFIX = $(TC_BIN)/arm-none-eabi-
CC      = $(PREFIX)gcc
OBJCOPY = $(PREFIX)objcopy
SIZE    = $(PREFIX)size

BRIDGE  = ../bridge
CFLAGS  = -mcpu=cortex-m3 -mthumb -O2 -g -Wall -Wextra -ffunction-sections -fdata-sections -I$(BRIDGE)
LDFLAGS = -mcpu=cortex-m3 -mthumb -T ../target_m1/stm32f103c8.ld -Wl,--gc-sections -nostartfiles

OBJS = startup.o main_bridge.o bridge_hal_reg.o bridge_app.o bridge_protocol.o bridge_payloads.o

all: firmware.elf firmware.bin firmware.hex

startup.o: ../target_m1/startup_stm32f103c8.s
	$(CC) -mcpu=cortex-m3 -mthumb -c -o $@ $<

main_bridge.o: main_bridge.c
	$(CC) $(CFLAGS) -c -o $@ $<

bridge_hal_reg.o: bridge_hal_reg.c
	$(CC) $(CFLAGS) -c -o $@ $<

bridge_app.o: $(BRIDGE)/bridge_app.c
	$(CC) $(CFLAGS) -c -o $@ $<

bridge_protocol.o: $(BRIDGE)/bridge_protocol.c
	$(CC) $(CFLAGS) -c -o $@ $<

bridge_payloads.o: $(BRIDGE)/bridge_payloads.c
	$(CC) $(CFLAGS) -c -o $@ $<

firmware.elf: $(OBJS)
	$(CC) $(LDFLAGS) -o $@ $^
	$(SIZE) $@

firmware.bin: firmware.elf
	$(OBJCOPY) -O binary $< $@

firmware.hex: firmware.elf
	$(OBJCOPY) -O ihex $< $@

clean:
	rm -f *.o *.elf *.bin *.hex
