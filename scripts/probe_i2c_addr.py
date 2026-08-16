"""探测指定 I2C 地址是否有设备应答（用于 0x78-0x7B 等扫描范围外的地址）。

运行：.\.venv\Scripts\python.exe scripts\probe_i2c_addr.py COM8
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QCoreApplication  # noqa: E402

from app.link.bridge_link import BridgeLink  # noqa: E402
from app.link.bridge_session import BridgeSession  # noqa: E402
from app.link.serial_link import SerialLink  # noqa: E402


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

    def probe(addr: int) -> str:
        acks.clear()
        errs.clear()
        sess.i2c_write(addr, b"\x00")   # 写 1 字节，看是否 ACK
        t0 = time.time()
        while time.time() - t0 < 1.0:
            app.processEvents()
            if acks:
                return "ACK(有设备)"
            if errs:
                return f"无应答(错误码{errs[0].code})"
            time.sleep(0.01)
        return "超时"

    for addr in (0x68, 0x69, 0x7A, 0x7B, 0x78, 0x3C, 0x3D):
        print(f"地址 0x{addr:02X}: {probe(addr)}")

    ser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
