"""桥接协议传输层：在串口字节流之上收发帧。"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from ..protocol.frame import Frame, FrameParser
from .serial_link import SerialLink


class BridgeLink(QObject):
    """封装 SerialLink，提供帧级收发与完整性跟踪。

    SEQ 语义：下行（PC→桥）用本类维护的递增序号；上行（桥→PC）用桥自身的
    递增序号。本类只对上行帧做丢帧检测（`seq_gap`），因为只解析 RX 方向。
    """

    frame_received = Signal(object)   # Frame
    frame_error = Signal(str)         # 'crc' / 'length' / 'seq_gap'
    status_changed = Signal(bool)
    error_occurred = Signal(str)

    def __init__(self, serial: SerialLink | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.serial = serial or SerialLink(self)
        self.parser = FrameParser()
        self._seq = 0
        self._last_seq: int | None = None
        self.seq_gaps = 0

        self.serial.data_received.connect(self._on_bytes)
        self.serial.status_changed.connect(self.status_changed)
        self.serial.error_occurred.connect(self.error_occurred)

    # ---- lifecycle ----
    def open(self, port: str, baudrate: int = 115200, **kwargs) -> None:
        self.serial.open(port, baudrate=baudrate, **kwargs)

    def close(self) -> None:
        self.serial.close()

    @property
    def is_open(self) -> bool:
        return self.serial.is_open

    # ---- send ----
    def send(self, cmd: int, payload: bytes = b"") -> Frame:
        self._seq = (self._seq + 1) & 0xFFFF
        frame = Frame(cmd=cmd, seq=self._seq, payload=payload)
        self.serial.write(frame.encode())
        return frame

    # ---- receive ----
    def _on_bytes(self, data: bytes, direction: str) -> None:
        if direction != "RX":
            return
        crc_before = self.parser.crc_errors
        len_before = self.parser.length_errors
        frames = self.parser.feed(data)
        if self.parser.crc_errors > crc_before:
            self.frame_error.emit("crc")
        if self.parser.length_errors > len_before:
            self.frame_error.emit("length")
        for f in frames:
            if self._last_seq is not None:
                expected = (self._last_seq + 1) & 0xFFFF
                if f.seq != expected:
                    self.seq_gaps += 1
                    self.frame_error.emit("seq_gap")
            self._last_seq = f.seq
            self.frame_received.emit(f)
