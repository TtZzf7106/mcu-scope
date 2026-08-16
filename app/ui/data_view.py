"""实时数据视图：hex / ASCII / 时间戳 / 方向。"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def ascii_repr(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b < 127 else "." for b in data)


class DataView(QWidget):
    """接收数据流展示。批量缓冲 + QTimer 刷新，避免高频数据卡 UI。"""

    MAX_BLOCKS = 20_000

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pending: list[str] = []

        self.chk_hex = QCheckBox("Hex")
        self.chk_hex.setChecked(True)
        self.chk_ascii = QCheckBox("ASCII")
        self.chk_ascii.setChecked(True)
        self.chk_ts = QCheckBox("时间戳")
        self.chk_ts.setChecked(True)
        self.btn_clear = QPushButton("清空")

        top = QHBoxLayout()
        top.addWidget(self.chk_hex)
        top.addWidget(self.chk_ascii)
        top.addWidget(self.chk_ts)
        top.addStretch(1)
        top.addWidget(self.btn_clear)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(self.MAX_BLOCKS)
        self.text.setFont(QFont("Consolas", 10))

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.text)

        self.btn_clear.clicked.connect(self.text.clear)

        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._flush)
        self._timer.start()

    def append(self, data: bytes, direction: str) -> None:
        parts: list[str] = []
        if self.chk_ts.isChecked():
            parts.append(datetime.now().strftime("[%H:%M:%S.%f")[:12] + "]")
        parts.append(f"[{direction}]")
        if self.chk_hex.isChecked():
            parts.append(data.hex(" ").upper())
        if self.chk_ascii.isChecked():
            parts.append("| " + ascii_repr(data))
        self._pending.append(" ".join(parts))

    def _flush(self) -> None:
        if not self._pending:
            return
        lines = "\n".join(self._pending)
        self._pending.clear()
        self.text.appendPlainText(lines)
        sb = self.text.verticalScrollBar()
        sb.setValue(sb.maximum())
