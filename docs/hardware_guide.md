# 硬件接线指南（桥接板 → 设备）

> 前提：桥接板已烧入 `bridge_reg/firmware.hex`，CH340 接 USART1(PA9/PA10)，ST-Link 烧录。

## 引脚速查

| 总线 | 桥接板引脚 | 方向 | 接设备 |
|---|---|---|---|
| I2C1 | **PB6** | SCL | 设备 SCL |
| | **PB7** | SDA | 设备 SDA |
| SPI1 | **PA5** | SCK | 设备 SCK/CLK |
| | **PA6** | MISO | 设备 MISO/DO |
| | **PA7** | MOSI | 设备 MOSI/DI |
| | **PA4** | CS | 设备 CS/SS |
| 电源 | 3.3V | — | 设备 VCC |
| | GND | — | 设备 GND |

> ST-Link(PA13/PA14)、串口(PA9/PA10) 均不冲突，可同时接。

## I2C 上拉（关键）

SCL/SDA 是开漏，各需 4.7kΩ 上拉到 3.3V（模块板载上拉则免）：

```
3.3V ──┬──[4.7kΩ]──┬── 设备 SCL
       │           └── PB6
       └──[4.7kΩ]──┬── 设备 SDA
                   └── PB7
```

## 常见设备地址

| 设备 | I2C 地址 | ID 寄存器 |
|---|---|---|
| AT24C02 EEPROM | 0x50 | 无 |
| MPU6050 | 0x68 | 0x75 = 0x68 |
| BMP280 | 0x76 | 0xD0 = 0x58 |
| SSD1306 OLED | 0x3C | 无 |
| HMC5883L | 0x1E | 0x0A = 0x48 |
| LIS3DH | 0x18 | 0x0F = 0x33 |

## 验证步骤

1. 接好设备（含上拉、共地、供电）；
2. 运行识别脚本：
   ```powershell
   .\.venv\Scripts\python.exe scripts\test_i2c_device.py COM8
   ```
   应显示扫描到的地址 + 自动识别的型号；
3. 或打开 GUI（`python -m app.main`）→ 桥接页 → 「扫描地址」。

## SPI 接线提示

SPI 4 线：SCK、MOSI、MISO、CS 都要接，共地。注意 CS 用 PA4，且 SPI 速率固定
500kHz（`bridge_hal_reg.c` 里可改）。
