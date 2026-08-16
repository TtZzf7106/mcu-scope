/* bridge_protocol.c — 桥接协议核心实现 */
#include "bridge_protocol.h"

#include <string.h>

uint16_t crc16_modbus(const uint8_t *data, uint32_t len, uint16_t seed)
{
    uint16_t crc = seed;
    for (uint32_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int j = 0; j < 8; j++) {
            if (crc & 1u)
                crc = (uint16_t)((crc >> 1) ^ 0xA001u);
            else
                crc = (uint16_t)(crc >> 1);
        }
    }
    return crc;
}

uint32_t bp_build_frame(uint8_t cmd, uint16_t seq, const uint8_t *payload,
                        uint16_t len, uint8_t *out)
{
    out[0] = BP_SOF_B0;
    out[1] = BP_SOF_B1;
    out[2] = cmd;
    out[3] = (uint8_t)(seq & 0xFFu);
    out[4] = (uint8_t)((seq >> 8) & 0xFFu);
    out[5] = (uint8_t)(len & 0xFFu);
    out[6] = (uint8_t)((len >> 8) & 0xFFu);
    for (uint16_t i = 0; i < len; i++)
        out[7 + i] = payload[i];

    /* CRC 覆盖 CMD..PAYLOAD = out[2 .. 6+len]，共 5+len 字节 */
    uint16_t crc = crc16_modbus(out + 2, 5u + len, 0xFFFFu);
    out[7 + len]     = (uint8_t)(crc & 0xFFu);
    out[8 + len]     = (uint8_t)((crc >> 8) & 0xFFu);
    return BP_HEADER_LEN + len + BP_CRC_LEN;
}

void bp_parser_init(BpParser *p)
{
    p->len = 0;
    p->crc_errors = 0;
    p->length_errors = 0;
}

static void bp_drop(BpParser *p, uint32_t n)
{
    if (n >= p->len) {
        p->len = 0;
        return;
    }
    memmove(p->buf, p->buf + n, p->len - n);
    p->len -= n;
}

void bp_parser_feed(BpParser *p, const uint8_t *data, uint32_t len)
{
    for (uint32_t i = 0; i < len; i++) {
        if (p->len >= sizeof(p->buf))
            bp_drop(p, 1);   /* 满则丢最旧，防死锁 */
        p->buf[p->len++] = data[i];
    }
}

int bp_parser_pop(BpParser *p, uint8_t *cmd, uint16_t *seq,
                  uint8_t *payload, uint16_t *payload_len)
{
    while (p->len >= BP_MIN_FRAME_LEN) {
        if (p->buf[0] != BP_SOF_B0 || p->buf[1] != BP_SOF_B1) {
            bp_drop(p, 1);
            continue;
        }

        uint8_t  c = p->buf[2];
        uint16_t s = (uint16_t)(p->buf[3] | ((uint16_t)p->buf[4] << 8));
        uint16_t l = (uint16_t)(p->buf[5] | ((uint16_t)p->buf[6] << 8));

        if (l > BP_MAX_PAYLOAD) {
            p->length_errors++;
            bp_drop(p, 1);
            continue;
        }

        uint32_t total = BP_HEADER_LEN + l + BP_CRC_LEN;
        if (p->len < total)
            return 0;   /* 数据不足，等下一包 */

        uint16_t crc_recv = (uint16_t)(p->buf[BP_HEADER_LEN + l]
                            | ((uint16_t)p->buf[BP_HEADER_LEN + l + 1] << 8));
        uint16_t crc_calc = crc16_modbus(p->buf + 2, 5u + l, 0xFFFFu);

        if (crc_recv != crc_calc) {
            p->crc_errors++;
            bp_drop(p, 1);
            continue;
        }

        for (uint16_t i = 0; i < l; i++)
            payload[i] = p->buf[BP_HEADER_LEN + i];
        *cmd = c;
        *seq = s;
        *payload_len = l;
        bp_drop(p, total);
        return 1;
    }
    return 0;
}
