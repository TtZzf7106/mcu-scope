"""M1 目标端串口验收：读 ping 上报 + 发送回环测试。

运行：.\.venv\Scripts\python.exe scripts\test_m1_serial.py [COM口]
"""
from __future__ import annotations

import sys
import time

import serial


def main() -> int:
    port = sys.argv[1] if len(sys.argv) > 1 else "COM8"
    ser = serial.Serial(port, 115200, timeout=1.0)

    # 1. 读 1.5 秒，应看到 "ping N"
    ser.reset_input_buffer()
    time.sleep(1.5)
    n = ser.in_waiting
    pings = ser.read(n)
    print(f"[读 {n} 字节] {pings!r}")
    assert b"ping " in pings, "未收到 ping 上报"

    # 2. 回环测试
    ser.write(b"hello mcu-scope\r\n")
    time.sleep(0.3)
    echo = ser.read(ser.in_waiting)
    print(f"[回环 {len(echo)} 字节] {echo!r}")
    assert b"hello mcu-scope" in echo, "未收到回环数据"

    ser.close()
    print("\nM1 串口验收通过 [OK]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
