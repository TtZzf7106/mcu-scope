"""连接与发送面板。"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..link.serial_link import SerialLink

BAUDRATES = ["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"]
DATA_BITS = ["5", "6", "7", "8"]
PARITIES = {"None": "N", "Even": "E", "Odd": "O", "Mark": "M", "Space": "S"}
STOP_BITS = {"1": 1, "1.5": 1.5, "2": 2}
LINE_ENDINGS = {"无": b"", "LF (\\n)": b"\n", "CR (\\r)": b"\r", "CRLF": b"\r\n"}
_HEX_CHARS = set("0123456789abcdefABCDEF")


class ConnectionPanel(QWidget):
    """串口参数配置 + 数据发送。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self.refresh_ports()

    def _build_ui(self) -> None:
        conn = QGroupBox("连接")
        grid = QGridLayout()

        self.cmb_port = QComboBox()
        self.btn_refresh = QPushButton("刷新")

        self.cmb_baud = QComboBox()
        self.cmb_baud.setEditable(True)
        self.cmb_baud.addItems(BAUDRATES)
        self.cmb_baud.setCurrentText("115200")

        self.cmb_data = QComboBox()
        self.cmb_data.addItems(DATA_BITS)
        self.cmb_data.setCurrentText("8")

        self.cmb_parity = QComboBox()
        self.cmb_parity.addItems(list(PARITIES.keys()))

        self.cmb_stop = QComboBox()
        self.cmb_stop.addItems(list(STOP_BITS.keys()))

        self.btn_open = QPushButton("打开")
        self.btn_open.setCheckable(True)

        grid.addWidget(QLabel("串口"), 0, 0)
        grid.addWidget(self.cmb_port, 0, 1, 1, 2)
        grid.addWidget(self.btn_refresh, 0, 3)
        grid.addWidget(QLabel("波特率"), 1, 0)
        grid.addWidget(self.cmb_baud, 1, 1)
        grid.addWidget(QLabel("数据位"), 1, 2)
        grid.addWidget(self.cmb_data, 1, 3)
        grid.addWidget(QLabel("校验"), 2, 0)
        grid.addWidget(self.cmb_parity, 2, 1)
        grid.addWidget(QLabel("停止位"), 2, 2)
        grid.addWidget(self.cmb_stop, 2, 3)
        grid.addWidget(self.btn_open, 3, 0, 1, 4)
        conn.setLayout(grid)

        send = QGroupBox("发送")
        sgrid = QGridLayout()
        self.edt_send = QLineEdit()
        self.chk_hex_send = QCheckBox("Hex 发送")
        self.cmb_eol = QComboBox()
        self.cmb_eol.addItems(list(LINE_ENDINGS.keys()))
        self.btn_send = QPushButton("发送")

        sgrid.addWidget(self.edt_send, 0, 0, 1, 3)
        sgrid.addWidget(self.chk_hex_send, 1, 0)
        sgrid.addWidget(QLabel("行尾"), 1, 1)
        sgrid.addWidget(self.cmb_eol, 1, 2)
        sgrid.addWidget(self.btn_send, 2, 0, 1, 3)
        send.setLayout(sgrid)

        layout = QVBoxLayout(self)
        layout.addWidget(conn)
        layout.addWidget(send)
        layout.addStretch(1)

        self.btn_refresh.clicked.connect(self.refresh_ports)
        self.edt_send.returnPressed.connect(self.btn_send.click)

    # ---- port list ----
    def refresh_ports(self) -> None:
        current = self.cmb_port.currentData()
        self.cmb_port.clear()
        for info in SerialLink.list_ports():
            self.cmb_port.addItem(info.label(), info.device)
        if current:
            idx = self.cmb_port.findData(current)
            if idx >= 0:
                self.cmb_port.setCurrentIndex(idx)

    # ---- params ----
    def current_port(self) -> str:
        return self.cmb_port.currentData() or self.cmb_port.currentText()

    def current_params(self) -> dict:
        baud_text = self.cmb_baud.currentText().strip()
        baud = int(baud_text) if baud_text.isdigit() else 115200
        return {
            "port": self.current_port(),
            "baudrate": baud,
            "bytesize": int(self.cmb_data.currentText()),
            "parity": PARITIES[self.cmb_parity.currentText()],
            "stopbits": STOP_BITS[self.cmb_stop.currentText()],
        }

    # ---- send payload ----
    def build_payload(self) -> tuple[bytes | None, str | None]:
        """返回 (payload, 错误信息)。失败时 payload 为 None。"""
        text = self.edt_send.text()
        if self.chk_hex_send.isChecked():
            hexstr = "".join(text.split())
            if len(hexstr) % 2 != 0:
                return None, "Hex 长度必须为偶数"
            if any(c not in _HEX_CHARS for c in hexstr):
                return None, "Hex 含非法字符"
            payload = bytes.fromhex(hexstr)
        else:
            payload = text.encode("utf-8")
        payload += LINE_ENDINGS[self.cmb_eol.currentText()]
        return payload, None

    def set_connected(self, connected: bool) -> None:
        self.btn_open.setChecked(connected)
        self.btn_open.setText("关闭" if connected else "打开")
