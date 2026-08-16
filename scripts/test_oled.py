"""SSD1306 OLED 点亮验证：初始化 + 画条纹图案。

接线：VCC→3.3V、GND→GND、SCL→PB6、SDA→PB7（地址 0x3C）。

运行：.\.venv\Scripts\python.exe scripts\test_oled.py [COM口]
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

ADDR = 0x3C

# SSD1306 初始化命令序列
INIT = [
    0xAE, 0xD5, 0x80, 0xA8, 0x3F, 0xD3, 0x00, 0x40,
    0x8D, 0x14, 0x20, 0x00, 0xA1, 0xC8, 0xDA, 0x12,
    0x81, 0xCF, 0xD9, 0xF1, 0xDB, 0x40, 0xA4, 0xA6, 0xAF,
]


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

    def cmd(cmds: list[int]) -> bool:
        """发送命令序列（0x00 控制字节 + 命令）。"""
        sess.i2c_write(ADDR, b"\x00" + bytes(cmds))
        ack = wait()
        return ack is not None and ack.status == 0

    # 1. 初始化
    ok = cmd(INIT)
    print(f"[{'PASS' if ok else 'FAIL'}] OLED 初始化")

    # 2. 设置寻址：列 0-127，页 0-7
    cmd([0x21, 0x00, 0x7F, 0x22, 0x00, 0x07])

    # 3. 画 4 条白色横条纹（每页 128 字节，页0/2/4/6 全亮）
    for page in range(8):
        fill = 0xFF if page % 2 == 0 else 0x00
        sess.i2c_write(ADDR, b"\x40" + bytes([fill]) * 128)
        wait()

    print("[PASS] 已写入条纹图案（4 条白横纹）")
    print("\n请看 OLED 屏幕：应显示 4 条白色横条纹。")

    ser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
