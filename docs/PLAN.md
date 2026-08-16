# MCU Scope — 单片机数据读取上位机 · 方案

## 目标

一个 Windows 上位机，读取单片机数据，支持 UART / I2C / SPI 三种协议，兼具
**主动收发** 与 **被动监听** 两种工作模式，可查看数据传输质量。

## 选型结论

- 技术栈：Python 3.11 + PySide6 + pyserial + pyqtgraph
- 硬件：STM32F103C8T6（现有）作目标设备；USB-TTL(CH340) 直连 UART；
  进入 M2 后增购第二块 STM32F103C8T6 作桥接器（I2C/SPI master + 被动监听 + 逻辑抓取）
- 波形范围：**数字波形**（0/1 时序、毛刺、协议解码）；模拟信号质量（上升沿/电压/过冲）需示波器，不在本期

## 质量指标

| 指标 | 手段 |
|---|---|
| 协议层错误（CRC/NACK/校验/帧错误） | 桥接固件统计回传（M3） |
| 时序（波特率偏差/间隔抖动/超时） | 桥接硬件定时器 µs 时间戳（M3） |
| 数据完整性（丢包/误码/重传） | 桥接协议帧序号 + CRC16（M3） |
| 实时吞吐与延迟 | 上位机滚动统计 + 时间戳回传（M1 起） |
| 数字波形 | STM32 定时器+DMA 采样 GPIO（M4） |

## 里程碑

- **M0** 计划 + 接线图（本次）
- **M1** UART 直连闭环：上位机 + pyserial，主动收发/被动监听，hex/ASCII/时间戳，吞吐曲线（现有硬件即可验收）
- **M2** STM32 桥接固件：PC↔桥接协议帧，I2C/SPI 主动 + 被动监听 + 时间戳回传
- **M3** 质量指标：协议错误 / 完整性 / 时序 / 延迟直方图
- **M4** 数字波形视图
- **M5** 导出（CSV/日志）、配置持久化、文档

## 目录结构

```
mcu-scope/
├── app/
│   ├── main.py               # 入口（python -m app.main）
│   ├── link/                 # 连接层
│   │   └── serial_link.py    # 串口（M1 直连；M2 起加 bridge_link.py）
│   ├── protocol/             # 帧编解码 / CRC / 协议解析器（M2 起）
│   ├── ui/                   # 主窗口 + 面板
│   │   ├── main_window.py
│   │   ├── connection_panel.py
│   │   ├── data_view.py
│   │   └── quality_panel.py
│   ├── analysis/             # 统计 + 绘图
│   │   └── stats.py
│   └── storage/              # 导出（M5）
├── firmware/                 # STM32 桥接固件（M2 起）
├── docs/                     # PLAN.md / wiring.md / 协议文档
└── requirements.txt
```

## 桥接协议帧（M2 设计稿）

```
[SOF AA 55][CMD 1B][SEQ 2B][LEN 2B][PAYLOAD ...][CRC16 2B]
```

命令集：握手/版本、UART 读写监听、I2C 扫描/读写/监听、SPI 配置/传输/监听、
逻辑抓取配置/启动/上传、错误与时间戳事件回传。桥接用 72MHz 定时器打 µs 时间戳。
