# 接线图

> TTL 电平 3.3V。目标板若为 5V 逻辑，务必确认 IO 耐受 5V，否则用 3.3V 供电/电平转换。

## M1 · UART 直连（现有硬件：USB-TTL + 目标 STM32F103）

### 方式 A：主动收发 / 终端模式（双向）

```
PC ── USB-TTL(CH340) ── 目标 STM32F103C8T6
      TX  ─────────────►  PA10 (USART1_RX)
      RX  ◄─────────────  PA9  (USART1_TX)
      GND ──────────────  GND
```

- 上位机发送 → CH340 TX → 目标 RX；目标回复 → 目标 TX → CH340 RX → 上位机。
- 目标 STM32 需烧入「串口回环/应答」固件（M1 验收用最小固件见 firmware/README.md）。

### 方式 B：被动监听 / 抓取（单向）

```
PC ── USB-TTL(CH340) ── 目标总线
      RX  ◄─────────────  要观察的那根数据线（如目标 TX）
      GND ──────────────  共地 GND
```

- 单块 CH340 一次只能监听一个方向；双向同时抓取需两块 USB-TTL 或进入 M2 用桥接器。
- 波特率/校验/停止位必须与被观察总线一致。

## M2+ · STM32 桥接（增购第二块 STM32F103C8T6）

```
PC ── USB-TTL(CH340) ── 桥接 STM32F103 ── 目标总线
      TX/RX ◄───────►  PA9/PA10 (USART1)   I2C: PB6(SCL) PB7(SDA) + 4.7kΩ 上拉到 3.3V
                                            SPI: PA5(SCK) PA6(MISO) PA7(MOSI) + CS
                                            UART: PA2/PA3 (USART2) 或 PA9/PA10 复用
```

- 桥接 STM32 的 I2C 外设接目标 SCL/SDA，SPI 接目标 SCK/MISO/MOSI/CS，UART 接目标 TX/RX。
- 逻辑抓取用空闲 GPIO 采样（M4 设计定引脚）。
