"""桥接协议命令表。"""

from __future__ import annotations


class Cmd:
    """PC↔桥接 命令/事件 ID。"""

    # 握手
    PING = 0x01          # PC→桥：握手请求；桥→PC：ACK + 版本信息

    # UART（目标总线）
    UART_CFG = 0x10      # 配置目标 UART（波特率/校验/停止位）
    UART_WRITE = 0x11    # 主动写目标 UART
    UART_LISTEN = 0x13   # 开始/停止被动监听目标 UART

    # I2C（目标总线）
    I2C_SCAN = 0x20      # 扫描 7-bit 地址
    I2C_WRITE = 0x21     # 主动写
    I2C_READ = 0x22      # 主动读
    I2C_LISTEN = 0x23    # 被动监听

    # SPI（目标总线）
    SPI_CFG = 0x30       # 配置模式/速率/CPOL/CPHA
    SPI_TRANSFER = 0x31  # 全双工传输
    SPI_LISTEN = 0x32    # 被动监听

    # 逻辑抓取（数字波形）
    LOGIC_CFG = 0x40     # 采样率/通道/触发
    LOGIC_START = 0x41   # 开始抓取
    LOGIC_DATA = 0x42    # 桥→PC：采样数据块
    LOGIC_STOP = 0x43    # 停止抓取

    # 通用事件 / 应答
    EVENT = 0xF0         # 桥→PC：异步数据/状态事件（带 µs 时间戳）
    ERROR = 0xF1         # 桥→PC：错误上报
    ACK = 0xF2           # 桥→PC：命令应答


# 便于反查日志
_NAMES = {v: k for k, v in Cmd.__dict__.items() if k.isupper()}


def cmd_name(cmd: int) -> str:
    return _NAMES.get(cmd, f"0x{cmd:02X}")
