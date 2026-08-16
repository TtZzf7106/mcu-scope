"""桥接会话端到端自测（mock 串口）。

验证：命令发送→帧编码、ACK→延迟相关、EVENT→数据、ERROR→协议错误、
LOGIC_DATA→波形采样，全链路经 mock 串口往返。

运行：.\.venv\Scripts\python.exe scripts\selftest_bridge.py
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QObject, Signal  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.link.bridge_link import BridgeLink  # noqa: E402
from app.link.bridge_session import BridgeSession  # noqa: E402
from app.protocol import payloads as P  # noqa: E402
from app.protocol.commands import Cmd  # noqa: E402
from app.protocol.frame import Frame, FrameParser  # noqa: E402


class MockSerial(QObject):
    data_received = Signal(bytes, str)
    status_changed = Signal(bool)
    error_occurred = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.tx: list[bytes] = []
        self.open_state = True

    def write(self, data: bytes) -> int:
        b = bytes(data)
        self.tx.append(b)
        self.data_received.emit(b, "TX")
        return len(b)

    def open(self, *a, **k) -> None:
        self.open_state = True
        self.status_changed.emit(True)

    def close(self) -> None:
        self.open_state = False
        self.status_changed.emit(False)

    @property
    def is_open(self) -> bool:
        return self.open_state


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    app = QApplication(sys.argv)
    ser = MockSerial()
    sess = BridgeSession(BridgeLink(ser))

    acks: list = []
    errs: list = []
    datas: list = []
    logics: list = []
    sess.ack_received.connect(lambda a: acks.append(a))
    sess.error_received.connect(lambda e: errs.append(e))
    sess.data_event.connect(lambda c, d, t, b: datas.append((c, d, t, b)))
    sess.logic_data.connect(lambda s, b: logics.append((s, b)))

    # 1. ping 发送 → 写出 PING 帧
    f = sess.ping()
    check("ping 写出 1 帧", len(ser.tx) == 1)
    fr = FrameParser().feed(ser.tx[0])
    check("ping 帧 CMD=PING", len(fr) == 1 and fr[0].cmd == Cmd.PING)

    # 2. ACK → 延迟相关
    ack_bytes = Frame(Cmd.ACK, seq=1, payload=P.Ack(Cmd.PING, P.STATUS_OK, f.seq).pack()).encode()
    ser.data_received.emit(ack_bytes, "RX")
    check("ACK → 延迟 + 应答信号", len(sess.metrics.recent_latencies()) == 1 and len(acks) == 1)

    # 3. EVENT → 数据事件
    ev_bytes = Frame(Cmd.EVENT, seq=2, payload=P.Event(P.CH_UART, P.DIR_RX, 1234, b"\x41\x42").pack()).encode()
    ser.data_received.emit(ev_bytes, "RX")
    check("EVENT → 数据事件", len(datas) == 1 and datas[0][0] == P.CH_UART and datas[0][3] == b"\x41\x42")

    # 4. ERROR → 协议错误计数
    er_bytes = Frame(Cmd.ERROR, seq=3, payload=P.Error(P.ERR_BUS).pack()).encode()
    ser.data_received.emit(er_bytes, "RX")
    check("ERROR → 协议错误计数", sess.metrics.protocol_errors == 1 and len(errs) == 1)

    # 5. LOGIC_DATA → 波形采样
    ld_bytes = Frame(Cmd.LOGIC_DATA, seq=4, payload=P.LogicData(7, bytes([0b01, 0b10])).pack()).encode()
    ser.data_received.emit(ld_bytes, "RX")
    check("LOGIC_DATA → 波形采样", len(logics) == 1 and logics[0][0] == 7 and logics[0][1] == bytes([1, 2]))

    # 6. 帧数统计（4 个 RX 帧）
    check("帧数统计", sess.metrics.total_frames == 4, f"total={sess.metrics.total_frames}")

    print("\n桥接会话自测全部通过 [OK]")


if __name__ == "__main__":
    main()
