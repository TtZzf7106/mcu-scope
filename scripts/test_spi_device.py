"""SPI 设备测试：读 JEDEC ID（识别 W25Qxx 等 SPI Flash）。

即使未接设备，也能验证 SPI 传输通路是否通（MISO 浮空返回 0xFF）。

运行：.\.venv\Scripts\python.exe scripts\test_spi_device.py [COM口]
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
    sess.ack_received.connect(lambda a: acks.append(a))
    ser.open(port, baudrate=115200)
    time.sleep(0.5)

    def wait_ack(timeout: float = 2.0):
        acks.clear()
        t0 = time.time()
        while time.time() - t0 < timeout:
            app.processEvents()
            if acks:
                return acks[0]
            time.sleep(0.01)
        return None

    # SPI 配置（固件固定 500kHz）
    sess.spi_cfg(500000, 0, 0)
    wait_ack(1.0)

    # 读 JEDEC ID：命令 0x9F + 3 字节响应
    sess.spi_transfer(0, bytes([0x9F, 0x00, 0x00, 0x00]))
    ack = wait_ack(2.0)

    if not ack or ack.status != 0:
        print("[FAIL] SPI 传输无 ACK（SPI 通路异常）")
        ser.close()
        return 1

    rx = ack.data
    print(f"[SPI] 读 JEDEC ID: 响应 {rx.hex(' ').upper()}")

    if len(rx) >= 4:
        ident = rx[1:4]
        if ident == b"\xEF\x40\x17":
            print("[PASS] 识别为 W25Q64 Flash (EF 40 17)")
        elif ident == b"\xEF\x40\x16":
            print("[PASS] 识别为 W25Q32 Flash (EF 40 16)")
        elif all(b == 0xFF for b in ident):
            print("[信息] 响应全 0xFF → 未接 SPI 设备（MISO 浮空），SPI 通路已通")
        else:
            print(f"[信息] 未知响应，可能接了其它 SPI 设备")
    else:
        print(f"[信息] 响应长度 {len(rx)}（预期 4）")

    ser.close()
    print("\nSPI 通路测试完成 [OK]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
