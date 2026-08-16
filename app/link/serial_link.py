"""UART 串口连接层。

封装 pyserial：在后台线程持续读取，通过 Qt 信号把数据/事件抛给 UI，
避免阻塞界面。M2 起新增 bridge_link.py 承载桥接协议帧。
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import serial
import serial.tools.list_ports
from PySide6.QtCore import QObject, Signal


@dataclass(frozen=True)
class PortInfo:
    """串口信息，label 供下拉框显示，device 供 open() 使用。"""

    device: str
    description: str
    hwid: str

    def label(self) -> str:
        if self.description and self.description != "n/a":
            return f"{self.device} — {self.description}"
        return self.device


class SerialLink(QObject):
    """串口读写管理器（后台线程读取）。"""

    data_received = Signal(bytes, str)  # payload, direction('RX'/'TX')
    status_changed = Signal(bool)       # connected True/False
    error_occurred = Signal(str)        # human-readable error

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._serial: serial.Serial | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    # ---- port discovery ----
    @staticmethod
    def list_ports() -> list[PortInfo]:
        result: list[PortInfo] = []
        try:
            comports = serial.tools.list_ports.comports()
        except Exception:  # noqa: BLE001
            return result
        for p in comports:
            result.append(
                PortInfo(device=p.device, description=p.description or "", hwid=p.hwid or "")
            )
        return result

    # ---- lifecycle ----
    def open(
        self,
        port: str,
        baudrate: int = 115200,
        bytesize: int = 8,
        parity: str = "N",
        stopbits: float = 1,
        timeout: float = 0.1,
    ) -> None:
        self.close()
        try:
            self._serial = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                timeout=timeout,
            )
        except Exception as exc:  # noqa: BLE001
            self._serial = None
            self.error_occurred.emit(f"打开串口失败：{exc}")
            return

        self._stop.clear()
        self._thread = threading.Thread(target=self._read_loop, name="serial-reader", daemon=True)
        self._thread.start()
        self.status_changed.emit(True)

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        with self._lock:
            if self._serial is not None:
                try:
                    self._serial.close()
                except Exception:  # noqa: BLE001
                    pass
                self._serial = None
        self.status_changed.emit(False)

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._serial is not None and self._serial.is_open

    # ---- write ----
    def write(self, data: bytes) -> int:
        """写入并立即回显为 TX 事件。返回实际写入字节数。"""
        with self._lock:
            if self._serial is None or not self._serial.is_open:
                self.error_occurred.emit("串口未打开")
                return 0
            try:
                n = self._serial.write(data)
            except Exception as exc:  # noqa: BLE001
                self.error_occurred.emit(f"发送失败：{exc}")
                return 0
        if n:
            self.data_received.emit(bytes(data[:n]), "TX")
        return n

    # ---- background reader ----
    def _read_loop(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                ser = self._serial
            if ser is None:
                break
            try:
                waiting = ser.in_waiting
            except Exception:  # noqa: BLE001
                time.sleep(0.01)
                continue
            if waiting > 0:
                try:
                    chunk = ser.read(waiting)
                except Exception as exc:  # noqa: BLE001
                    if not self._stop.is_set():
                        self.error_occurred.emit(f"读取失败：{exc}")
                    break
                if chunk:
                    self.data_received.emit(bytes(chunk), "RX")
            else:
                time.sleep(0.005)
