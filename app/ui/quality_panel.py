"""质量面板：吞吐曲线 + 累计字节。"""
from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from ..analysis.stats import SessionStats


def fmt_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KiB"
    return f"{n / 1024 / 1024:.1f} MiB"


class QualityPanel(QWidget):
    """实时 RX/TX 吞吐曲线与累计统计。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        pg.setConfigOptions(antialias=True)

        self._plot = pg.PlotWidget()
        self._plot.setBackground("#1e1e2e")
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        self._plot.setLabel("left", "速率", units="B/s")
        self._plot.setLabel("bottom", "时间", units="s")
        self._plot.addLegend()
        self._rx_curve = self._plot.plot(pen=pg.mkPen("#4ade80", width=2), name="RX")
        self._tx_curve = self._plot.plot(pen=pg.mkPen("#60a5fa", width=2), name="TX")

        self.lbl_rx_rate = QLabel("RX: 0 B/s")
        self.lbl_tx_rate = QLabel("TX: 0 B/s")
        self.lbl_total_rx = QLabel("累计 RX: 0 B")
        self.lbl_total_tx = QLabel("累计 TX: 0 B")

        grid = QGridLayout()
        grid.addWidget(self.lbl_rx_rate, 0, 0)
        grid.addWidget(self.lbl_tx_rate, 0, 1)
        grid.addWidget(self.lbl_total_rx, 1, 0)
        grid.addWidget(self.lbl_total_tx, 1, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(self._plot, stretch=1)
        layout.addLayout(grid)

    def update_data(self, stats: SessionStats) -> None:
        if stats.times:
            t0 = stats.times[0]
            times = [t - t0 for t in stats.times]
            self._rx_curve.setData(times, stats.rx_rates)
            self._tx_curve.setData(times, stats.tx_rates)
        rx = stats.rx_rates[-1] if stats.rx_rates else 0.0
        tx = stats.tx_rates[-1] if stats.tx_rates else 0.0
        self.lbl_rx_rate.setText(f"RX: {rx:.0f} B/s")
        self.lbl_tx_rate.setText(f"TX: {tx:.0f} B/s")
        self.lbl_total_rx.setText(f"累计 RX: {fmt_bytes(stats.total_rx)}")
        self.lbl_total_tx.setText(f"累计 TX: {fmt_bytes(stats.total_tx)}")
