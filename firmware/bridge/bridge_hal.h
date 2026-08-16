/* bridge_hal.h — 桥接外设抽象层
 *
 * 调度器（bridge_app.c）只依赖此接口，不直接调 HAL。这样：
 *   - 宿主机用 bridge_hal_mock.c 编译测试调度逻辑；
 *   - 板子用 stm32/bridge_hal_stm32.c 接真实 HAL 外设。
 */
#ifndef BRIDGE_HAL_H
#define BRIDGE_HAL_H

#include <stdint.h>

/* 被动监听 / 目标数据回调：channel+dir+µs时间戳+数据 */
typedef void (*BrDataCallback)(uint8_t channel, uint8_t dir, uint32_t ts_us,
                               const uint8_t *data, uint16_t len);

/* 生命周期 */
void br_hal_init(void);
void br_hal_set_data_callback(BrDataCallback cb);

/* 到 PC 的串口发送（USART1） */
void br_pc_tx(const uint8_t *data, uint16_t len);

/* µs 时间戳 */
uint32_t br_timestamp_us(void);

/* 目标 UART（USART2） */
void br_target_uart_cfg(uint32_t baud, uint8_t data_bits, uint8_t parity, uint8_t stop_bits);
void br_target_uart_write(const uint8_t *data, uint16_t len);
void br_target_uart_listen(uint8_t enable);

/* I2C（I2C1）：返回 0 成功，非 0 失败 */
int  br_i2c_scan(uint8_t *found, uint8_t max);
int  br_i2c_write(uint8_t addr7, const uint8_t *data, uint16_t len);
int  br_i2c_read(uint8_t addr7, uint16_t len, uint8_t *out);
void br_i2c_listen(uint8_t enable);

/* SPI（SPI1） */
void br_spi_cfg(uint32_t hz, uint8_t mode, uint8_t bit_order);
int  br_spi_transfer(uint8_t cs, const uint8_t *tx, uint16_t len, uint8_t *rx);
void br_spi_listen(uint8_t enable);

/* 逻辑抓取（采样 GPIO） */
void br_logic_cfg(uint32_t hz, uint8_t mask, uint8_t trig_ch, uint8_t trig_edge);
void br_logic_start(void);
void br_logic_stop(void);
/* 取一次逻辑抓取数据：有数据返回 1（out 至少 max 字节，count 为样本数） */
int  br_logic_get(uint8_t *out, uint16_t max, uint16_t *count, uint16_t *block_seq);

#endif /* BRIDGE_HAL_H */
