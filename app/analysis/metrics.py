"""传输质量指标：错误计数、数据完整性、延迟。"""
from __future__ import annotations

import time
from collections import deque


class QualityMetrics:
    """桥接链路的传输质量账本。

    - 协议层错误：crc / length / seq_gap / protocol（桥回传的 NACK 等）
    - 数据完整性：丢帧率（seq_gap）、错误率
    - 延迟：请求-应答往返时间（回环测延迟，M3 起）
    """

    def __init__(self, latency_maxlen: int = 4000) -> None:
        self.total_frames = 0
        self.crc_errors = 0
        self.length_errors = 0
        self.seq_gaps = 0
        self.protocol_errors = 0
        self.latency_samples: deque[tuple[float, float]] = deque(maxlen=latency_maxlen)
        self._pending_echo: dict[int, float] = {}

    def record_frame(self) -> None:
        self.total_frames += 1

    def record_frame_error(self, kind: str) -> None:
        if kind == "crc":
            self.crc_errors += 1
        elif kind == "length":
            self.length_errors += 1
        elif kind == "seq_gap":
            self.seq_gaps += 1
        elif kind == "protocol":
            self.protocol_errors += 1

    # ---- 回环延迟 ----
    def mark_sent(self, seq: int) -> None:
        self._pending_echo[seq] = time.perf_counter()

    def mark_echo(self, seq: int) -> float | None:
        """收到应答，返回往返毫秒；无对应请求则返回 None。"""
        t0 = self._pending_echo.pop(seq, None)
        if t0 is None:
            return None
        ms = (time.perf_counter() - t0) * 1000.0
        self.latency_samples.append((time.perf_counter(), ms))
        return ms

    # ---- 派生指标 ----
    @property
    def loss_rate(self) -> float:
        if self.total_frames == 0:
            return 0.0
        return self.seq_gaps / (self.total_frames + self.seq_gaps)

    @property
    def error_rate(self) -> float:
        total_errors = self.crc_errors + self.length_errors + self.protocol_errors
        if self.total_frames == 0:
            return 0.0
        return total_errors / (self.total_frames + total_errors)

    def recent_latencies(self, window_s: float = 30.0) -> list[float]:
        cutoff = time.perf_counter() - window_s
        while self.latency_samples and self.latency_samples[0][0] < cutoff:
            self.latency_samples.popleft()
        return [ms for _, ms in self.latency_samples]

    def reset(self) -> None:
        self.total_frames = 0
        self.crc_errors = 0
        self.length_errors = 0
        self.seq_gaps = 0
        self.protocol_errors = 0
        self.latency_samples.clear()
        self._pending_echo.clear()
