"""I2C / SPI 解码自测（合成波形）。

运行：.\.venv\Scripts\python.exe scripts\selftest_i2c_spi.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.analysis.logic_capture import LogicCapture  # noqa: E402
from app.analysis.i2c_decode import decode_i2c  # noqa: E402
from app.analysis.spi_decode import decode_spi  # noqa: E402


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        raise SystemExit(1)


def build_i2c_write(addr7: int, data: list[int], oversample: int = 4) -> LogicCapture:
    scl = [1] * oversample
    sda = [1] * oversample

    def h(s, d, n):
        scl.extend([s] * n)
        sda.extend([d] * n)

    h(1, 1, oversample)          # 空闲
    h(1, 0, oversample)          # START: SDA 1→0 而 SCL 高

    def bit(b):
        h(0, b, oversample)      # SCL 低，设 SDA
        h(1, b, oversample)      # SCL 高，采样

    def byte(v):
        for i in range(8):
            bit((v >> (7 - i)) & 1)

    byte((addr7 << 1) | 0)       # 地址 + W
    bit(0)                       # ACK
    for d in data:
        byte(d)
        bit(0)                   # ACK
    h(1, 1, oversample)          # STOP: SDA 0→1 而 SCL 高
    h(1, 1, oversample)          # 空闲

    cap = LogicCapture(["SCL", "SDA"], 1e-6)
    for i in range(len(scl)):
        cap.add([scl[i], sda[i]])
    return cap


def build_spi(mosi_bytes: list[int], miso_bytes: list[int],
              oversample: int = 4) -> LogicCapture:
    sck = [0] * oversample
    mosi = [0] * oversample
    miso = [0] * oversample

    def h(s, mo, mi, n):
        sck.extend([s] * n)
        mosi.extend([mo] * n)
        miso.extend([mi] * n)

    for mo_byte, mi_byte in zip(mosi_bytes, miso_bytes):
        for b in range(8):
            mo = (mo_byte >> (7 - b)) & 1
            mi = (mi_byte >> (7 - b)) & 1
            h(0, mo, mi, oversample)   # SCK 低
            h(1, mo, mi, oversample)   # SCK 高（采样）

    cap = LogicCapture(["SCK", "MOSI", "MISO"], 1e-6)
    for i in range(len(sck)):
        cap.add([sck[i], mosi[i], miso[i]])
    return cap


def main() -> None:
    # 1. I2C 写事务：地址 0x50，数据 [0x01, 0x02]
    cap = build_i2c_write(0x50, [0x01, 0x02])
    trs = decode_i2c(cap, 0, 1)
    check("I2C 解出 1 个事务", len(trs) == 1, f"n={len(trs)}")
    t = trs[0]
    check("I2C 地址=0x50 写", t.addr7 == 0x50 and not t.is_read and t.addr_ack,
          f"addr=0x{t.addr7:02X} read={t.is_read}")
    check("I2C 数据字节", [b.value for b in t.data] == [0x01, 0x02]
          and all(b.ack for b in t.data),
          f"data={[hex(b.value) for b in t.data]}")

    # 2. SPI 传输（mode 0）：MOSI [0x41,0x42]，MISO [0xAB,0xCD]
    cap = build_spi([0x41, 0x42], [0xAB, 0xCD])
    mo, mi = decode_spi(cap, 0, 1, 2, mode=0)
    check("SPI MOSI 解码", mo == [0x41, 0x42], f"mosi={[hex(b) for b in mo]}")
    check("SPI MISO 解码", mi == [0xAB, 0xCD], f"miso={[hex(b) for b in mi]}")

    print("\nI2C/SPI 解码自测全部通过 [OK]")


if __name__ == "__main__":
    main()
