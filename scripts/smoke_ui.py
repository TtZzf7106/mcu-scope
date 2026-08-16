"""UI 离屏冒烟测试：构建主窗口、模拟收发、验证记录与导出。

运行：.\.venv\Scripts\python.exe scripts\smoke_ui.py
"""
from __future__ import annotations

import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.ui.main_window import MainWindow  # noqa: E402
from app.storage.export import export_csv, export_log  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    w = MainWindow()

    # 模拟收发
    w._on_data(b"ping 0\n", "RX")
    w._on_data(b"hello", "TX")
    w._sample()  # 触发绘图/指标刷新

    assert len(w._log) == 2, f"日志条数错误: {len(w._log)}"
    assert w.stats.total_rx == 7 and w.stats.total_tx == 5, "字节统计错误"

    # 导出
    with tempfile.TemporaryDirectory() as d:
        c = os.path.join(d, "s.csv")
        export_csv(c, w._log)
        export_log(os.path.join(d, "s.log"), w._log)
        assert os.path.getsize(c) > 0, "CSV 导出为空"

    # 标签页数量
    tabs = w.centralWidget().widget(1)
    assert tabs.count() == 5, f"标签页数量错误: {tabs.count()}"

    # 指标面板刷新不抛异常（先记帧，再记丢帧/CRC，模拟真实序列）
    for _ in range(9):
        w.metrics.record_frame()
    w.metrics.record_frame_error("seq_gap")
    w.metrics.record_frame_error("crc")
    w.metrics_panel.update_data(w.metrics)
    assert w.metrics.loss_rate > 0

    # 波形视图：加载示例 + UART 解码
    from app.analysis.logic_capture import demo_uart
    cap = demo_uart()
    w.waveform.set_capture(cap)
    assert w.waveform._capture is not None and len(cap.samples) > 0
    w.waveform.spin_ch.setValue(0)
    w.waveform.spin_baud.setValue(115200)
    w.waveform._decode()
    assert "41" in w.waveform.lbl_decode.text() and "A" in w.waveform.lbl_decode.text(), \
        f"解码结果异常: {w.waveform.lbl_decode.text()}"

    w.close()
    print("UI 冒烟测试通过 [OK]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
