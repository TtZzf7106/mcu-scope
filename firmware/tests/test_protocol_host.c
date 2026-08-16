/* test_protocol_host.c — 桥接协议核心宿主机单测（gcc 编译）
 *
 * 编译：gcc -std=c11 -Wall -Wextra -O2 -I../bridge -o test_protocol_host.exe \
 *           test_protocol_host.c ../bridge/bridge_protocol.c
 */
#include <stdio.h>
#include <string.h>

#include "bridge_protocol.h"
#include "bridge_payloads.h"

static int failures = 0;

#define CHECK(cond, name) do {                                  \
    if (cond) { printf("[PASS] %s\n", name); }                  \
    else { printf("[FAIL] %s\n", name); failures++; }           \
} while (0)

/* 喂入并抽取全部帧，返回帧数 */
static int drain(BpParser *p, const uint8_t *data, uint32_t len)
{
    bp_parser_feed(p, data, len);
    int n = 0;
    uint8_t cmd, out[BP_MAX_PAYLOAD];
    uint16_t seq, plen;
    while (bp_parser_pop(p, &cmd, &seq, out, &plen))
        n++;
    return n;
}

int main(void)
{
    /* 1. CRC 标准向量 */
    CHECK(crc16_modbus((const uint8_t *)"123456789", 9, 0xFFFFu) == 0x4B37u,
          "CRC16 0x4B37");

    /* 2. 组帧 + 解析往返 */
    uint8_t payload[16];
    for (int i = 0; i < 16; i++)
        payload[i] = (uint8_t)i;

    uint8_t frame[BP_MAX_PAYLOAD + 32];
    uint32_t n = bp_build_frame(0x21, 7, payload, 16, frame);
    CHECK(n == 9u + 16u, "帧长度 = 25");

    BpParser p;
    bp_parser_init(&p);
    uint8_t cmd, out[BP_MAX_PAYLOAD];
    uint16_t seq, plen;
    bp_parser_feed(&p, frame, n);
    int got = bp_parser_pop(&p, &cmd, &seq, out, &plen);
    CHECK(got == 1 && cmd == 0x21 && seq == 7 && plen == 16
              && memcmp(out, payload, 16) == 0,
          "组帧/解析往返");

    /* 3. 分片喂入 */
    bp_parser_init(&p);
    for (uint32_t i = 0; i < n; i += 3) {
        uint32_t chunk = (n - i < 3) ? (n - i) : 3;
        bp_parser_feed(&p, frame + i, chunk);
    }
    got = bp_parser_pop(&p, &cmd, &seq, out, &plen);
    CHECK(got == 1 && plen == 16, "分片流式解析");

    /* 4. 噪声前缀重同步 */
    bp_parser_init(&p);
    {
        uint8_t noise[] = {0x00, 0xFF};
        bp_parser_feed(&p, noise, 2);
    }
    got = bp_parser_pop(&p, &cmd, &seq, out, &plen);
    CHECK(got == 0, "噪声不足以成帧");
    bp_parser_feed(&p, frame, n);
    got = bp_parser_pop(&p, &cmd, &seq, out, &plen);
    CHECK(got == 1 && plen == 16, "噪声前缀重同步");

    /* 5. 坏帧跳过 + 后续帧可解 */
    bp_parser_init(&p);
    {
        uint8_t g1[BP_MAX_PAYLOAD + 32], bad[BP_MAX_PAYLOAD + 32], g2[BP_MAX_PAYLOAD + 32];
        uint8_t pa = 0x61, pb = 0x62, pc = 0x63; /* 'a','b','c' */
        uint32_t n1 = bp_build_frame(0x10, 1, &pa, 1, g1);
        uint32_t n2 = bp_build_frame(0x10, 2, &pb, 1, bad);
        uint32_t n3 = bp_build_frame(0x10, 3, &pc, 1, g2);
        bad[n2 - 1] ^= 0xFFu;   /* 破坏 CRC 末字节 */
        int cnt = drain(&p, g1, n1);
        cnt += drain(&p, bad, n2);
        cnt += drain(&p, g2, n3);
        CHECK(cnt == 2 && p.crc_errors == 1, "坏帧跳过 + 后续帧可解");
    }

    /* 6. 超长帧 */
    bp_parser_init(&p);
    {
        uint8_t over[] = {0xAA, 0x55, 0x01, 0x01, 0x00, 0x00, 0x10, 0x00, 0x00};
        bp_parser_feed(&p, over, sizeof(over));
        got = bp_parser_pop(&p, &cmd, &seq, out, &plen);
        CHECK(p.length_errors == 1 && got == 0, "超长帧标记");
    }

    /* 打印一帧的十六进制，供与 Python 端交叉比对 */
    printf("\nFRAME_HEX: ");
    for (uint32_t i = 0; i < n; i++)
        printf("%02X", frame[i]);
    printf("\n\n");

    /* 打印 payload 十六进制，供与 Python 端交叉比对 */
    {
        uint8_t pev[32], puc[8];
        uint8_t evdata[] = {0x01, 0x02, 0xFF};
        uint32_t ne = bp_pack_event(BP_CH_I2C, BP_DIR_RX, 0x12345678u, evdata, 3, pev);
        uint32_t nu = bp_pack_uart_cfg(115200u, 8, 0, 1, puc);
        printf("EVENT_HEX:   ");
        for (uint32_t i = 0; i < ne; i++)
            printf("%02X", pev[i]);
        printf("\nUARTCFG_HEX: ");
        for (uint32_t i = 0; i < nu; i++)
            printf("%02X", puc[i]);
        printf("\n\n");
    }

    if (failures) {
        printf("%d 项失败\n", failures);
        return 1;
    }
    printf("C 单测全部通过 [OK]\n");
    return 0;
}
