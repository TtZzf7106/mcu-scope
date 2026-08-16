/* bridge_app.c — 桥接应用调度器
 *
 * 职责：解析 PC 命令帧 → 分发给对应外设 → 回 ACK/EVENT/ERROR 帧。
 * 被动监听/目标数据经 BrDataCallback 进来后，包成 EVENT 帧回传 PC。
 */
#include "bridge_app.h"
#include "bridge_protocol.h"
#include "bridge_payloads.h"
#include "bridge_hal.h"

#include <string.h>

static BpParser g_parser;
static uint16_t g_tx_seq = 0;

static void dispatch(uint8_t cmd, uint16_t seq, const uint8_t *p, uint16_t plen);
static void send_frame(uint8_t cmd, const uint8_t *payload, uint16_t plen);
static void send_ack(uint8_t ack_cmd, uint16_t req_seq, uint8_t status,
                     const uint8_t *data, uint16_t dlen);
static void send_error(uint8_t code);
static void on_peripheral_data(uint8_t channel, uint8_t dir, uint32_t ts_us,
                               const uint8_t *data, uint16_t len);

static uint32_t le_u32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

void br_app_init(void)
{
    bp_parser_init(&g_parser);
    g_tx_seq = 0;
    br_hal_set_data_callback(on_peripheral_data);
    br_hal_init();
}

void br_app_on_pc_bytes(const uint8_t *data, uint32_t len)
{
    bp_parser_feed(&g_parser, data, len);
    uint8_t cmd, payload[BP_MAX_PAYLOAD];
    uint16_t seq, plen;
    while (bp_parser_pop(&g_parser, &cmd, &seq, payload, &plen))
        dispatch(cmd, seq, payload, plen);
}

void br_app_poll(void)
{
    /* 逻辑抓取数据分块上传（经 LOGIC_DATA） */
    uint8_t buf[BP_MAX_PAYLOAD];
    uint16_t count, block_seq;
    if (br_logic_get(buf, BP_MAX_PAYLOAD - 4u, &count, &block_seq)) {
        uint8_t p[BP_MAX_PAYLOAD];
        p[0] = (uint8_t)(block_seq & 0xFFu);
        p[1] = (uint8_t)((block_seq >> 8) & 0xFFu);
        p[2] = (uint8_t)(count & 0xFFu);
        p[3] = (uint8_t)((count >> 8) & 0xFFu);
        for (uint16_t i = 0; i < count; i++)
            p[4 + i] = buf[i];
        send_frame(BP_CMD_LOGIC_DATA, p, 4u + count);
    }
}

