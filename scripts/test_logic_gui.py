"""逻辑抓取 GUI 闭环测试：驱动 MainWindow → 抓取 → 波形视图更新。

运行：.\.venv\Scripts\python.exe scripts\test_logic_gui.py [COM口]
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

    w.bridge_session.logic_cfg(100000, 0x01)
    time.sleep(0.2)
    w.bridge_session.logic_start()

    t0 = time.time()
    while time.time() - t0 < 3.0:
        app.processEvents()
        if w.waveform._capture is not None:
            break
        time.sleep(0.01)

    cap = w.waveform._capture
    ok = cap is not None
    print(f"[{'PASS' if ok else 'FAIL'}] GUI 波形更新: "
          f"{cap.sample_count() if cap else 0} 样本")
    if not ok:
        w.link.close()
        return 1

    w.link.close()
    print("\n逻辑抓取 GUI 闭环测试通过 [OK]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
