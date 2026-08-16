"""主窗口：连接面板 + 实时数据/吞吐/质量指标标签页 + 导出菜单。"""
from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox, QSplitter, QTabWidget

from ..analysis.logic_capture import from_bitmap
from ..analysis.metrics import QualityMetrics
from ..analysis.stats import SessionStats
from ..link.bridge_link import BridgeLink
from ..link.bridge_session import BridgeSession
from ..link.serial_link import SerialLink
from ..storage.export import ExportEntry, export_csv, export_log
from .bridge_panel import BridgePanel
from .connection_panel import ConnectionPanel
from .data_view import DataView
from .metrics_panel import MetricsPanel
from .quality_panel import QualityPanel
from .waveform_view import WaveformView


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MCU Scope — 单片机数据读取上位机（M1 UART）")
        self.resize(1280, 800)

        self.link = SerialLink(self)
        self.stats = SessionStats()
        self.metrics = QualityMetrics()
        self._log: list[ExportEntry] = []

        self.conn = ConnectionPanel()
        self.data = DataView()
        self.quality = QualityPanel()
        self.metrics_panel = MetricsPanel()
        self.waveform = WaveformView()
        self.bridge_link = BridgeLink(self.link)
        self.bridge_session = BridgeSession(self.bridge_link)
        self.bridge_panel = BridgePanel(self.bridge_session)

        tabs = QTabWidget()
        tabs.addTab(self.data, "实时数据")
        tabs.addTab(self.quality, "吞吐")
        tabs.addTab(self.metrics_panel, "质量指标")
        tabs.addTab(self.waveform, "波形")
        tabs.addTab(self.bridge_panel, "桥接")

        main_split = QSplitter(Qt.Orientation.Horizontal)
        main_split.addWidget(self.conn)
        main_split.addWidget(tabs)
        main_split.setStretchFactor(0, 0)
        main_split.setStretchFactor(1, 1)
        main_split.setSizes([280, 1000])

        self.setCentralWidget(main_split)

        self.status = self.statusBar()
        self.status.showMessage("未连接")

        self._build_menu()

        self.conn.btn_open.clicked.connect(self._toggle_connection)
        self.conn.btn_send.clicked.connect(self._send)
        self.link.data_received.connect(self._on_data)
        self.link.status_changed.connect(self._on_status)
        self.link.error_occurred.connect(self._on_error)
        self.bridge_session.logic_data.connect(self._on_logic_data)

        self._timer = QTimer(self)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self._sample)
        self._timer.start()

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("文件")
        menu.addAction("导出 CSV...", self._export_csv)
        menu.addAction("导出日志...", self._export_log)
        menu.addSeparator()
        menu.addAction("清空记录", self._clear_log)
        menu.addSeparator()
        menu.addAction("退出", self.close)

    # ---- 连接 ----
    def _toggle_connection(self) -> None:
        if self.link.is_open:
            self.link.close()
        else:
            params = self.conn.current_params()
            self.link.open(
                port=params["port"],
                baudrate=params["baudrate"],
                bytesize=params["bytesize"],
                parity=params["parity"],
                stopbits=params["stopbits"],
            )

    # ---- 发送 ----
    def _send(self) -> None:
        payload, err = self.conn.build_payload()
        if err is not None:
            QMessageBox.warning(self, "发送", err)
            return
        if not payload:
            return
        self.link.write(payload)

    # ---- 接收 ----
    def _on_data(self, data: bytes, direction: str) -> None:
        self.stats.add(len(data), direction)
        self.data.append(data, direction)
        self._log.append(ExportEntry(ts=time.time(), direction=direction, data=data))
        if len(self._log) > 1_000_000:  # 防内存无界增长
            del self._log[:100_000]

    def _on_logic_data(self, block_seq: int, samples: bytes) -> None:
        """逻辑抓取数据 → 波形视图。"""
        rate = self.bridge_session.logic_rate
        if rate <= 0:
            return
        cap = from_bitmap(samples, 1.0 / rate, [f"CH{i}" for i in range(8)])
        self.waveform.set_capture(cap)

    def _on_status(self, connected: bool) -> None:
        self.conn.set_connected(connected)
        self.status.showMessage(f"已连接 {self.conn.current_port()}" if connected else "未连接")

    def _on_error(self, message: str) -> None:
        self.status.showMessage(message, 5000)

    def _sample(self) -> None:
        self.stats.sample()
        self.quality.update_data(self.stats)
        self.metrics_panel.update_data(self.metrics)

    # ---- 导出 ----
    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "导出 CSV", "session.csv", "CSV (*.csv)")
        if not path:
            return
        export_csv(path, self._log)
        self.status.showMessage(f"已导出 {len(self._log)} 条到 {path}", 5000)

    def _export_log(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "导出日志", "session.log", "日志 (*.log *.txt)")
        if not path:
            return
        export_log(path, self._log)
        self.status.showMessage(f"已导出 {len(self._log)} 条到 {path}", 5000)

    def _clear_log(self) -> None:
        self._log.clear()
        self.data.text.clear()
        self.stats = SessionStats()
        self.metrics.reset()
        self.status.showMessage("已清空记录与统计", 3000)
