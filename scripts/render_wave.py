"""渲染波形视图为 PNG（离屏），用于预览/验证 M4 渲染。

运行：.\.venv\Scripts\python.exe scripts\render_wave.py
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.ui.waveform_view import WaveformView  # noqa: E402
from app.analysis.logic_capture import demo_uart  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    w = WaveformView()
    w.resize(1200, 500)
    w.set_capture(demo_uart())
    w.show()
    app.processEvents()
    pix = w.grab()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wave_preview.png")
    pix.save(out)
    print(f"saved {os.path.abspath(out)}  {pix.width()}x{pix.height()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
