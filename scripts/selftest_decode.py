"""UART 解码自测。

运行：.\.venv\Scripts\python.exe scripts\selftest_decode.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.analysis.logic_capture import LogicCapture, demo_uart  # noqa: E402
from app.analysis.uart_decode import decode_uart  # noqa: E402


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        raise SystemExit(1)


def build_uart_bytes(values: list[int], baud: int = 115200, oversample: int = 16,
                     idle_bits: int = 3) -> LogicCapture:
    """构造单通道 UART 采样：每个字节 start + 8 数据位(LSB) + stop，字节间留空闲。"""
    dt = 1.0 / (baud * oversample)
    samples: list[int] = []
    for v in values:
        bits = [0] + [(v >> i) & 1 for i in range(8)] + [1]
        for bit in bits:
            samples.extend([bit] * oversample)
        samples.extend([1] * (idle_bits * oversample))  # 空闲高电平
    cap = LogicCapture(["UART"], dt)
    for s in samples:
        cap.add([s])
    return cap


def main() -> None:
    # 1. 解码 demo 'A' (0x41)
    res = decode_uart(demo_uart(), 0, 115200)
    check("demo 解码 'A'", len(res) == 1 and res[0].value == 0x41 and not res[0].framing_error,
          f"got {[hex(b.value) for b in res]}")

    # 2. 多字节连续（含空闲间隙）
    res = decode_uart(build_uart_bytes([0x41, 0x42, 0x0D]), 0, 115200)
    check("多字节 'AB\\r'", [b.value for b in res] == [0x41, 0x42, 0x0D] and all(not b.framing_error for b in res),
          f"got {[hex(b.value) for b in res]}")

    # 3. 帧错误检测：破坏停止位中点采样（解码器在 start+9.5*spb=152 处采样）
    cap = build_uart_bytes([0x55])
    cap.samples[152] = [0]  # 停止位中点改 0 → 帧错误
    res = decode_uart(cap, 0, 115200)
    check("帧错误检测", len(res) == 1 and res[0].value == 0x55 and res[0].framing_error,
          f"framing={res[0].framing_error if res else None}")

    # 4. 采样率不足报错
    try:
        decode_uart(LogicCapture(["x"], 0.001), 0, 115200)
        check("采样率不足报错", False, "未抛异常")
    except ValueError:
        check("采样率不足报错", True)

    print("\nUART 解码自测全部通过 [OK]")


if __name__ == "__main__":
    main()
