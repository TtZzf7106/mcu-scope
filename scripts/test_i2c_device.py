"""I2C 设备识别与测试（接好设备后运行）。

功能：
  1. 扫描 I2C 总线，列出所有从机地址；
  2. 对已知设备读 ID 寄存器，自动识别型号；
  3. AT24C02 EEPROM 写读回测试。

运行：.\.venv\Scripts\python.exe scripts\test_i2c_device.py [COM口]
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

# 已知设备：(地址, [ (名称, ID寄存器, 期望值), ... ])，ID 为 None 表示无 ID 寄存器
KNOWN = {
    0x68: [("MPU6050", 0x75, 0x68), ("MPU9250", 0x75, 0x71)],
    0x76: [("BMP280", 0xD0, 0x58), ("BME280", 0xD0, 0x60)],
    0x77: [("BMP280(alt)", 0xD0, 0x58)],
    0x1E: [("HMC5883L", 0x0A, 0x48)],
    0x18: [("LIS3DH", 0x0F, 0x33)],
    0x3C: [("SSD1306 OLED", None, None)],
    0x50: [("AT24Cxx EEPROM", None, None)],
}


def main() -> int:
    port = sys.argv[1] if len(sys.argv) > 1 else "COM8"
    app = QCoreApplication(sys.argv)
    ser = SerialLink()
    sess = BridgeSession(BridgeLink(ser))
    acks: list = []
    errs: list = []
    sess.ack_received.connect(lambda a: acks.append(a))
    sess.error_received.connect(lambda e: errs.append(e))
    ser.open(port, baudrate=115200)
    time.sleep(0.5)

    def wait_ack(timeout: float = 2.0):
        acks.clear()
        errs.clear()
        t0 = time.time()
        while time.time() - t0 < timeout:
            app.processEvents()
            if acks or errs:
                return acks[0] if acks else None
            time.sleep(0.01)
        return None

    # 1. 扫描
    sess.i2c_scan()
    ack = wait_ack(4.0)
    addrs = list(ack.data) if ack and ack.status == 0 else []
    print(f"[扫描] 发现 {len(addrs)} 个从机: "
          + (" ".join(f"0x{a:02X}" for a in addrs) if addrs else "（无，检查接线+上拉电阻）"))

    if not addrs:
        ser.close()
        print("未发现 I2C 设备。请确认：PB6=SCL、PB7=SDA、共地、3.3V、4.7kΩ 上拉。")
        return 0

    # 2. 识别已知设备
    for addr in addrs:
        if addr in KNOWN:
            for name, reg, expect in KNOWN[addr]:
                if reg is None:
                    print(f"[识别] 0x{addr:02X} 可能是 {name}（无 ID 寄存器）")
                    continue
                sess.i2c_write(addr, bytes([reg]))
                wait_ack(0.5)
                sess.i2c_read(addr, 1)
                ack = wait_ack(1.0)
                got = ack.data[0] if ack and ack.status == 0 and ack.data else None
                mark = "PASS" if got == expect else "FAIL"
                print(f"[{mark}] 0x{addr:02X} {name}: ID寄存器0x{reg:02X} "
                      f"= 0x{got:02X} (期望 0x{expect:02X})")
        else:
            print(f"[未知] 0x{addr:02X}（不在已知列表，可读寄存器进一步确认）")

    # 3. AT24Cxx EEPROM 写读回测试
    for a in addrs:
        if a in (0x50, 0x51, 0x52, 0x53):
            sess.i2c_write(a, bytes([0x00, 0x55]))
            wait_ack(0.5)
            time.sleep(0.01)
            sess.i2c_write(a, bytes([0x00]))  # 设读指针到地址 0
            wait_ack(0.5)
            sess.i2c_read(a, 1)
            ack = wait_ack(1.0)
            got = ack.data if ack and ack.status == 0 else None
            ok = got == b"\x55"
            print(f"[{'PASS' if ok else 'FAIL'}] 0x{a:02X} EEPROM 写0x55读回 "
                  f"{got.hex(' ').upper() if got else '无响应'}")

    ser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
