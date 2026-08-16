# firmware — 固件

## 状态

- **target_m1/**：M1 目标端回环固件（寄存器级，无 HAL）——**已编译并实机烧录验证**（HSI 8MHz，回环 + ping 上报 + LED 心跳）。
- **bridge/**：M2 桥接协议/调度器（纯 C，宿主机单测通过）+ `stm32/bridge_hal_stm32.c`（HAL 实现，待编译）。
- **bridge_reg/**：M2 桥接固件（**寄存器级，已编译** `firmware.hex`，3160 字节）——复用 bridge/ 的协议与调度器，USART1/2 + SPI1 + I2C1 + DWT 时间戳，待第二块板子烧录。

## target_m1 构建与烧录

工具链：STM32CubeIDE 自带 arm-none-eabi-gcc（见 Makefile 的 `TC_BIN`）。

```powershell
cd firmware\target_m1
mingw32-make          # 产出 firmware.hex
# 烧录（ST-LINK Utility）
& 'B:\stm32cube\ST-LINK Utility\ST-LINK_CLI.exe' -c SWD -P firmware.hex -V -Rst
```

验收：`..\..\.venv\Scripts\python.exe ..\..\scripts\test_m1_serial.py COM8`
（应看到 `ping N` 上报 + 发送即回显）。

> 注：板子若无可用 8MHz HSE 晶振，固件用 HSI 8MHz（波特率 115200 误差 0.6%，
> 回环足够）；若要精确波特率，确认晶振后改回 HSE+PLL 72MHz。



## M2 · 桥接协议核心（已实现，可宿主机验证）

`bridge/` 下是**与 HAL 无关的协议核心**，纯 C，已在本机用 gcc 编译单测，
并与上位机 `app/protocol/` 逐字节交叉验证通过：

```
firmware/
├── bridge/
│   ├── bridge_protocol.h/.c   # 帧格式/命令表/CRC16 + 组帧 + 流式解析
│   ├── bridge_payloads.h/.c   # payload 编解码（EVENT/UART_CFG/ACK...）
│   ├── bridge_hal.h           # 外设抽象接口（调度器只依赖此接口）
│   ├── bridge_app.h/.c        # 命令分发调度器
│   └── stm32/
│       └── bridge_hal_stm32.c # STM32F103 HAL 实现（板子端，待编译）
└── tests/
    ├── test_protocol_host.c   # 协议核心单测
    ├── test_bridge_app.c      # 调度器单测
    └── bridge_hal_mock.c      # 宿主机 mock 外设
```

### 宿主机编译与测试

```powershell
cd firmware\tests
# 协议核心单测
gcc -std=c11 -Wall -Wextra -O2 -I ..\bridge -o test_protocol_host.exe `
    test_protocol_host.c ..\bridge\bridge_protocol.c ..\bridge\bridge_payloads.c
.\test_protocol_host.exe

# 调度器单测（mock 外设）
gcc -std=c11 -Wall -Wextra -O2 -I ..\bridge -o test_bridge_app.exe `
    test_bridge_app.c bridge_hal_mock.c ..\bridge\bridge_app.c `
    ..\bridge\bridge_protocol.c ..\bridge\bridge_payloads.c
.\test_bridge_app.exe
```

或 `mingw32-make`（若已装 GNU Make）。

### 与上位机交叉验证

C 单测打印 `FRAME_HEX`，与 Python 端同帧 `Frame(cmd=0x21, seq=7, payload=bytes(range(16))).encode().hex().upper()`
逐字节一致（`AA55...97CD`），证明线级兼容。

## M2 · 桥接应用层（调度器已实现并验证，HAL 待板子）

`bridge_app.c` 的命令分发、ACK/EVENT/ERROR 生成、参数校验已用 mock 外设在
宿主机验证（`test_bridge_app.c`）。板子端 `stm32/bridge_hal_stm32.c` 已按
STM32F103 HAL 写好，待硬件到位后用 STM32CubeMX 生成工程（USART1 接 PC、
USART2 接目标 UART、I2C1(PB6/PB7)、SPI1(PA5/PA6/PA7)），把 `bridge/` 加入
编译，在 main 循环调 `br_app_init()` + `br_app_on_pc_bytes()` + `br_app_poll()`。
集成步骤见 `stm32/bridge_hal_stm32.c` 头部注释。
