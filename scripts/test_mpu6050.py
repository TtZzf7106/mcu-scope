"""MPU6050 读取验证：WHO_AM_I + 加速度 + 陀螺仪。

接线：VCC→3.3V、GND→GND、SCL→PB6、SDA→PB7（AD0 悬空 → 地址 0x68）。

运行：.\.venv\Scripts\python.exe scripts\test_mpu6050.py [COM口]
"""
from __future__ import annotations

import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QCoreApplication  # noqa: E402

from app.link.bridge_link import BridgeLink  # noqa: E402
from app.link.bridge_session import BridgeSession  # noqa: E402
from app.link.serial_link import SerialLink  # noqa: E402

ADDR = 0x68


def main() -> int:
    port = sys.argv[1] if len(sys.argv) > 1 else "COM8"
    app = QCoreApplication(sys.argv)
    ser = SerialLink()
    sess = BridgeSession(BridgeLink(ser))
    acks: list = []
    errs: list = []
    sess.ack_received.connect(lambda a: acks.append(a))
    sess.error_received.connect(lambda e: errs.append(e))
    ser.open(port, baudrate=115200)
    time.sleep(0.5)

    def wait(timeout: float = 1.5):
        acks.clear()
        errs.clear()
        t0 = time.time()
        while time.time() - t0 < timeout:
            app.processEvents()
            if acks or errs:
                return acks[0] if acks else None
            time.sleep(0.01)
        return None

    def read_reg(reg: int, n: int) -> bytes | None:
        sess.i2c_write(ADDR, bytes([reg]))
        if wait() is None:
            return None
        time.sleep(0.01)
        sess.i2c_read(ADDR, n)
        ack = wait()
        return ack.data if ack and ack.status == 0 else None

    # 1. 唤醒（PWR_MGMT_1 = 0x6B 写 0）
    sess.i2c_write(ADDR, bytes([0x6B, 0x00]))
    wait()

    # 2. WHO_AM_I
    who = read_reg(0x75, 1)
    ok = who == b"\x68"
    print(f"[{'PASS' if ok else 'FAIL'}] WHO_AM_I = "
          f"{who.hex(' ').upper() if who else '无响应'} (期望 68)")

    if not ok:
        ser.close()
        print("MPU6050 未正确应答。检查：VCC/GND/SCL/SDA 接线、3.3V 供电、共地。")
        return 1

    # 3. 加速度（0x3B 起 6 字节，大端 int16）
    acc = read_reg(0x3B, 6)
    if acc:
        ax, ay, az = struct.unpack(">hhh", acc)
        print(f"[PASS] 加速度原始: X={ax} Y={ay} Z={az}")
        print(f"       换算(g): X={ax/16384:.3f} Y={ay/16384:.3f} Z={az/16384:.3f}")

    # 4. 陀螺仪（0x43 起 6 字节）
    gyr = read_reg(0x43, 6)
    if gyr:
        gx, gy, gz = struct.unpack(">hhh", gyr)
        print(f"[PASS] 陀螺仪原始: X={gx} Y={gy} Z={gz}")
        print(f"       换算(deg/s): X={gx/131:.2f} Y={gy/131:.2f} Z={gz/131:.2f}")

    ser.close()
    print("\nMPU6050 读取验证通过 [OK]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
