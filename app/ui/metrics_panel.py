"""质量指标面板：协议错误计数 + 丢帧/错误率 + 延迟直方图。

M1 直连模式下无帧可解析，计数器保持 0；M2 桥接模式接入后由 BridgeLink
填充。延迟直方图基于回环往返时间（M3 起）。
"""
from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from ..analysis.metrics import QualityMetrics


class MetricsPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        pg.setConfigOptions(antialias=True)

        err = QGroupBox("协议层错误")
        egrid = QGridLayout()
        self.lbl_crc = QLabel("CRC 错误: 0")
        self.lbl_len = QLabel("长度错误: 0")
        self.lbl_gap = QLabel("丢帧(seq): 0")
        self.lbl_proto = QLabel("协议错误(NACK等): 0")
        egrid.addWidget(self.lbl_crc, 0, 0)
        egrid.addWidget(self.lbl_len, 0, 1)
        egrid.addWidget(self.lbl_gap, 1, 0)
        egrid.addWidget(self.lbl_proto, 1, 1)
        err.setLayout(egrid)

        rate = QGroupBox("完整性与错误率")
        rgrid = QGridLayout()
        self.lbl_frames = QLabel("总帧数: 0")
        self.lbl_loss = QLabel("丢帧率: 0.00%")
        self.lbl_err = QLabel("错误率: 0.00%")
        rgrid.addWidget(self.lbl_frames, 0, 0)
        rgrid.addWidget(self.lbl_loss, 1, 0)
        rgrid.addWidget(self.lbl_err, 1, 1)
        rate.setLayout(rgrid)

        lat = QGroupBox("延迟 (ms)")
        lgrid = QGridLayout()
        self.lbl_lat = QLabel("min/avg/max: -")
        self.lat_plot = pg.PlotWidget()
        self.lat_plot.setBackground("#1e1e2e")
        self.lat_plot.setLabel("left", "次数")
        self.lat_plot.setLabel("bottom", "延迟", units="ms")
        lgrid.addWidget(self.lbl_lat, 0, 0)
        lgrid.addWidget(self.lat_plot, 1, 0)
        lat.setLayout(lgrid)

        layout = QVBoxLayout(self)
        layout.addWidget(err)
        layout.addWidget(rate)
        layout.addWidget(lat, stretch=1)

        self._hist: pg.BarGraphItem | None = None

    def update_data(self, metrics: QualityMetrics) -> None:
        self.lbl_crc.setText(f"CRC 错误: {metrics.crc_errors}")
        self.lbl_len.setText(f"长度错误: {metrics.length_errors}")
        self.lbl_gap.setText(f"丢帧(seq): {metrics.seq_gaps}")
        self.lbl_proto.setText(f"协议错误(NACK等): {metrics.protocol_errors}")
        self.lbl_frames.setText(f"总帧数: {metrics.total_frames}")
        self.lbl_loss.setText(f"丢帧率: {metrics.loss_rate * 100:.2f}%")
        self.lbl_err.setText(f"错误率: {metrics.error_rate * 100:.2f}%")

        lats = metrics.recent_latencies()
        if lats:
            mn, mx = min(lats), max(lats)
            avg = sum(lats) / len(lats)
            self.lbl_lat.setText(f"min/avg/max: {mn:.2f}/{avg:.2f}/{mx:.2f} ms  (n={len(lats)})")
            if len(lats) >= 2:
                bins = min(30, max(2, len(lats) // 10 + 1))
                hist, edges = np.histogram(lats, bins=bins)
                x = (edges[:-1] + edges[1:]) / 2
                width = (edges[1] - edges[0]) * 0.9
                if self._hist is None:
                    self._hist = pg.BarGraphItem(x=x, height=hist, width=width, brush="#f472b6")
                    self.lat_plot.addItem(self._hist)
                else:
                    self._hist.setOpts(x=x, height=hist, width=width)
        else:
            self.lbl_lat.setText("min/avg/max: -")
