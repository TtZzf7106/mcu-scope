"""SPI 逻辑采样解码：从 SCK/MOSI/MISO 波形还原字节（被动监听 + 协议解码）。

算法：按 SPI 模式（CPOL/CPHA）找采样边沿，每 8 个边沿组成一个字节（MSB first）。
"""
from __future__ import annotations

from .logic_capture import LogicCapture


def _samples(cap: LogicCapture, ch: int) -> list[int]:
    return [row[ch] for row in cap.samples]


def decode_spi(cap: LogicCapture, sck_ch: int, mosi_ch: int, miso_ch: int,
               mode: int = 0) -> tuple[list[int], list[int]]:
    """返回 (mosi_bytes, miso_bytes)。mode 0..3 = CPOL | (CPHA<<1)。"""
    sck = _samples(cap, sck_ch)
    mosi = _samples(cap, mosi_ch)
    miso = _samples(cap, miso_ch)
    n = len(sck)

    cpol = (mode >> 1) & 1
    cpha = mode & 1

    # 采样边沿：CPHA=0 → 第 1 个边沿；CPHA=1 → 第 2 个边沿
    rising = [i for i in range(1, n) if sck[i - 1] == 0 and sck[i] == 1]
    falling = [i for i in range(1, n) if sck[i - 1] == 1 and sck[i] == 0]
    if cpha == 0:
        edges = rising if cpol == 0 else falling
    else:
        edges = falling if cpol == 0 else rising

    mosi_bytes: list[int] = []
    miso_bytes: list[int] = []
    for k in range(0, len(edges) - 7, 8):
        mo = 0
        mi = 0
        for b in range(8):
            e = edges[k + b]
            mo = (mo << 1) | mosi[e]
            mi = (mi << 1) | miso[e]
        mosi_bytes.append(mo)
        miso_bytes.append(mi)
    return mosi_bytes, miso_bytes
