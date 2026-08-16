"""桥接控制面板：PING / I2C 扫描读写 / SPI 传输。"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..link.bridge_session import BridgeSession
from ..protocol.commands import Cmd


class BridgePanel(QWidget):
    def __init__(self, session: BridgeSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session = session

        # ---- PING ----
        ping = QGroupBox("连接测试")
        pgrid = QGridLayout()
        self.btn_ping = QPushButton("PING")
        self.lbl_ping = QLabel("未测试")
        pgrid.addWidget(self.btn_ping, 0, 0)
        pgrid.addWidget(self.lbl_ping, 0, 1)
        ping.setLayout(pgrid)

        # ---- I2C ----
        i2c = QGroupBox("I2C")
        igrid = QGridLayout()
        self.btn_scan = QPushButton("扫描地址")
        self.lbl_scan = QLabel("")
        self.spin_addr = QSpinBox()
        self.spin_addr.setRange(0x08, 0x77)
        self.spin_addr.setValue(0x50)
        self.spin_addr.setDisplayIntegerBase(16)
        self.spin_addr.setPrefix("0x")
        self.edt_wr = QLineEdit()
        self.edt_wr.setPlaceholderText("写数据 hex，如 A0 01")
        self.btn_wr = QPushButton("写")
        self.spin_len = QSpinBox()
        self.spin_len.setRange(1, 255)
        self.spin_len.setValue(16)
        self.btn_rd = QPushButton("读")
        self.lbl_i2c = QLabel("")
        igrid.addWidget(self.btn_scan, 0, 0)
        igrid.addWidget(self.lbl_scan, 0, 1)
        igrid.addWidget(QLabel("地址"), 1, 0)
        igrid.addWidget(self.spin_addr, 1, 1)
        igrid.addWidget(self.edt_wr, 2, 0, 1, 2)
        igrid.addWidget(self.btn_wr, 3, 0)
        igrid.addWidget(QLabel("读长度"), 3, 1)
        igrid.addWidget(self.spin_len, 4, 0)
        igrid.addWidget(self.btn_rd, 4, 1)
        igrid.addWidget(self.lbl_i2c, 5, 0, 1, 2)
        i2c.setLayout(igrid)

        # ---- SPI ----
        spi = QGroupBox("SPI")
        sgrid = QGridLayout()
        self.edt_spi = QLineEdit()
        self.edt_spi.setPlaceholderText("发送 hex，如 9F 00 00")
        self.btn_spi = QPushButton("传输")
        self.lbl_spi = QLabel("")
        sgrid.addWidget(self.edt_spi, 0, 0, 1, 2)
        sgrid.addWidget(self.btn_spi, 1, 0)
        sgrid.addWidget(self.lbl_spi, 1, 1)
        spi.setLayout(sgrid)

        layout = QVBoxLayout(self)
        layout.addWidget(ping)
        layout.addWidget(i2c)
        layout.addWidget(spi)
        layout.addStretch(1)

        # ---- 信号 ----
        session.ack_received.connect(self._on_ack)
        session.error_received.connect(self._on_error)
        self.btn_ping.clicked.connect(session.ping)
        self.btn_scan.clicked.connect(session.i2c_scan)
        self.btn_wr.clicked.connect(self._i2c_write)
        self.btn_rd.clicked.connect(self._i2c_read)
        self.btn_spi.clicked.connect(self._spi_transfer)

    # ---- 动作 ----
    @staticmethod
    def _parse_hex(text: str) -> bytes | None:
        h = "".join(text.split())
        if len(h) % 2 or any(c not in "0123456789abcdefABCDEF" for c in h):
            return None
        return bytes.fromhex(h)

    def _i2c_write(self) -> None:
        data = self._parse_hex(self.edt_wr.text())
        if data is None:
            self.lbl_i2c.setText("非法 hex")
            return
        self.session.i2c_write(self.spin_addr.value(), data)

    def _i2c_read(self) -> None:
        self.session.i2c_read(self.spin_addr.value(), self.spin_len.value())

    def _spi_transfer(self) -> None:
        data = self._parse_hex(self.edt_spi.text())
        if data is None:
            self.lbl_spi.setText("非法 hex")
            return
        self.session.spi_transfer(0, data)

    # ---- 响应 ----
    def _last_latency(self) -> float:
        lats = self.session.metrics.recent_latencies()
        return lats[-1] if lats else 0.0

    def _on_ack(self, ack) -> None:
        if ack.status != 0:
            return
        if ack.ack_cmd == Cmd.PING:
            ver = f"{ack.data[0]}.{ack.data[1]}" if len(ack.data) >= 2 else "?"
            self.lbl_ping.setText(f"版本 {ver} · 延迟 {self._last_latency():.1f}ms")
        elif ack.ack_cmd == Cmd.I2C_SCAN:
            addrs = " ".join(f"0x{b:02X}" for b in ack.data)
            self.lbl_scan.setText(f"{len(ack.data)} 个: {addrs}" if addrs else "无设备")
        elif ack.ack_cmd in (Cmd.I2C_READ, Cmd.I2C_WRITE):
            self.lbl_i2c.setText(f"OK · {ack.data.hex(' ').upper()}")
        elif ack.ack_cmd == Cmd.SPI_TRANSFER:
            self.lbl_spi.setText(f"RX: {ack.data.hex(' ').upper()}")

    def _on_error(self, err) -> None:
        if err.code == 2:  # ERR_BUS
            self.lbl_i2c.setText("总线错误(NACK)")
            self.lbl_spi.setText("总线错误")
        else:
            self.lbl_i2c.setText(f"错误 code={err.code}")
            self.lbl_spi.setText(f"错误 code={err.code}")
