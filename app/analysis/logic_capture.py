"""数字波形捕获模型。

M4 桥接固件经 LOGIC_DATA 事件回传采样；此处提供数据模型与示例生成器，
供波形视图渲染。采样为固定周期、每周期每通道一个 0/1 电平。
"""
from __future__ import annotations


class LogicCapture:
    def __init__(self, channel_names: list[str], sample_period_s: float) -> None:
        self.names = list(channel_names)
        self.dt = sample_period_s
        # samples[k][c] = 0/1，k 为采样序号
        self.samples: list[list[int]] = []

    def add(self, levels: list[int]) -> None:
        if len(levels) != len(self.names):
            raise ValueError(f"通道数不匹配: {len(levels)} != {len(self.names)}")
        self.samples.append([int(l) for l in levels])

    @property
    def duration(self) -> float:
        return len(self.samples) * self.dt

    def channel_series(self, channel: int) -> tuple[list[float], list[float]]:
        """返回通道的阶梯 (x, y) 序列（y 为 0/1），用于绘制直角方波。"""
        xs: list[float] = []
        ys: list[float] = []
        dt = self.dt
        for k, row in enumerate(self.samples):
            lvl = row[channel]
            xs.append(k * dt)
            ys.append(float(lvl))
            xs.append((k + 1) * dt)
            ys.append(float(lvl))
        return xs, ys

    def sample_count(self) -> int:
        return len(self.samples)


def from_bitmap(samples: bytes, sample_period_s: float,
                channel_names: list[str]) -> LogicCapture:
    """从 LOGIC_DATA 的位图样本构造 LogicCapture（每字节 bit i = 通道 i 电平）。"""
    cap = LogicCapture(channel_names, sample_period_s)
    for byte in samples:
        cap.add([(byte >> i) & 1 for i in range(len(channel_names))])
    return cap


def demo_uart() -> LogicCapture:
    """示例：通道0 = UART 发送 'A'(0x41) @115200，通道1 = 分频方波。"""
    baud = 115200
    dt = 1.0 / (baud * 16)  # 16x 过采样
    cap = LogicCapture(["UART_TX", "CLK"], dt)
    # start=0, 0x41 LSB-first = 1,0,0,0,0,0,1,0, stop=1
    bits = [0, 1, 0, 0, 0, 0, 0, 1, 0, 1]
    for bit in bits:
        for _ in range(16):
            cap.add([bit, 1])
    # 空闲高电平 + 时钟分频翻转
    for k in range(240):
        cap.add([1, (k // 20) % 2])
    return cap
