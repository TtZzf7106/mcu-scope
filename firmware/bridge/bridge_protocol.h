/* bridge_protocol.h — 桥接协议核心（纯 C，HAL 无关）
 *
 * 与上位机 app/protocol/ 保持一致：
 *   帧格式  [SOF AA 55][CMD 1B][SEQ 2B][LEN 2B][PAYLOAD][CRC16 2B]（小端）
 *   CRC16-MODBUS 覆盖 CMD..PAYLOAD
 */
#ifndef BRIDGE_PROTOCOL_H
#define BRIDGE_PROTOCOL_H

#include <stdint.h>

#define BP_SOF_B0         0xAAu
#define BP_SOF_B1         0x55u
#define BP_HEADER_LEN     7u    /* SOF(2)+CMD(1)+SEQ(2)+LEN(2) */
#define BP_CRC_LEN        2u
#define BP_MIN_FRAME_LEN  (BP_HEADER_LEN + BP_CRC_LEN)
#define BP_MAX_PAYLOAD    2048u

/* 命令表（与 Python app/protocol/commands.py 一致） */
enum {
    BP_CMD_PING         = 0x01,
    BP_CMD_UART_CFG     = 0x10,
    BP_CMD_UART_WRITE   = 0x11,
    BP_CMD_UART_LISTEN  = 0x13,
    BP_CMD_I2C_SCAN     = 0x20,
    BP_CMD_I2C_WRITE    = 0x21,
    BP_CMD_I2C_READ     = 0x22,
    BP_CMD_I2C_LISTEN   = 0x23,
    BP_CMD_SPI_CFG      = 0x30,
    BP_CMD_SPI_TRANSFER = 0x31,
    BP_CMD_SPI_LISTEN   = 0x32,
    BP_CMD_LOGIC_CFG    = 0x40,
    BP_CMD_LOGIC_START  = 0x41,
    BP_CMD_LOGIC_DATA   = 0x42,
    BP_CMD_LOGIC_STOP   = 0x43,
    BP_CMD_EVENT        = 0xF0,
    BP_CMD_ERROR        = 0xF1,
    BP_CMD_ACK          = 0xF2,
};

/* CRC16-MODBUS（位运算，逐字节等价于 Python 表实现；MCU 上可换表提速） */
uint16_t crc16_modbus(const uint8_t *data, uint32_t len, uint16_t seed);

/* 组帧：out 至少 BP_HEADER_LEN + len + BP_CRC_LEN；返回总长度 */
uint32_t bp_build_frame(uint8_t cmd, uint16_t seq, const uint8_t *payload,
                        uint16_t len, uint8_t *out);

/* 流式解析器 */
typedef struct {
    uint8_t  buf[BP_MAX_PAYLOAD + BP_HEADER_LEN + BP_CRC_LEN];
    uint32_t len;
    uint32_t crc_errors;
    uint32_t length_errors;
} BpParser;

void bp_parser_init(BpParser *p);

/* 喂入原始字节（缓冲区满时丢最旧字节重同步，防死锁） */
void bp_parser_feed(BpParser *p, const uint8_t *data, uint32_t len);

/* 取下一帧：成功返回 1 并填充 out 参数；无完整帧（或已跳过坏帧）返回 0。
 * 坏 CRC / 超长帧会丢 1 字节重同步并累计 crc_errors / length_errors。 */
int bp_parser_pop(BpParser *p, uint8_t *cmd, uint16_t *seq,
                  uint8_t *payload, uint16_t *payload_len);

#endif /* BRIDGE_PROTOCOL_H */
