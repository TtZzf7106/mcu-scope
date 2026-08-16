"""吞吐率统计。

M1 只统计字节速率与累计量；协议错误/时序/延迟等指标在 M3 由桥接固件回传后补充。
"""
from __future__ import annotations

import time
from collections import deque


class SessionStats:
    """滚动窗口吞吐统计 + 累计字节。"""

    def __init__(self, window: float = 1.0, history_len: int = 600) -> None:
        self.window = window
        self.history_len = history_len
        self.total_rx = 0
        self.total_tx = 0
        self._rx_events: deque[tuple[float, int]] = deque()
        self._tx_events: deque[tuple[float, int]] = deque()
        # 绘图历史（相对时间从第一个样本起）
        self.times: list[float] = []
        self.rx_rates: list[float] = []
        self.tx_rates: list[float] = []

    def add(self, n: int, direction: str) -> None:
        now = time.monotonic()
        if direction == "RX":
            self.total_rx += n
            self._rx_events.append((now, n))
        else:
            self.total_tx += n
            self._tx_events.append((now, n))

    def sample(self) -> tuple[float, float, float]:
        """采集一次速率样本，返回 (now, rx_rate, tx_rate) 字节/秒。"""
        now = time.monotonic()
        cutoff = now - self.window
        self._trim(self._rx_events, cutoff)
        self._trim(self._tx_events, cutoff)
        rx = sum(n for _, n in self._rx_events) / self.window
        tx = sum(n for _, n in self._tx_events) / self.window
        self.times.append(now)
        self.rx_rates.append(rx)
        self.tx_rates.append(tx)
        if len(self.times) > self.history_len:
            drop = len(self.times) - self.history_len
            del self.times[:drop]
            del self.rx_rates[:drop]
            del self.tx_rates[:drop]
        return now, rx, tx

    @property
    def total_bytes(self) -> int:
        return self.total_rx + self.total_tx

    @staticmethod
    def _trim(buf: deque, cutoff: float) -> None:
        while buf and buf[0][0] < cutoff:
            buf.popleft()
