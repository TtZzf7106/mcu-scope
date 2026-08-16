# 桥接协议规范（M2）

## 帧格式

PC ↔ 桥接 STM32 之间通过 UART 传输的二进制帧（多字节字段一律**小端**）：

```
┌────────────┬────────┬────────┬────────┬──────────────┬─────────┐
│ SOF 2B     │ CMD 1B │ SEQ 2B │ LEN 2B │ PAYLOAD LEN B │ CRC16 2B│
│ AA 55      │        │        │        │              │         │
└────────────┴────────┴────────┴────────┴──────────────┴─────────┘
```

- **SOF**：固定 `0xAA 0x55`，用于字节流同步。
- **CMD**：命令/事件 ID，见下文命令表。
- **SEQ**：发送方递增序号（0..65535 回绕），接收方据此检测丢帧。
- **LEN**：PAYLOAD 长度（0..2048）。
- **CRC16**：CRC16-MODBUS（poly=0x8005 反射 0xA001，init=0xFFFF），覆盖 **CMD..PAYLOAD**（不含 SOF）。

最短帧 = 7 + 2 = 9 字节（空 payload）。

## 命令表

| CMD | 名称 | 方向 | 说明 |
|---|---|---|---|
| 0x01 | PING | PC→桥 / 桥→PC | 握手；桥回 ACK + 版本 |
| 0x10 | UART_CFG | PC→桥 | 配置目标 UART（波特率/校验/停止位） |
| 0x11 | UART_WRITE | PC→桥 | 主动写目标 UART |
| 0x13 | UART_LISTEN | PC→桥 | 开始/停止被动监听目标 UART |
| 0x20 | I2C_SCAN | PC→桥 | 扫描 7-bit 地址 |
| 0x21 | I2C_WRITE | PC→桥 | 主动写 |
| 0x22 | I2C_READ | PC→桥 | 主动读 |
| 0x23 | I2C_LISTEN | PC→桥 | 被动监听 |
| 0x30 | SPI_CFG | PC→桥 | 配置模式/速率/CPOL/CPHA |
| 0x31 | SPI_TRANSFER | PC→桥 | 全双工传输 |
| 0x32 | SPI_LISTEN | PC→桥 | 被动监听 |
| 0x40 | LOGIC_CFG | PC→桥 | 采样率/通道/触发 |
| 0x41 | LOGIC_START | PC→桥 | 开始抓取 |
| 0x42 | LOGIC_DATA | 桥→PC | 采样数据块 |
| 0x43 | LOGIC_STOP | PC→桥 | 停止抓取 |
| 0xF0 | EVENT | 桥→PC | 异步数据/状态事件（带 µs 时间戳） |
| 0xF1 | ERROR | 桥→PC | 错误上报 |
| 0xF2 | ACK | 桥→PC | 命令应答 |

## SEQ 语义

- 下行（PC→桥）：PC 侧 `BridgeLink` 维护递增 SEQ。
- 上行（桥→PC）：桥维护**独立**的递增 SEQ。
- 丢帧检测只作用于上行帧（PC 只解析 RX 方向），相邻帧 SEQ 不连续即记 `seq_gap`。

## 时间戳与事件（M3）

桥用 72MHz 定时器给每条上行 EVENT 打 **µs 时间戳**，PAYLOAD 布局（EVENT）：

```
[通道 1B][方向 1B][时间戳 µs 4B][数据 N B]
```

供上位机做时序抖动、吞吐、延迟分析。桥同时累计并回传：NACK 次数、校验/帧错误
次数（ERROR 事件），构成「协议层错误」指标。

## PAYLOAD 布局（各 CMD 的载荷，多字节小端）

实现：`app/protocol/payloads.py`（上位机）、`firmware/bridge/bridge_payloads.*`（固件），
两者已逐字节交叉验证。

### EVENT（0xF0，桥→PC）

```
[通道 1B][方向 1B][时间戳 µs 4B][数据 N B]
```

- 通道：0=UART, 1=I2C, 2=SPI, 3=LOGIC
- 方向：0=RX, 1=TX

### ACK（0xF2，桥→PC）

```
[应答CMD 1B][状态 1B][请求序号 2B][数据 N B]
```

状态：0=OK, 1=ERR。请求序号回传被应答请求的 SEQ，供上位机做延迟相关。

### ERROR（0xF1，桥→PC）

```
[错误码 1B][数据 N B]
```

错误码：0=未知命令, 1=参数错误, 2=总线错误(NACK), 3=超时, 4=缓冲区溢出。

### UART_CFG（0x10，PC→桥）

```
[波特率 4B][数据位 1B][校验 1B][停止位 1B]
```

校验：0=None, 1=Even, 2=Odd。

### I2C_WRITE（0x21）/ I2C_READ（0x22）

```
WRITE: [7bit地址 1B][数据 N B]
READ:  [7bit地址 1B][长度 2B]
```

### SPI_CFG（0x30）/ SPI_TRANSFER（0x31）

```
CFG:      [速率Hz 4B][模式 1B][位序 1B]     # 模式 0..3 = CPOL|(CPHA<<1)，位序 0=MSB
TRANSFER: [CS引脚 1B][数据 N B]
```

### LOGIC_CFG（0x40）/ LOGIC_DATA（0x42）

```
CFG:  [采样率Hz 4B][通道掩码 1B][触发通道 1B][触发边沿 1B]
DATA: [块序号 2B][样本数 2B][样本 N B]        # 每字节 bit i = 通道 i 电平
```

> 注：LISTEN 类命令（UART_LISTEN/I2C_LISTEN/SPI_LISTEN）payload 为单字节使能
> （0=停止, 1=开始），LOGIC_START/STOP 为空 payload。
