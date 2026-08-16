/* bridge_payloads.c — payload 编解码实现 */
#include "bridge_payloads.h"

uint32_t bp_pack_event(uint8_t channel, uint8_t dir, uint32_t ts_us,
                       const uint8_t *data, uint16_t len, uint8_t *out)
{
    out[0] = channel;
    out[1] = dir;
    out[2] = (uint8_t)(ts_us & 0xFFu);
    out[3] = (uint8_t)((ts_us >> 8) & 0xFFu);
    out[4] = (uint8_t)((ts_us >> 16) & 0xFFu);
    out[5] = (uint8_t)((ts_us >> 24) & 0xFFu);
    for (uint16_t i = 0; i < len; i++)
        out[6 + i] = data[i];
    return 6u + len;
}

uint32_t bp_pack_uart_cfg(uint32_t baud, uint8_t data_bits, uint8_t parity,
                          uint8_t stop_bits, uint8_t *out)
{
    out[0] = (uint8_t)(baud & 0xFFu);
    out[1] = (uint8_t)((baud >> 8) & 0xFFu);
    out[2] = (uint8_t)((baud >> 16) & 0xFFu);
    out[3] = (uint8_t)((baud >> 24) & 0xFFu);
    out[4] = data_bits;
    out[5] = parity;
    out[6] = stop_bits;
    return 7u;
}

uint32_t bp_pack_ack(uint8_t ack_cmd, uint8_t status, uint16_t req_seq,
                     const uint8_t *data, uint16_t len, uint8_t *out)
{
    out[0] = ack_cmd;
    out[1] = status;
    out[2] = (uint8_t)(req_seq & 0xFFu);
    out[3] = (uint8_t)((req_seq >> 8) & 0xFFu);
    for (uint16_t i = 0; i < len; i++)
        out[4 + i] = data[i];
    return 4u + len;
}
