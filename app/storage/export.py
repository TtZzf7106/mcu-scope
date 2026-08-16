"""数据导出：CSV / 文本日志。"""
from __future__ import annotations

import csv
import time
from datetime import datetime


class ExportEntry:
    """一条收发记录。ts 为 wall-clock 秒（time.time()）。"""

    __slots__ = ("ts", "direction", "data")

    def __init__(self, ts: float, direction: str, data: bytes) -> None:
        self.ts = ts
        self.direction = direction
        self.data = data


def ascii_repr(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b < 127 else "." for b in data)


def export_csv(path: str, entries: list[ExportEntry]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "direction", "hex", "ascii"])
        for e in entries:
            w.writerow(
                [datetime.fromtimestamp(e.ts).strftime("%H:%M:%S.%f")[:-3],
                 e.direction, e.data.hex(" ").upper(), ascii_repr(e.data)]
            )


def export_log(path: str, entries: list[ExportEntry]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for e in entries:
            dt = datetime.fromtimestamp(e.ts).strftime("%H:%M:%S.%f")[:-3]
            f.write(f"[{dt}] [{e.direction}] {e.data.hex(' ').upper()} | {ascii_repr(e.data)}\n")
