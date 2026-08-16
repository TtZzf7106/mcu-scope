"""桥接 GUI 实机功能测试：驱动面板按钮 → BridgeSession → 真实板子 → 标签更新。

运行：.\.venv\Scripts\python.exe scripts\test_bridge_gui.py [COM口]
"""
from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.ui.main_window import MainWindow  # noqa: E402


def main() -> int:
    port = sys.argv[1] if len(sys.argv) > 1 else "COM8"
    app = QApplication(sys.argv)
    w = MainWindow()
    w.link.open(port, baudrate=115200)
    time.sleep(0.5)

    def pump_until(pred, timeout: float) -> bool:
        t0 = time.time()
        while time.time() - t0 < timeout:
            app.processEvents()
            if pred():
                return True
            time.sleep(0.01)
        return False

    # PING
    w.bridge_panel.btn_ping.click()
    ok = pump_until(lambda: "版本" in w.bridge_panel.lbl_ping.text(), 2.0)
    print(f"[{'PASS' if ok else 'FAIL'}] GUI PING → 标签: {w.bridge_panel.lbl_ping.text()}")
    assert ok, "PING 未响应"

    # I2C 扫描
    w.bridge_panel.btn_scan.click()
    ok = pump_until(lambda: w.bridge_panel.lbl_scan.text() != "", 3.0)
    print(f"[{'PASS' if ok else 'FAIL'}] GUI I2C 扫描 → 标签: {w.bridge_panel.lbl_scan.text()}")
    assert ok, "I2C 扫描未响应"

    w.link.close()
    print("\n桥接 GUI 功能测试通过 [OK]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
