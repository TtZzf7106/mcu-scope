"""桥接协议帧编解码与流式解析。

帧格式（多字节小端）：
    [SOF 0xAA 0x55][CMD 1B][SEQ 2B][LEN 2B][PAYLOAD LEN 字节][CRC16 2B]

CRC16-MODBUS 覆盖 CMD..PAYLOAD（不含 SOF）。SEQ 由发送方递增，接收方据此
检测丢帧（数据完整性指标）。
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

from .crc import crc16_modbus

SOF = b"\xaa\x55"
SOF_B0 = 0xAA
SOF_B1 = 0x55
HEADER_LEN = 2 + 1 + 2 + 2  # SOF + CMD + SEQ + LEN = 7
CRC_LEN = 2
MIN_FRAME_LEN = HEADER_LEN + CRC_LEN
MAX_PAYLOAD = 2048


@dataclass
class Frame:
    cmd: int
    seq: int = 0
    payload: bytes = b""

    def encode(self) -> bytes:
        if not (0 <= self.cmd <= 0xFF):
            raise ValueError("cmd 越界")
        if not (0 <= self.seq <= 0xFFFF):
            raise ValueError("seq 越界")
        if len(self.payload) > MAX_PAYLOAD:
            raise ValueError(f"payload 过长: {len(self.payload)} > {MAX_PAYLOAD}")
        body = struct.pack("<BHH", self.cmd, self.seq, len(self.payload)) + self.payload
        crc = crc16_modbus(body)
        return SOF + body + struct.pack("<H", crc)


class FrameParser:
    """从字节流提取帧：SOF 同步 + 长度边界 + CRC 校验。

    CRC 错误 / 长度越界时丢弃一个字节重新同步，并累计错误计数。
    """

    def __init__(self) -> None:
        self.buffer = bytearray()
        self.crc_errors = 0
        self.length_errors = 0

    def feed(self, data: bytes) -> list[Frame]:
        self.buffer += data
        out: list[Frame] = []
        while len(self.buffer) >= MIN_FRAME_LEN:
            if self.buffer[0] != SOF_B0 or self.buffer[1] != SOF_B1:
                del self.buffer[0]  # 未对齐，逐字节滑动找 SOF
                continue

            cmd = self.buffer[2]
            seq = struct.unpack_from("<H", self.buffer, 3)[0]
            length = struct.unpack_from("<H", self.buffer, 5)[0]

            if length > MAX_PAYLOAD:
                self.length_errors += 1
                del self.buffer[0]
                continue

            total = HEADER_LEN + length + CRC_LEN
            if len(self.buffer) < total:
                break  # 数据不足，等下一包

            body = bytes(self.buffer[2 : 2 + 1 + 2 + 2 + length])  # CMD..PAYLOAD
            crc_recv = struct.unpack_from("<H", self.buffer, HEADER_LEN + length)[0]
            if crc_recv != crc16_modbus(body):
                self.crc_errors += 1
                del self.buffer[0]
                continue

            payload = bytes(self.buffer[HEADER_LEN : HEADER_LEN + length])
            out.append(Frame(cmd=cmd, seq=seq, payload=payload))
            del self.buffer[:total]
        return out

    def reset(self) -> None:
        self.buffer.clear()
        self.crc_errors = 0
        self.length_errors = 0
