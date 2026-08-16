/* bridge_hal_mock.c — 宿主机测试用的外设抽象 mock 实现。
 * 只做内存记录，供 test_bridge_app.c 断言调度行为。 */
#include "bridge_hal.h"
#include "bridge_payloads.h"
#include <string.h>

static uint8_t g_pc_tx_buf[4096];
static uint32_t g_pc_tx_len = 0;
static uint32_t g_ts = 0;
static uint32_t g_target_uart_baud = 0;
static BrDataCallback g_cb = NULL;

void br_hal_init(void) { g_pc_tx_len = 0; g_ts = 0; g_target_uart_baud = 0; }
void br_hal_set_data_callback(BrDataCallback cb) { g_cb = cb; }

void br_pc_tx(const uint8_t *data, uint16_t len)
{
    if (g_pc_tx_len + len < sizeof(g_pc_tx_buf)) {
        memcpy(g_pc_tx_buf + g_pc_tx_len, data, len);
        g_pc_tx_len += len;
    }
}

uint32_t br_timestamp_us(void) { g_ts += 1000u; return g_ts; }

void br_target_uart_cfg(uint32_t baud, uint8_t data_bits, uint8_t parity, uint8_t stop_bits)
{
    (void)data_bits; (void)parity; (void)stop_bits;
    g_target_uart_baud = baud;
}
void br_target_uart_write(const uint8_t *data, uint16_t len) { (void)data; (void)len; }
void br_target_uart_listen(uint8_t enable) { (void)enable; }

int br_i2c_scan(uint8_t *found, uint8_t max)
{
    if (max > 0) found[0] = 0x50;  /* 模拟发现 0x50 */
    return 1;
}
int br_i2c_write(uint8_t addr7, const uint8_t *data, uint16_t len)
{ (void)addr7; (void)data; (void)len; return 0; }
int br_i2c_read(uint8_t addr7, uint16_t len, uint8_t *out)
{
    (void)addr7;
    for (uint16_t i = 0; i < len; i++) out[i] = 0xAA;
    return 0;
}
void br_i2c_listen(uint8_t enable) { (void)enable; }

void br_spi_cfg(uint32_t hz, uint8_t mode, uint8_t bit_order)
{ (void)hz; (void)mode; (void)bit_order; }
int br_spi_transfer(uint8_t cs, const uint8_t *tx, uint16_t len, uint8_t *rx)
{
    (void)cs;
    for (uint16_t i = 0; i < len; i++) rx[i] = tx[i] ^ 0xFFu;
    return 0;
}
void br_spi_listen(uint8_t enable) { (void)enable; }

void br_logic_cfg(uint32_t hz, uint8_t mask, uint8_t trig_ch, uint8_t trig_edge)
{ (void)hz; (void)mask; (void)trig_ch; (void)trig_edge; }
void br_logic_start(void) {}
void br_logic_stop(void) {}
int br_logic_get(uint8_t *out, uint16_t max, uint16_t *count, uint16_t *block_seq)
{ (void)out; (void)max; (void)count; (void)block_seq; return 0; }

/* ---- 供测试使用的访问器 ---- */
const uint8_t *br_mock_pc_tx(uint32_t *len) { *len = g_pc_tx_len; return g_pc_tx_buf; }
void br_mock_reset_tx(void) { g_pc_tx_len = 0; }
uint32_t br_mock_target_uart_baud(void) { return g_target_uart_baud; }

/* 模拟目标 UART 收到数据 → 触发数据回调 → 应产生 EVENT 帧 */
void br_mock_emit_uart_rx(const uint8_t *data, uint16_t len)
{
    if (g_cb)
        g_cb(BP_CH_UART, BP_DIR_RX, br_timestamp_us(), data, len);
}
