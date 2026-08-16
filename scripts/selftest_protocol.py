"""协议层自测：CRC 校验值、帧往返、流式解析、容错、指标、导出。

运行：.\.venv\Scripts\python.exe scripts\selftest_protocol.py
"""
from __future__ import annotations

import os
import sys
import tempfile

# 让脚本可直接从项目根运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.protocol.crc import crc16_modbus  # noqa: E402
from app.protocol.frame import Frame, FrameParser  # noqa: E402
from app.analysis.metrics import QualityMetrics  # noqa: E402
from app.storage.export import ExportEntry, export_csv, export_log  # noqa: E402


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        raise SystemExit(1)


def main() -> None:
    # 1. CRC16-MODBUS 标准校验值 "123456789" -> 0x4B37
    crc = crc16_modbus(b"123456789")
    check("CRC16-MODBUS 标准向量 0x4B37", crc == 0x4B37, f"got 0x{crc:04X}")

    # 2. 帧往返
    f = Frame(cmd=0x21, seq=7, payload=bytes(range(16)))
    raw = f.encode()
    decoded = FrameParser().feed(raw)
    check("帧往返 encode→decode", len(decoded) == 1 and decoded[0] == f,
          f"cmd={decoded[0].cmd if decoded else None}")

    # 3. 分片喂入（模拟串口拆包）
    p = FrameParser()
    frames = []
    for i in range(0, len(raw), 3):
        frames += p.feed(raw[i : i + 3])
    check("分片流式解析", len(frames) == 1 and frames[0] == f, f"n={len(frames)}")

    # 4. 噪声前缀重同步
    p = FrameParser()
    frames = p.feed(b"\x00\xff" + raw)
    check("噪声前缀重同步", len(frames) == 1 and frames[0] == f)

    # 5. 多帧连续 + 中间坏帧
    p = FrameParser()
    good1 = Frame(cmd=0x10, seq=1, payload=b"a").encode()
    bad = bytearray(Frame(cmd=0x10, seq=2, payload=b"b").encode())
    bad[-1] ^= 0xFF  # 破坏 CRC 末字节
    good2 = Frame(cmd=0x10, seq=3, payload=b"c").encode()
    frames = p.feed(good1 + bad + good2)
    check("坏帧跳过 + 后续帧可解", len(frames) == 2 and p.crc_errors == 1,
          f"n={len(frames)} crc_err={p.crc_errors}")

    # 6. 长度越界容错（喂足 9 字节最小帧才进入解析循环）
    p = FrameParser()
    over = b"\xaa\x55" + b"\x01" + b"\x01\x00" + b"\x00\x10" + b"\x00\x00"  # LEN=0x1000 超上限
    frames = p.feed(over)
    check("超长帧标记", p.length_errors == 1 and len(frames) == 0,
          f"len_err={p.length_errors}")

    # 7. 质量指标
    m = QualityMetrics()
    for _ in range(10):
        m.record_frame()
    m.record_frame_error("crc")
    m.record_frame_error("seq_gap")
    m.mark_sent(1)
    import time
    time.sleep(0.01)
    ms = m.mark_echo(1)
    check("丢帧率", abs(m.loss_rate - 1 / 11) < 1e-9, f"loss={m.loss_rate:.4f}")
    check("错误率", abs(m.error_rate - 1 / 11) < 1e-9, f"err={m.error_rate:.4f}")
    check("回环延迟可测", ms is not None and ms > 0, f"{ms:.1f}ms")

    # 8. 导出
    entries = [ExportEntry(ts=1_700_000_000.0, direction="RX", data=b"Hi\x00\xff")]
    with tempfile.TemporaryDirectory() as d:
        c = os.path.join(d, "out.csv")
        l = os.path.join(d, "out.log")
        export_csv(c, entries)
        export_log(l, entries)
        check("CSV 导出", os.path.getsize(c) > 0)
        check("日志导出", os.path.getsize(l) > 0 and b"Hi" in open(l, "rb").read())

    print("\n全部自测通过 [OK]")


if __name__ == "__main__":
    main()
