"""桥接会话层：把 BridgeLink 的帧事件接到质量指标/数据/波形。

这是 M3/M4 的宿主侧数据通路：ACK→延迟相关、ERROR→协议错误计数、
EVENT→实时数据、LOGIC_DATA→波形采样。桥接硬件到位后，UI 挂上本类即可。
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from ..analysis.metrics import QualityMetrics
from ..protocol import payloads as P
from ..protocol.commands import Cmd
from ..protocol.frame import Frame
from .bridge_link import BridgeLink


class BridgeSession(QObject):
    """高层桥接操作 + 帧分发。"""

    data_event = Signal(int, int, int, bytes)   # channel, dir, ts_us, data
    logic_data = Signal(int, bytes)             # block_seq, samples
    ack_received = Signal(object)               # P.Ack
    error_received = Signal(object)             # P.Error

    def __init__(self, link: BridgeLink | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.link = link or BridgeLink()
        self.metrics = QualityMetrics()
        self.logic_rate = 0      # 最近一次 LOGIC_CFG 的采样率
        self.logic_mask = 0xFF   # 最近一次 LOGIC_CFG 的通道掩码
        self.link.frame_received.connect(self._on_frame)
        self.link.frame_error.connect(self._on_frame_error)

    # ---- 命令发送（返回 Frame，其 seq 用于延迟相关）----
    def send(self, cmd: int, payload: bytes = b"") -> Frame:
        frame = self.link.send(cmd, payload)
        self.metrics.mark_sent(frame.seq)
        return frame

    def ping(self) -> Frame:
        return self.send(Cmd.PING)

    def uart_cfg(self, baud: int, data_bits: int = 8, parity: int = 0, stop_bits: int = 1) -> Frame:
        return self.send(Cmd.UART_CFG, P.UartCfg(baud, data_bits, parity, stop_bits).pack())

    def uart_write(self, data: bytes) -> Frame:
        return self.send(Cmd.UART_WRITE, data)

    def uart_listen(self, enable: bool) -> Frame:
        return self.send(Cmd.UART_LISTEN, bytes([1 if enable else 0]))

    def i2c_scan(self) -> Frame:
        return self.send(Cmd.I2C_SCAN)

    def i2c_write(self, addr7: int, data: bytes) -> Frame:
        return self.send(Cmd.I2C_WRITE, P.I2cWrite(addr7, data).pack())

    def i2c_read(self, addr7: int, length: int) -> Frame:
        return self.send(Cmd.I2C_READ, P.I2cRead(addr7, length).pack())

    def spi_cfg(self, speed_hz: int, mode: int = 0, bit_order: int = 0) -> Frame:
        return self.send(Cmd.SPI_CFG, P.SpiCfg(speed_hz, mode, bit_order).pack())

    def spi_transfer(self, cs: int, data: bytes) -> Frame:
        return self.send(Cmd.SPI_TRANSFER, P.SpiTransfer(cs, data).pack())

    def logic_cfg(self, rate_hz: int, mask: int, trig_ch: int = 0, trig_edge: int = 0) -> Frame:
        self.logic_rate = rate_hz
        self.logic_mask = mask
        return self.send(Cmd.LOGIC_CFG, P.LogicCfg(rate_hz, mask, trig_ch, trig_edge).pack())

    def logic_start(self) -> Frame:
        return self.send(Cmd.LOGIC_START)

    def logic_stop(self) -> Frame:
        return self.send(Cmd.LOGIC_STOP)

    # ---- 帧分发 ----
    def _on_frame_error(self, kind: str) -> None:
        self.metrics.record_frame_error(kind)

    def _on_frame(self, frame: Frame) -> None:
        self.metrics.record_frame()
        if frame.cmd == Cmd.ACK:
            try:
                ack = P.Ack.unpack(frame.payload)
            except ValueError:
                return
            self.metrics.mark_echo(ack.req_seq)
            self.ack_received.emit(ack)
        elif frame.cmd == Cmd.ERROR:
            try:
                err = P.Error.unpack(frame.payload)
            except ValueError:
                return
            self.metrics.record_frame_error("protocol")
            self.error_received.emit(err)
        elif frame.cmd == Cmd.EVENT:
            try:
                ev = P.Event.unpack(frame.payload)
            except ValueError:
                return
            self.data_event.emit(ev.channel, ev.direction, ev.ts_us, ev.data)
        elif frame.cmd == Cmd.LOGIC_DATA:
            try:
                ld = P.LogicData.unpack(frame.payload)
            except ValueError:
                return
            self.logic_data.emit(ld.block_seq, ld.samples)
