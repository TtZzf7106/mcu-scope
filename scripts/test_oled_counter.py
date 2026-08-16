"""SSD1306 OLED 计数器：每秒 +1，满 100 归 0，大字体居中显示。

运行：.\.venv\Scripts\python.exe scripts\test_oled_counter.py COM8
停止：Ctrl+C
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

# 5x7 字模（每数字 5 列，bit0=顶部行）
FONT = {
    "0": [0x3E, 0x51, 0x49, 0x45, 0x3E],
    "1": [0x00, 0x42, 0x7F, 0x40, 0x00],
    "2": [0x42, 0x61, 0x51, 0x49, 0x46],
    "3": [0x21, 0x41, 0x45, 0x4B, 0x31],
    "4": [0x18, 0x14, 0x12, 0x7F, 0x10],
    "5": [0x27, 0x45, 0x45, 0x45, 0x39],
    "6": [0x3C, 0x4A, 0x49, 0x49, 0x30],
    "7": [0x01, 0x71, 0x09, 0x05, 0x03],
    "8": [0x36, 0x49, 0x49, 0x49, 0x36],
    "9": [0x06, 0x49, 0x49, 0x29, 0x1E],
}

# SSD1306 初始化命令
INIT = [
    0xAE, 0xD5, 0x80, 0xA8, 0x3F, 0xD3, 0x00, 0x40,
    0x8D, 0x14, 0x20, 0x00, 0xA1, 0xC8, 0xDA, 0x12,
    0x81, 0xCF, 0xD9, 0xF1, 0xDB, 0x40, 0xA4, 0xA6, 0xAF,
]


def draw_number(buf: bytearray, num: int, scale: int = 4) -> None:
    """把数字画到 128x64 帧缓冲（buf 为 8 页 × 128 列 = 1024 字节）。"""
    text = str(num)
    glyph_w = 5 * scale
    gap = 1 * scale
    total_w = len(text) * glyph_w + (len(text) - 1) * gap
    x = (128 - total_w) // 2
    y = (64 - 7 * scale) // 2
    for ch in text:
        glyph = FONT[ch]
        for col in range(5):
            bits = glyph[col]
            for row in range(7):
                if bits & (1 << row):
                    for dy in range(scale):
                        for dx in range(scale):
                            px = x + col * scale + dx
                            py = y + row * scale + dy
                            buf[py // 8 * 128 + px] |= (1 << (py % 8))
        x += glyph_w + gap


def main() -> int:
    port = sys.argv[1] if len(sys.argv) > 1 else "COM8"
    app = QCoreApplication(sys.argv)
    ser = SerialLink()
    sess = BridgeSession(BridgeLink(ser))
    acks: list = []
    sess.ack_received.connect(lambda a: acks.append(a))
    ser.open(port, baudrate=115200)
    time.sleep(0.5)

    def wait(timeout: float = 2.0):
        acks.clear()
        t0 = time.time()
        while time.time() - t0 < timeout:
            app.processEvents()
            if acks:
                return acks[0]
            time.sleep(0.01)
        return None

    # 初始化
    sess.i2c_write(ADDR, b"\x00" + bytes(INIT))
    wait()

    counter = 0
    print("计数器已启动（Ctrl+C 停止）")
    try:
        while True:
            buf = bytearray(1024)
            draw_number(buf, counter)
            # 设置寻址 + 写整屏
            sess.i2c_write(ADDR, b"\x00\x21\x00\x7F\x22\x00\x07")
            wait()
            sess.i2c_write(ADDR, b"\x40" + bytes(buf))
            wait()
            print(f"显示: {counter}")
            counter = (counter + 1) % 100   # 满 100 归 0
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        ser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
