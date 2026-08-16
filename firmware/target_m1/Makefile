# M1 目标端回环固件构建
# 工具链二选一（默认用 CubeIDE 自带，无空格路径最稳）：
TC_BIN ?= B:/stm32cube/cubeide/STM32CubeIDE_1.14.0/STM32CubeIDE/plugins/com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.11.3.rel1.win32_1.1.100.202309141235/tools/bin
# TC_BIN ?= "C:/Program Files (x86)/Arm GNU Toolchain arm-none-eabi/14.2 rel1/bin"

PREFIX = $(TC_BIN)/arm-none-eabi-

CC      = $(PREFIX)gcc
OBJCOPY = $(PREFIX)objcopy
SIZE    = $(PREFIX)size

CFLAGS  = -mcpu=cortex-m3 -mthumb -O2 -g -Wall -Wextra -ffunction-sections -fdata-sections
LDFLAGS = -mcpu=cortex-m3 -mthumb -T stm32f103c8.ld -Wl,--gc-sections -nostartfiles

all: firmware.elf firmware.bin firmware.hex

startup.o: startup_stm32f103c8.s
	$(CC) -mcpu=cortex-m3 -mthumb -c -o $@ $<

main.o: main.c
	$(CC) $(CFLAGS) -c -o $@ $<

firmware.elf: startup.o main.o
	$(CC) $(LDFLAGS) -o $@ $^
	$(SIZE) $@

firmware.bin: firmware.elf
	$(OBJCOPY) -O binary $< $@

firmware.hex: firmware.elf
	$(OBJCOPY) -O ihex $< $@

clean:
	rm -f *.o *.elf *.bin *.hex
