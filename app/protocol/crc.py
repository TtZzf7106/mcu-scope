"""CRC16-MODBUS。

poly=0x8005（反射 0xA001），init=0xFFFF，xorout=0x0000，refin/refout=true。
与 STM32 侧位运算实现逐字节等价，保证跨端一致性。
"""
from __future__ import annotations

_TABLE: list[int] = []


def _make_table() -> list[int]:
    table: list[int] = []
    for i in range(256):
        crc = i
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
        table.append(crc)
    return table


def crc16_modbus(data: bytes | bytearray | memoryview, seed: int = 0xFFFF) -> int:
    table = _TABLE
    crc = seed
    for b in data:
        crc = (crc >> 8) ^ table[(crc ^ b) & 0xFF]
    return crc & 0xFFFF


# 表在模块加载末尾填充，函数运行时已就绪
_TABLE = _make_table()
