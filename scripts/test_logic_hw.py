"""逻辑抓取实机自测：LOGIC_START 抓取自测方波，经 LOGIC_DATA 回传并校验。

运行：.\.venv\Scripts\python.exe scripts\test_logic_hw.py [COM口]
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QCoreApplication  # noqa: E402

from app.link.bridge_link import BridgeLink  # noqa: E402
from app.link.bridge_session import BridgeSession  # noqa: E402
from app.link.serial_link import SerialLink  # noqa: E402


def main() -> int:
    port = sys.argv[1] if len(sys.argv) > 1 else "COM8"
    app = QCoreApplication(sys.argv)
    ser = SerialLink()
    sess = BridgeSession(BridgeLink(ser))

    logics: list = []
    sess.logic_data.connect(lambda s, b: logics.append((s, b)))
    ser.open(port, baudrate=115200)
    time.sleep(0.5)

    def pump_until(fn, timeout: float) -> bool:
        t0 = time.time()
        while time.time() - t0 < timeout:
            app.processEvents()
            if fn():
                return True
            time.sleep(0.01)
        return False

    # 配置：100kHz 采样，通道掩码 0x01（PA0）
    sess.logic_cfg(100000, 0x01)
    time.sleep(0.2)

    # 启动抓取（固件阻塞 ~20ms 抓 2000 样本 + 自测方波）
    sess.logic_start()
    ok = pump_until(lambda: len(logics) >= 1, 3.0)
    assert ok, "未收到 LOGIC_DATA"

    seq, samples = logics[0]
    n = len(samples)
    print(f"[信息] 收到 LOGIC_DATA: block_seq={seq}, 样本数={n}")

    ones = samples.count(1)
    zeros = samples.count(0)
    first_high = all(b == 1 for b in samples[:50])
    first_low = all(b == 0 for b in samples[50:100])

    print(f"[{'PASS' if n == 2000 else 'FAIL'}] 样本数=2000")
    print(f"[{'PASS' if ones > 0 and zeros > 0 else 'FAIL'}] 含 0/1 跳变 (1:{ones}, 0:{zeros})")
    print(f"[{'PASS' if first_high else 'FAIL'}] 前 50 样本为高")
    print(f"[{'PASS' if first_low else 'FAIL'}] 后 50 样本为低")

    ok = n == 2000 and ones > 0 and zeros > 0 and first_high and first_low
    ser.close()
    if not ok:
        print("\n逻辑抓取自测失败")
        return 1
    print("\n逻辑抓取自测通过 [OK]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
