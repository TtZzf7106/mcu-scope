"""数字波形视图：逻辑分析仪式多通道波形 + 游标测量 + UART 解码。"""
from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..analysis.i2c_decode import decode_i2c
from ..analysis.logic_capture import LogicCapture, demo_uart
from ..analysis.spi_decode import decode_spi
from ..analysis.uart_decode import decode_uart

CHANNEL_COLORS = [
    "#4ade80", "#60a5fa", "#facc15", "#f472b6",
    "#a78bfa", "#fb923c", "#34d399", "#f87171",
]


class WaveformView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        pg.setConfigOptions(antialias=True)

        self._plot = pg.PlotWidget()
        self._plot.setBackground("#1e1e2e")
        self._plot.showGrid(x=True, y=True, alpha=0.25)
        self._plot.setLabel("bottom", "时间", units="s")
        self._plot.setMouseEnabled(x=True, y=True)

        self.lbl_info = QLabel("未捕获")
        self.btn_demo = QPushButton("加载示例波形")

        self.spin_ch = QSpinBox()
        self.spin_ch.setRange(0, 7)
        self.spin_ch.setValue(0)
        self.spin_baud = QSpinBox()
        self.spin_baud.setRange(300, 4_000_000)
        self.spin_baud.setValue(115200)
        self.spin_baud.setSingleStep(9600)
        self.btn_decode = QPushButton("UART 解码")
        self.lbl_decode = QLabel("")

        self.spin_i2c_scl = QSpinBox()
        self.spin_i2c_scl.setRange(0, 7)
        self.spin_i2c_scl.setValue(0)
        self.spin_i2c_sda = QSpinBox()
        self.spin_i2c_sda.setRange(0, 7)
        self.spin_i2c_sda.setValue(1)
        self.btn_i2c = QPushButton("I2C 解码")
        self.lbl_i2c = QLabel("")

        self.spin_spi_sck = QSpinBox()
        self.spin_spi_sck.setRange(0, 7)
        self.spin_spi_sck.setValue(0)
        self.spin_spi_mosi = QSpinBox()
        self.spin_spi_mosi.setRange(0, 7)
        self.spin_spi_mosi.setValue(1)
        self.spin_spi_miso = QSpinBox()
        self.spin_spi_miso.setRange(0, 7)
        self.spin_spi_miso.setValue(2)
        self.spin_spi_mode = QSpinBox()
        self.spin_spi_mode.setRange(0, 3)
        self.spin_spi_mode.setValue(0)
        self.btn_spi = QPushButton("SPI 解码")
        self.lbl_spi = QLabel("")

        top = QHBoxLayout()
        top.addWidget(self.btn_demo)
        top.addWidget(self.lbl_info, stretch=1)

        decode_row = QHBoxLayout()
        decode_row.addWidget(QLabel("UART 解码: 通道"))
        decode_row.addWidget(self.spin_ch)
        decode_row.addWidget(QLabel("波特率"))
        decode_row.addWidget(self.spin_baud)
        decode_row.addWidget(self.btn_decode)
        decode_row.addWidget(self.lbl_decode, stretch=1)

        i2c_row = QHBoxLayout()
        i2c_row.addWidget(QLabel("I2C: SCL"))
        i2c_row.addWidget(self.spin_i2c_scl)
        i2c_row.addWidget(QLabel("SDA"))
        i2c_row.addWidget(self.spin_i2c_sda)
        i2c_row.addWidget(self.btn_i2c)
        i2c_row.addWidget(self.lbl_i2c, stretch=1)

        spi_row = QHBoxLayout()
        spi_row.addWidget(QLabel("SPI: SCK"))
        spi_row.addWidget(self.spin_spi_sck)
        spi_row.addWidget(QLabel("MOSI"))
        spi_row.addWidget(self.spin_spi_mosi)
        spi_row.addWidget(QLabel("MISO"))
        spi_row.addWidget(self.spin_spi_miso)
        spi_row.addWidget(QLabel("模式"))
        spi_row.addWidget(self.spin_spi_mode)
        spi_row.addWidget(self.btn_spi)
        spi_row.addWidget(self.lbl_spi, stretch=1)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addLayout(decode_row)
        layout.addLayout(i2c_row)
        layout.addLayout(spi_row)
        layout.addWidget(self._plot, stretch=1)

        self._capture: LogicCapture | None = None
        self._cursor = pg.InfiniteLine(
            angle=90, movable=True, pen=pg.mkPen("#f43f5e", width=1, style=Qt.PenStyle.DashLine)
        )
        self._plot.addItem(self._cursor)
        self._cursor.sigPositionChanged.connect(self._on_cursor)

        self.btn_demo.clicked.connect(lambda: self.set_capture(demo_uart()))
        self.btn_decode.clicked.connect(self._decode)
        self.btn_i2c.clicked.connect(self._decode_i2c)
        self.btn_spi.clicked.connect(self._decode_spi)

    def set_capture(self, capture: LogicCapture) -> None:
        self._capture = capture
        self._plot.clear()
        offset = 0.0
        ticks: list[tuple[float, str]] = []
        for ci, name in enumerate(capture.names):
            xs, ys = capture.channel_series(ci)
            y = [offset + v for v in ys]
            self._plot.plot(
                xs, y, pen=pg.mkPen(CHANNEL_COLORS[ci % len(CHANNEL_COLORS)], width=2)
            )
            ticks.append((offset + 0.5, name))
            offset += 2.0
        self._plot.getAxis("left").setTicks([ticks])
        self._plot.setYRange(-1, offset)
        self._plot.setXRange(0, max(capture.duration, 1e-6))
        self._plot.addItem(self._cursor)
        self._update_info()
        self.lbl_decode.setText("")
        self.lbl_i2c.setText("")
        self.lbl_spi.setText("")

    def _on_cursor(self, *_args) -> None:
        self._update_info()

    def _update_info(self) -> None:
        if self._capture is None:
            self.lbl_info.setText("未捕获")
            return
        t = self._cursor.value()
        k = int(t / self._capture.dt)
        if 0 <= k < len(self._capture.samples):
            levels = "".join(str(b) for b in reversed(self._capture.samples[k]))
            self.lbl_info.setText(
                f"t={t * 1000:.3f} ms · 样本#{k} · 电平(MSB→LSB)={levels}"
            )
        else:
            self.lbl_info.setText(
                f"通道 {len(self._capture.names)} · 采样率 {1 / self._capture.dt:.0f} Hz · "
                f"时长 {self._capture.duration * 1000:.1f} ms · 点数 {len(self._capture.samples)}"
            )

    def _decode(self) -> None:
        if self._capture is None:
            self.lbl_decode.setText("请先加载波形")
            return
        ch = self.spin_ch.value()
        if ch >= len(self._capture.names):
            self.lbl_decode.setText("通道越界")
            return
        try:
            res = decode_uart(self._capture, ch, self.spin_baud.value())
        except ValueError as exc:
            self.lbl_decode.setText(f"解码失败: {exc}")
            return
        if not res:
            self.lbl_decode.setText("未解出字节（检查通道/波特率）")
            return
        hexs = " ".join(f"{b.value:02X}" for b in res)
        text = "".join(chr(b.value) if 32 <= b.value < 127 else "." for b in res)
        errs = sum(1 for b in res if b.framing_error)
        suffix = f" · 帧错误 {errs}" if errs else ""
        self.lbl_decode.setText(f"{len(res)} 字节: {hexs}  |  {text}{suffix}")

    def _decode_i2c(self) -> None:
        if self._capture is None:
            self.lbl_i2c.setText("请先加载波形")
            return
        scl = self.spin_i2c_scl.value()
        sda = self.spin_i2c_sda.value()
        if max(scl, sda) >= len(self._capture.names):
            self.lbl_i2c.setText("通道越界")
            return
        trs = decode_i2c(self._capture, scl, sda)
        if not trs:
            self.lbl_i2c.setText("未解出事务")
            return
        parts = []
        for t in trs:
            rw = "R" if t.is_read else "W"
            data = " ".join(f"{b.value:02X}{'' if b.ack else '!'}" for b in t.data)
            parts.append(f"0x{t.addr7:02X}{rw}[{data}]")
        self.lbl_i2c.setText(f"{len(trs)} 事务: " + " | ".join(parts))

    def _decode_spi(self) -> None:
        if self._capture is None:
            self.lbl_spi.setText("请先加载波形")
            return
        sck = self.spin_spi_sck.value()
        mosi = self.spin_spi_mosi.value()
        miso = self.spin_spi_miso.value()
        if max(sck, mosi, miso) >= len(self._capture.names):
            self.lbl_spi.setText("通道越界")
            return
        mo, mi = decode_spi(self._capture, sck, mosi, miso, self.spin_spi_mode.value())
        if not mo:
            self.lbl_spi.setText("未解出字节")
            return
        self.lbl_spi.setText(f"MOSI {' '.join(f'{b:02X}' for b in mo)}  |  "
                             f"MISO {' '.join(f'{b:02X}' for b in mi)}")
