"""桥接协议 payload 编解码（各 CMD 的 PAYLOAD 部分）。

多字节字段一律小端，与帧层一致。布局规范见 docs/protocol.md。
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

# ---- 通道 ----
CH_UART = 0
CH_I2C = 1
CH_SPI = 2
CH_LOGIC = 3

# ---- 方向 ----
DIR_RX = 0
DIR_TX = 1

# ---- 应答状态 ----
STATUS_OK = 0
STATUS_ERR = 1

# ---- 错误码 ----
ERR_UNKNOWN_CMD = 0
ERR_BAD_PARAM = 1
ERR_BUS = 2          # 总线错误（如 I2C NACK）
ERR_TIMEOUT = 3
ERR_OVERFLOW = 4

# ---- UART 校验 ----
PARITY_NONE = 0
PARITY_EVEN = 1
PARITY_ODD = 2


@dataclass
class Event:
    """桥→PC 异步数据/状态事件：带 µs 时间戳。"""

    channel: int
    direction: int
    ts_us: int
    data: bytes

    def pack(self) -> bytes:
        return struct.pack("<BBI", self.channel, self.direction, self.ts_us) + self.data

    @staticmethod
    def unpack(b: bytes) -> "Event":
        if len(b) < 6:
            raise ValueError("EVENT payload 过短")
        ch, d, ts = struct.unpack_from("<BBI", b, 0)
        return Event(ch, d, ts, b[6:])


@dataclass
class Ack:
    """桥→PC 命令应答。req_seq 回传被应答请求的序号，供延迟相关。"""

    ack_cmd: int
    status: int
    req_seq: int = 0
    data: bytes = b""

    def pack(self) -> bytes:
        return struct.pack("<BBH", self.ack_cmd, self.status, self.req_seq) + self.data

    @staticmethod
    def unpack(b: bytes) -> "Ack":
        if len(b) < 4:
            raise ValueError("ACK payload 过短")
        cmd, st, rs = struct.unpack_from("<BBH", b, 0)
        return Ack(cmd, st, rs, b[4:])


@dataclass
class Error:
    """桥→PC 错误上报。"""

    code: int
    data: bytes = b""

    def pack(self) -> bytes:
        return struct.pack("<B", self.code) + self.data

    @staticmethod
    def unpack(b: bytes) -> "Error":
        if len(b) < 1:
            raise ValueError("ERROR payload 过短")
        return Error(b[0], b[1:])


@dataclass
class UartCfg:
    """PC→桥 配置目标 UART。"""

    baud: int
    data_bits: int = 8
    parity: int = PARITY_NONE
    stop_bits: int = 1

    def pack(self) -> bytes:
        return struct.pack("<IBBB", self.baud, self.data_bits, self.parity, self.stop_bits)

    @staticmethod
    def unpack(b: bytes) -> "UartCfg":
        if len(b) < 7:
            raise ValueError("UART_CFG payload 过短")
        baud, db, p, sb = struct.unpack_from("<IBBB", b, 0)
        return UartCfg(baud, db, p, sb)


@dataclass
class I2cWrite:
    addr7: int
    data: bytes

    def pack(self) -> bytes:
        return struct.pack("<B", self.addr7) + self.data

    @staticmethod
    def unpack(b: bytes) -> "I2cWrite":
        if len(b) < 1:
            raise ValueError("I2C_WRITE payload 过短")
        return I2cWrite(b[0], b[1:])


@dataclass
class I2cRead:
    addr7: int
    length: int

    def pack(self) -> bytes:
        return struct.pack("<BH", self.addr7, self.length)

    @staticmethod
    def unpack(b: bytes) -> "I2cRead":
        if len(b) < 3:
            raise ValueError("I2C_READ payload 过短")
        a, l = struct.unpack_from("<BH", b, 0)
        return I2cRead(a, l)


@dataclass
class SpiCfg:
    speed_hz: int
    mode: int = 0       # 0..3 = CPOL | (CPHA<<1)
    bit_order: int = 0  # 0=MSB first, 1=LSB first

    def pack(self) -> bytes:
        return struct.pack("<IBB", self.speed_hz, self.mode, self.bit_order)

    @staticmethod
    def unpack(b: bytes) -> "SpiCfg":
        if len(b) < 6:
            raise ValueError("SPI_CFG payload 过短")
        s, m, o = struct.unpack_from("<IBB", b, 0)
        return SpiCfg(s, m, o)


@dataclass
class SpiTransfer:
    cs_pin: int
    data: bytes

    def pack(self) -> bytes:
        return struct.pack("<B", self.cs_pin) + self.data

    @staticmethod
    def unpack(b: bytes) -> "SpiTransfer":
        if len(b) < 1:
            raise ValueError("SPI_TRANSFER payload 过短")
        return SpiTransfer(b[0], b[1:])


@dataclass
class LogicCfg:
    sample_rate_hz: int
    channel_mask: int
    trigger_ch: int = 0
    trigger_edge: int = 0  # 0=下降沿, 1=上升沿

    def pack(self) -> bytes:
        return struct.pack(
            "<IBBB", self.sample_rate_hz, self.channel_mask, self.trigger_ch, self.trigger_edge
        )

    @staticmethod
    def unpack(b: bytes) -> "LogicCfg":
        if len(b) < 7:
            raise ValueError("LOGIC_CFG payload 过短")
        s, m, c, e = struct.unpack_from("<IBBB", b, 0)
        return LogicCfg(s, m, c, e)


@dataclass
class LogicData:
    """桥→PC 逻辑采样数据块。samples 每字节 = 各通道电平位图（bit i = 通道 i）。"""

    block_seq: int
    samples: bytes

    def pack(self) -> bytes:
        return struct.pack("<HH", self.block_seq, len(self.samples)) + self.samples

    @staticmethod
    def unpack(b: bytes) -> "LogicData":
        if len(b) < 4:
            raise ValueError("LOGIC_DATA payload 过短")
        seq, n = struct.unpack_from("<HH", b, 0)
        if len(b) < 4 + n:
            raise ValueError("LOGIC_DATA 数据不足")
        return LogicData(seq, b[4 : 4 + n])
