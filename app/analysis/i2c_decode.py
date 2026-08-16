"""I2C 逻辑采样解码：从 SCL/SDA 波形还原事务（被动监听 + 协议解码）。

算法：找 SCL 上升沿逐位采样 SDA；START=SCL 高时 SDA 下降，STOP=SCL 高时 SDA 上升；
每 9 位一组（8 数据位 MSB-first + 1 ACK 位）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .logic_capture import LogicCapture


@dataclass
class I2cByte:
    value: int
    ack: bool   # True=ACK（SDA 低）


@dataclass
class I2cTransfer:
    addr7: int
    is_read: bool
    addr_ack: bool
    data: list = field(default_factory=list)  # list[I2cByte]


def _samples(cap: LogicCapture, ch: int) -> list[int]:
    return [row[ch] for row in cap.samples]


def decode_i2c(cap: LogicCapture, scl_ch: int, sda_ch: int) -> list[I2cTransfer]:
    scl = _samples(cap, scl_ch)
    sda = _samples(cap, sda_ch)
    n = len(scl)

    rise = [i for i in range(1, n) if scl[i - 1] == 0 and scl[i] == 1]

    # START / STOP 事件（SDA 变化时 SCL 为高）
    events: list[tuple[int, str]] = []
    for i in range(1, n):
        if scl[i] == 1:
            if sda[i - 1] == 1 and sda[i] == 0:
                events.append((i, "START"))
            elif sda[i - 1] == 0 and sda[i] == 1:
                events.append((i, "STOP"))

    transfers: list[I2cTransfer] = []
    i = 0
    while i < len(events):
        if events[i][1] != "START":
            i += 1
            continue
        start_idx = events[i][0]
        j = i + 1
        while j < len(events) and events[j][1] != "STOP":
            j += 1
        if j >= len(events):
            break
        stop_idx = events[j][0]

        bits = [sda[e] for e in rise if start_idx < e < stop_idx]
        if len(bits) < 9:
            i = j + 1
            continue

        # 地址字节（MSB first）：bit7..bit1 = 地址，bit0 = R/W
        addr_byte = 0
        for b in range(8):
            addr_byte = (addr_byte << 1) | bits[b]
        addr7 = addr_byte >> 1
        is_read = (addr_byte & 1) == 1
        addr_ack = bits[8] == 0

        data: list[I2cByte] = []
        k = 9
        while k + 9 <= len(bits):
            val = 0
            for b in range(8):
                val = (val << 1) | bits[k + b]
            data.append(I2cByte(val, bits[k + 8] == 0))
            k += 9

        transfers.append(I2cTransfer(addr7, is_read, addr_ack, data))
        i = j + 1

    return transfers
