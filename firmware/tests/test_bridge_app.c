/* test_bridge_app.c — 桥接调度器宿主机单测（gcc + mock HAL）
 *
 * 验证命令分发、ACK/EVENT/ERROR 生成、参数校验，与上位机协议同源。
 */
#include <stdio.h>
#include <string.h>

#include "bridge_app.h"
#include "bridge_protocol.h"
#include "bridge_payloads.h"

/* mock 访问器 */
extern const uint8_t *br_mock_pc_tx(uint32_t *len);
extern void br_mock_reset_tx(void);
extern uint32_t br_mock_target_uart_baud(void);
extern void br_mock_emit_uart_rx(const uint8_t *data, uint16_t len);

static int failures = 0;
#define CHECK(cond, name) do {                                  \
    if (cond) { printf("[PASS] %s\n", name); }                  \
    else { printf("[FAIL] %s\n", name); failures++; }           \
} while (0)

/* 解析 mock 发回 PC 的第一帧 */
static int pop_first_tx(uint8_t *cmd, uint16_t *seq, uint8_t *out, uint16_t *plen)
{
    uint32_t txlen;
    const uint8_t *tx = br_mock_pc_tx(&txlen);
    BpParser p;
    bp_parser_init(&p);
    bp_parser_feed(&p, tx, txlen);
    return bp_parser_pop(&p, cmd, seq, out, plen);
}

int main(void)
{
    br_app_init();

    /* 1. PING → ACK(PING, OK, req_seq, ver 1.0) */
    {
        uint8_t req[64];
        uint32_t n = bp_build_frame(BP_CMD_PING, 1, 0, 0, req);
        br_mock_reset_tx();
        br_app_on_pc_bytes(req, n);
        uint8_t cmd, out[BP_MAX_PAYLOAD];
        uint16_t seq, plen;
        int got = pop_first_tx(&cmd, &seq, out, &plen);
        CHECK(got == 1 && cmd == BP_CMD_ACK && plen == 6
                  && out[0] == BP_CMD_PING && out[1] == BP_STATUS_OK
                  && out[2] == 1 && out[3] == 0 && out[4] == 1 && out[5] == 0,
              "PING → ACK(版本 1.0)");
    }

    /* 2. UART_CFG → ACK + 波特率已下发 */
    {
        uint8_t cfg[7] = {0x00, 0xC2, 0x01, 0x00, 8, 0, 1};  /* 115200 8N1 */
        uint8_t req[64];
        uint32_t n = bp_build_frame(BP_CMD_UART_CFG, 2, cfg, 7, req);
        br_mock_reset_tx();
        br_app_on_pc_bytes(req, n);
        uint8_t cmd, out[BP_MAX_PAYLOAD];
        uint16_t seq, plen;
        int got = pop_first_tx(&cmd, &seq, out, &plen);
        CHECK(got == 1 && cmd == BP_CMD_ACK && out[0] == BP_CMD_UART_CFG
                  && out[1] == BP_STATUS_OK && br_mock_target_uart_baud() == 115200,
              "UART_CFG → ACK + 波特率 115200");
    }

    /* 3. I2C_SCAN → ACK 带地址 0x50 */
    {
        uint8_t req[64];
        uint32_t n = bp_build_frame(BP_CMD_I2C_SCAN, 3, 0, 0, req);
        br_mock_reset_tx();
        br_app_on_pc_bytes(req, n);
        uint8_t cmd, out[BP_MAX_PAYLOAD];
        uint16_t seq, plen;
        int got = pop_first_tx(&cmd, &seq, out, &plen);
        CHECK(got == 1 && cmd == BP_CMD_ACK && out[0] == BP_CMD_I2C_SCAN
                  && out[1] == BP_STATUS_OK && plen >= 5 && out[4] == 0x50,
              "I2C_SCAN → ACK(发现 0x50)");
    }

    /* 4. 未知命令 → ERROR */
    {
        uint8_t req[64];
        uint32_t n = bp_build_frame(0xEE, 4, 0, 0, req);
        br_mock_reset_tx();
        br_app_on_pc_bytes(req, n);
        uint8_t cmd, out[BP_MAX_PAYLOAD];
        uint16_t seq, plen;
        int got = pop_first_tx(&cmd, &seq, out, &plen);
        CHECK(got == 1 && cmd == BP_CMD_ERROR && out[0] == ERR_UNKNOWN_CMD,
              "未知命令 → ERROR(UNKNOWN)");
    }

    /* 5. 目标 UART 数据 → EVENT 帧 */
    {
        br_mock_reset_tx();
        uint8_t d[] = {0x68, 0x69};
        br_mock_emit_uart_rx(d, 2);
        uint8_t cmd, out[BP_MAX_PAYLOAD];
        uint16_t seq, plen;
        int got = pop_first_tx(&cmd, &seq, out, &plen);
        CHECK(got == 1 && cmd == BP_CMD_EVENT && plen == 8
                  && out[0] == BP_CH_UART && out[1] == BP_DIR_RX
                  && out[6] == 0x68 && out[7] == 0x69,
              "目标 UART 数据 → EVENT(带时间戳)");
    }

    /* 6. 坏 CRC 帧不崩溃、不影响后续 */
    {
        uint8_t good[64], bad[64];
        uint32_t ng = bp_build_frame(BP_CMD_PING, 5, 0, 0, good);
        memcpy(bad, good, ng);
        bad[ng - 1] ^= 0xFFu;
        br_mock_reset_tx();
        br_app_on_pc_bytes(bad, ng);
        br_app_on_pc_bytes(good, ng);
        uint8_t cmd, out[BP_MAX_PAYLOAD];
        uint16_t seq, plen;
        int got = pop_first_tx(&cmd, &seq, out, &plen);
        CHECK(got == 1 && cmd == BP_CMD_ACK, "坏帧跳过 → 后续正常 ACK");
    }

    printf("\n");
    if (failures) {
        printf("%d 项失败\n", failures);
        return 1;
    }
    printf("调度器单测全部通过 [OK]\n");
    return 0;
}
