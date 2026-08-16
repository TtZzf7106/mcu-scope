"""payload 编解码往返自测。

运行：.\.venv\Scripts\python.exe scripts\selftest_payloads.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.protocol import payloads as P  # noqa: E402


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        raise SystemExit(1)


def rt(obj) -> object:
    """pack 后按同类型 unpack，返回还原对象。"""
    raw = obj.pack()
    return type(obj).unpack(raw)


def main() -> None:
    # EVENT
    e = P.Event(channel=P.CH_I2C, direction=P.DIR_RX, ts_us=0x12345678, data=b"\x01\x02\xFF")
    e2 = rt(e)
    check("EVENT 往返", e2 == e, f"{e2}")

    # ACK
    a = P.Ack(ack_cmd=0x21, status=P.STATUS_OK, req_seq=7, data=b"\x68\x69")
    check("ACK 往返", rt(a) == a)

    # ERROR
    er = P.Error(code=P.ERR_BUS, data=b"")
    check("ERROR 往返", rt(er) == er)

    # UART_CFG
    u = P.UartCfg(baud=115200, data_bits=8, parity=P.PARITY_NONE, stop_bits=1)
    check("UART_CFG 往返", rt(u) == u)

    # I2C
    iw = P.I2cWrite(addr7=0x50, data=b"\x00\x01\x02")
    ir = P.I2cRead(addr7=0x50, length=16)
    check("I2C_WRITE 往返", rt(iw) == iw)
    check("I2C_READ 往返", rt(ir) == ir)

    # SPI
    sc = P.SpiCfg(speed_hz=1_000_000, mode=0, bit_order=0)
    st = P.SpiTransfer(cs_pin=0, data=b"\xAA\xBB")
    check("SPI_CFG 往返", rt(sc) == sc)
    check("SPI_TRANSFER 往返", rt(st) == st)

    # LOGIC
    lc = P.LogicCfg(sample_rate_hz=1_000_000, channel_mask=0x0F, trigger_ch=0, trigger_edge=1)
    ld = P.LogicData(block_seq=7, samples=bytes(range(16)))
    check("LOGIC_CFG 往返", rt(lc) == lc)
    check("LOGIC_DATA 往返", rt(ld) == ld)

    # 边界：过短报错
    try:
        P.Event.unpack(b"\x00\x01")
        check("过短报错", False, "未抛异常")
    except ValueError:
        check("过短报错", True)

    # 交叉验证用：打印 EVENT / UART_CFG 的 hex
    print(f"\nEVENT_HEX:   {e.pack().hex().upper()}")
    print(f"UARTCFG_HEX: {u.pack().hex().upper()}")

    print("\npayload 编解码自测全部通过 [OK]")


if __name__ == "__main__":
    main()
