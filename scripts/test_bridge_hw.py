"""桥接固件实机端到端测试（无需第二块板子）。

前提：目标板已烧入 bridge_reg/firmware.hex，CH340 接 USART1(PA9/PA10)。
用真实 BridgeSession（非 mock）通过串口与桥接固件对话，验证协议栈。

运行：.\.venv\Scripts\python.exe scripts\test_bridge_hw.py [COM口]
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QCoreApplication

from app.link.bridge_link import BridgeLink
from app.link.bridge_session import BridgeSession
from app.link.serial_link import SerialLink
from app.protocol.commands import Cmd


def main() -> int:
    port = sys.argv[1] if len(sys.argv) > 1 else "COM8"
    app = QCoreApplication(sys.argv)

    serial = SerialLink()
    sess = BridgeSession(BridgeLink(serial))

    acks: list = []
    errs: list = []
    sess.ack_received.connect(lambda a: acks.append(a))
    sess.error_received.connect(lambda e: errs.append(e))

    serial.open(port, baudrate=115200)
    time.sleep(0.5)  # 等串口/固件稳定

    def wait_for(fn, timeout: float = 2.0) -> bool:
        t0 = time.time()
        while time.time() - t0 < timeout:
            app.processEvents()
            if fn():
                return True
            time.sleep(0.01)
        return False

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
        if not ok:
            raise SystemExit(1)

    # 1. PING → ACK(版本 1.0)
    acks.clear()
    sess.ping()
    ok = wait_for(lambda: len(acks) >= 1, 2.0)
    check("PING → ACK", ok and acks[0].ack_cmd == Cmd.PING and acks[0].status == 0
          and acks[0].data == b"\x01\x00", f"ack={acks[0] if acks else None}")

    # 2. UART_CFG → ACK
    acks.clear()
    sess.uart_cfg(115200)
    ok = wait_for(lambda: len(acks) >= 1, 2.0)
    check("UART_CFG → ACK", ok and acks[0].ack_cmd == Cmd.UART_CFG and acks[0].status == 0)

    # 3. UART_WRITE → ACK
    acks.clear()
    sess.uart_write(b"\x41\x42\x43")
    ok = wait_for(lambda: len(acks) >= 1, 2.0)
    check("UART_WRITE → ACK", ok and acks[0].ack_cmd == Cmd.UART_WRITE and acks[0].status == 0)

    # 4. 未知命令 → ERROR(UNKNOWN_CMD=0)
    errs.clear()
    sess.send(0xEE)
    ok = wait_for(lambda: len(errs) >= 1, 2.0)
    check("未知命令 → ERROR", ok and errs[0].code == 0, f"err={errs[0] if errs else None}")

    # 5. I2C_SCAN → ACK（无设备/无上拉应安全返回，不挂死）
    acks.clear()
    sess.i2c_scan()
    ok = wait_for(lambda: len(acks) >= 1, 3.0)
    n = len(acks[0].data) if acks else -1
    check("I2C_SCAN → ACK（不挂死）", ok and acks[0].ack_cmd == Cmd.I2C_SCAN,
          f"发现 {n} 个地址")

    # 6. 帧/错误统计
    print(f"[信息] 收到帧 {sess.metrics.total_frames} · CRC错误 {sess.metrics.crc_errors} "
          f"· 丢帧 {sess.metrics.seq_gaps}")

    serial.close()
    print("\n桥接实机端到端测试通过 [OK]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
