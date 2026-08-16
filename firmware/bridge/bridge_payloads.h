/* bridge_payloads.h — 桥接协议 payload 编解码（纯 C，HAL 无关）
 *
 * 与上位机 app/protocol/payloads.py 保持一致，多字节小端。
 */
#ifndef BRIDGE_PAYLOADS_H
#define BRIDGE_PAYLOADS_H

#include <stdint.h>

/* 通道 */
#define BP_CH_UART  0
#define BP_CH_I2C   1
#define BP_CH_SPI   2
#define BP_CH_LOGIC 3

/* 方向 */
#define BP_DIR_RX   0
#define BP_DIR_TX   1

/* 应答状态 */
#define BP_STATUS_OK  0
#define BP_STATUS_ERR 1

/* 错误码 */
#define ERR_UNKNOWN_CMD 0
#define ERR_BAD_PARAM   1
#define ERR_BUS         2
#define ERR_TIMEOUT     3
#define ERR_OVERFLOW    4

/* EVENT payload: [channel u8][dir u8][ts_us u32 LE][data...]
 * 返回总长度；out 至少 6 + len 字节。 */
uint32_t bp_pack_event(uint8_t channel, uint8_t dir, uint32_t ts_us,
                       const uint8_t *data, uint16_t len, uint8_t *out);

/* UART_CFG payload: [baud u32 LE][data_bits u8][parity u8][stop_bits u8]
 * 返回总长度（恒为 7）。 */
uint32_t bp_pack_uart_cfg(uint32_t baud, uint8_t data_bits, uint8_t parity,
                          uint8_t stop_bits, uint8_t *out);

/* ACK payload: [ack_cmd u8][status u8][req_seq u16 LE][data...]
 * 返回总长度；out 至少 4 + len 字节。 */
uint32_t bp_pack_ack(uint8_t ack_cmd, uint8_t status, uint16_t req_seq,
                     const uint8_t *data, uint16_t len, uint8_t *out);

#endif /* BRIDGE_PAYLOADS_H */
