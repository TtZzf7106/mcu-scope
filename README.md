# MCU Scope — 单片机数据读取上位机

读取单片机数据的 Windows 上位机：UART / I2C / SPI，主动收发 + 被动监听，数据传输质量分析。

## 安装

```powershell
cd F:\工作\AI_Project\mcu-scope
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 运行

```powershell
.\.venv\Scripts\python.exe -m app.main
```

## 里程碑状态

- [x] M0 计划 + 接线图
- [x] M1 UART 直连闭环
- [ ] M2 STM32 桥接固件（I2C/SPI）—— 宿主侧协议/桥接层已就绪，固件待硬件
- [~] M3 质量指标 —— 宿主侧指标面板 + 统计已就绪，待桥接回传数据填充
- [~] M4 数字波形 —— 波形视图 + 示例渲染已就绪（scripts/render_wave.py 可预览），待桥接回传真实采样
- [~] M5 导出/文档 —— 导出菜单 + CSV/日志已就绪

## 自测

```powershell
.\.venv\Scripts\python.exe scripts\selftest_protocol.py   # 协议层（帧/CRC）
.\.venv\Scripts\python.exe scripts\selftest_payloads.py   # payload 编解码
.\.venv\Scripts\python.exe scripts\selftest_decode.py     # UART 解码
.\.venv\Scripts\python.exe scripts\selftest_i2c_spi.py   # I2C/SPI 解码
.\.venv\Scripts\python.exe scripts\selftest_bridge.py     # 桥接会话端到端
.\.venv\Scripts\python.exe scripts\smoke_ui.py            # UI 离屏冒烟
```

硬件实机测试（需接好 ST-Link + CH340 + 板子）：

```powershell
.\.venv\Scripts\python.exe scripts\test_m1_serial.py COM8   # M1 目标回环/上报
.\.venv\Scripts\python.exe scripts\test_bridge_hw.py COM8   # 桥接协议栈端到端
.\.venv\Scripts\python.exe scripts\test_bridge_gui.py COM8  # 桥接 GUI 功能
```

固件协议核心/调度器（纯 C）自测见 `firmware/tests/`（gcc 编译 + 与上位机交叉验证）。

详见 [docs/PLAN.md](docs/PLAN.md)、[docs/wiring.md](docs/wiring.md)、[docs/protocol.md](docs/protocol.md)。
