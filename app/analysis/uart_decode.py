"""UART 逻辑采样解码：从数字波形通道还原字节。

输入：LogicCapture 的某一通道 + 已知波特率（采样率需每比特 >=3 点）。
算法：找起始位下降沿 → 采样起始位/8 数据位(LSB first)/停止位 → 还原字节，
并标记帧错误（停止位非高）。
"""
from __future__ import annotations

from dataclasses import dataclass

from .logic_capture import LogicCapture


@dataclass
class DecodedByte:
    value: int          # 数据字节
    start_t: float      # 起始位开始时间 (s)
    end_t: float        # 停止位结束时间 (s)
    framing_error: bool # 停止位非高（或无法验证）


def _sample_at(samples: list[int], idx: float) -> int | None:
    i = int(idx)
    if i < 0 or i >= len(samples):
        return None
    return samples[i]


def decode_uart(capture: LogicCapture, channel: int, baud: int) -> list[DecodedByte]:
    if channel < 0 or channel >= len(capture.names):
        raise ValueError(f"通道越界: {channel}")
    samples = [row[channel] for row in capture.samples]
    dt = capture.dt
    spb = (1.0 / baud) / dt  # 每比特采样点数
    if spb < 3.0:
        raise ValueError(f"采样率不足：每比特仅 {spb:.1f} 点（需 >=3）")

    results: list[DecodedByte] = []
    n = len(samples)
    i = 0
    while i < n:
        # 起始位：下降沿(1→0)，或帧从 0 开始
        if samples[i] == 0 and (i == 0 or samples[i - 1] == 1):
            if _sample_at(samples, i + spb * 0.5) == 0:  # 起始位中点应为 0
                value = 0
                ok = True
                for b in range(8):
                    bit = _sample_at(samples, i + spb * (b + 1.5))
                    if bit is None:
                        ok = False
                        break
                    if bit == 1:
                        value |= 1 << b
                if ok:
                    stop = _sample_at(samples, i + spb * 9.5)
                    framing = stop != 1
                    end_idx = int(i + spb * 10)
                    results.append(DecodedByte(value, i * dt, end_idx * dt, framing))
                    i = end_idx  # 停在下一位（可能紧邻下一帧起始位）
                    continue
        i += 1
    return results