static void dispatch(uint8_t cmd, uint16_t seq, const uint8_t *p, uint16_t plen)
{
    switch (cmd) {
    case BP_CMD_PING: {
        uint8_t ver[2] = {1u, 0u};  /* 协议版本 1.0 */
        send_ack(BP_CMD_PING, seq, BP_STATUS_OK, ver, 2);
        break;
    }
    case BP_CMD_UART_CFG:
        if (plen < 7) { send_error(ERR_BAD_PARAM); break; }
        br_target_uart_cfg(le_u32(p), p[4], p[5], p[6]);
        send_ack(BP_CMD_UART_CFG, seq, BP_STATUS_OK, 0, 0);
        break;
    case BP_CMD_UART_WRITE:
        br_target_uart_write(p, plen);
        send_ack(BP_CMD_UART_WRITE, seq, BP_STATUS_OK, 0, 0);
        break;
    case BP_CMD_UART_LISTEN:
        if (plen < 1) { send_error(ERR_BAD_PARAM); break; }
        br_target_uart_listen(p[0]);
        send_ack(BP_CMD_UART_LISTEN, seq, BP_STATUS_OK, 0, 0);
        break;

    case BP_CMD_I2C_SCAN: {
        uint8_t found[128];
        int n = br_i2c_scan(found, 128);
        send_ack(BP_CMD_I2C_SCAN, seq, BP_STATUS_OK, found, (uint16_t)n);
        break;
    }
    case BP_CMD_I2C_WRITE: {
        if (plen < 1) { send_error(ERR_BAD_PARAM); break; }
        int r = br_i2c_write(p[0], p + 1, plen - 1);
        if (r == -2)
            send_error(ERR_TIMEOUT);       /* START 失败：总线卡死/无时钟 */
        else if (r != 0)
            send_error(ERR_BUS);           /* NACK：设备无应答 */
        else
            send_ack(BP_CMD_I2C_WRITE, seq, BP_STATUS_OK, 0, 0);
        break;
    }
    case BP_CMD_I2C_READ: {
        if (plen < 3) { send_error(ERR_BAD_PARAM); break; }
        uint16_t n = (uint16_t)(p[1] | ((uint16_t)p[2] << 8));
        uint8_t out[BP_MAX_PAYLOAD];
        if (n > BP_MAX_PAYLOAD) { send_error(ERR_BAD_PARAM); break; }
        int r = br_i2c_read(p[0], n, out);
        if (r == -2)
            send_error(ERR_TIMEOUT);
        else if (r != 0)
            send_error(ERR_BUS);
        else
            send_ack(BP_CMD_I2C_READ, seq, BP_STATUS_OK, out, n);
        break;
    }
    case BP_CMD_I2C_LISTEN:
        if (plen < 1) { send_error(ERR_BAD_PARAM); break; }
        br_i2c_listen(p[0]);
        send_ack(BP_CMD_I2C_LISTEN, seq, BP_STATUS_OK, 0, 0);
        break;

    case BP_CMD_SPI_CFG:
        if (plen < 6) { send_error(ERR_BAD_PARAM); break; }
        br_spi_cfg(le_u32(p), p[4], p[5]);
        send_ack(BP_CMD_SPI_CFG, seq, BP_STATUS_OK, 0, 0);
        break;
    case BP_CMD_SPI_TRANSFER: {
        if (plen < 1) { send_error(ERR_BAD_PARAM); break; }
        uint8_t rx[BP_MAX_PAYLOAD];
        if (br_spi_transfer(p[0], p + 1, plen - 1, rx) != 0)
            send_error(ERR_BUS);
        else
            send_ack(BP_CMD_SPI_TRANSFER, seq, BP_STATUS_OK, rx, plen - 1);
        break;
    }
    case BP_CMD_SPI_LISTEN:
        if (plen < 1) { send_error(ERR_BAD_PARAM); break; }
        br_spi_listen(p[0]);
        send_ack(BP_CMD_SPI_LISTEN, seq, BP_STATUS_OK, 0, 0);
        break;

    case BP_CMD_LOGIC_CFG:
        if (plen < 7) { send_error(ERR_BAD_PARAM); break; }
        br_logic_cfg(le_u32(p), p[4], p[5], p[6]);
        send_ack(BP_CMD_LOGIC_CFG, seq, BP_STATUS_OK, 0, 0);
        break;
    case BP_CMD_LOGIC_START:
        br_logic_start();
        send_ack(BP_CMD_LOGIC_START, seq, BP_STATUS_OK, 0, 0);
        break;
    case BP_CMD_LOGIC_STOP:
        br_logic_stop();
        send_ack(BP_CMD_LOGIC_STOP, seq, BP_STATUS_OK, 0, 0);
        break;

    default:
        send_error(ERR_UNKNOWN_CMD);
    }
}

static void send_frame(uint8_t cmd, const uint8_t *payload, uint16_t plen)
{
    uint8_t buf[BP_MAX_PAYLOAD + BP_HEADER_LEN + BP_CRC_LEN];
    uint32_t n = bp_build_frame(cmd, g_tx_seq++, payload, plen, buf);
    br_pc_tx(buf, n);
}

static void send_ack(uint8_t ack_cmd, uint16_t req_seq, uint8_t status,
                     const uint8_t *data, uint16_t dlen)
{
    uint8_t p[BP_MAX_PAYLOAD + 4];
    uint32_t n = bp_pack_ack(ack_cmd, status, req_seq, data, dlen, p);
    send_frame(BP_CMD_ACK, p, (uint16_t)n);
}

static void send_error(uint8_t code)
{
    uint8_t p[1];
    p[0] = code;
    send_frame(BP_CMD_ERROR, p, 1);
}

static void on_peripheral_data(uint8_t channel, uint8_t dir, uint32_t ts_us,
                               const uint8_t *data, uint16_t len)
{
    uint8_t p[BP_MAX_PAYLOAD + 6];
    uint32_t n = bp_pack_event(channel, dir, ts_us, data, len, p);
    send_frame(BP_CMD_EVENT, p, (uint16_t)n);
}
