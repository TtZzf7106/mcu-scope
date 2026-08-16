/* bridge_hal_stm32.c — STM32F103C8T6 外设实现（板子端）
 *
 * ⚠️ 本文件依赖 CubeMX 生成的 HAL 工程，未在宿主机编译验证。
 *
 * CubeMX 配置要求（STM32F103C8T6，HSE 8MHz → 72MHz）：
 *   USART1 (PA9 TX / PA10 RX)  115200  → 接 PC（经 USB-TTL）
 *   USART2 (PA2 TX / PA3 RX)   可变     → 接目标 UART
 *   I2C1   (PB6 SCL / PB7 SDA) 100kHz   → 接目标 I2C（+4.7kΩ 上拉）
 *   SPI1   (PA5 SCK / PA6 MISO / PA7 MOSI) → 接目标 SPI（CS 用任意 GPIO）
 *
 * 集成步骤：
 *   1. CubeMX 生成工程后，把 firmware/bridge/ 下所有 .c/.h 加入编译；
 *   2. 在 main.c 的 while(1) 之前调用 br_app_init()；
 *   3. USART1 接收：在 HAL_UART_RxCpltCallback 或主循环里，把收到的字节
 *      调用 br_app_on_pc_bytes() 喂入；
 *   4. 主循环里周期性调用 br_app_poll()。
 *
 * 句柄 huart1/huart2/hi2c1/hspi1 由 CubeMX 在 main.c 生成；若 main.h 未导出，
 * 在下方取消注释 extern 声明。
 */
#include "bridge_hal.h"
#include "main.h"   /* CubeMX 生成：外设句柄与 CMSIS */

#include <string.h>

/* 若 main.h 未导出句柄，改用下面 extern 声明：
   extern UART_HandleTypeDef huart1, huart2;
   extern I2C_HandleTypeDef hi2c1;
   extern SPI_HandleTypeDef hspi1;
*/

static BrDataCallback g_cb = NULL;

/* ---- µs 时间戳：DWT 周期计数器（72MHz）---- */
static void dwt_init(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

void br_hal_init(void)
{
    dwt_init();  /* 其余外设已由 CubeMX 在 main() 初始化 */
}

void br_hal_set_data_callback(BrDataCallback cb) { g_cb = cb; }

void br_pc_tx(const uint8_t *data, uint16_t len)
{
    HAL_UART_Transmit(&huart1, (uint8_t *)data, len, 100);
}

uint32_t br_timestamp_us(void)
{
    return DWT->CYCCNT / 72u;   /* 72 计数 = 1µs */
}

/* ---- 目标 UART ---- */
void br_target_uart_cfg(uint32_t baud, uint8_t data_bits, uint8_t parity, uint8_t stop_bits)
{
    huart2.Init.BaudRate = baud;
    huart2.Init.WordLength = (data_bits == 9) ? UART_WORDLENGTH_9B : UART_WORDLENGTH_8B;
    huart2.Init.Parity = (parity == 1) ? UART_PARITY_EVEN
                       : (parity == 2) ? UART_PARITY_ODD : UART_PARITY_NONE;
    huart2.Init.StopBits = (stop_bits == 2) ? UART_STOPBITS_2 : UART_STOPBITS_1;
    HAL_UART_DeInit(&huart2);
    HAL_UART_Init(&huart2);
}

void br_target_uart_write(const uint8_t *data, uint16_t len)
{
    HAL_UART_Transmit(&huart2, (uint8_t *)data, len, 100);
}

void br_target_uart_listen(uint8_t enable)
{
    /* 监听模式：使能后目标 UART 收到的数据经回调回传。
       简化实现：始终接收；enable 只控制是否上报。 */
    (void)enable;
}

/* ---- I2C ---- */
int br_i2c_scan(uint8_t *found, uint8_t max)
{
    int n = 0;
    for (uint16_t addr = 0x08; addr <= 0x77 && n < max; addr++) {
        if (HAL_I2C_IsDeviceReady(&hi2c1, (uint16_t)(addr << 1), 1, 10) == HAL_OK)
            found[n++] = (uint8_t)addr;
    }
    return n;
}

int br_i2c_write(uint8_t addr7, const uint8_t *data, uint16_t len)
{
    if (HAL_I2C_Master_Transmit(&hi2c1, (uint16_t)(addr7 << 1),
                                (uint8_t *)data, len, 100) != HAL_OK)
        return -1;
    return 0;
}

int br_i2c_read(uint8_t addr7, uint16_t len, uint8_t *out)
{
    if (HAL_I2C_Master_Receive(&hi2c1, (uint16_t)(addr7 << 1), out, len, 100) != HAL_OK)
        return -1;
    return 0;
}

void br_i2c_listen(uint8_t enable)
{
    /* 被动监听 I2C 需第二路 I2C 从机模式或 GPIO 位抓取；暂留 TODO。 */
    (void)enable;
}

/* ---- SPI ---- */
static uint32_t g_spi_hz = 0;
static uint8_t g_spi_mode = 0;
static uint8_t g_spi_bit_order = 0;

void br_spi_cfg(uint32_t hz, uint8_t mode, uint8_t bit_order)
{
    g_spi_hz = hz;
    g_spi_mode = mode;
    g_spi_bit_order = bit_order;
    /* 简化：SPI 时钟由 CubeMX 初始配置决定，运行期改速率需重新 Init；
       这里记录参数，HAL_SPI_Init 重建见 CubeMX 文档。 */
}

int br_spi_transfer(uint8_t cs, const uint8_t *tx, uint16_t len, uint8_t *rx)
{
    /* CS 拉低（cs 为 GPIO 索引，映射见 CubeMX 配置） */
    (void)cs;
    HAL_StatusTypeDef st = HAL_SPI_TransmitReceive(&hspi1, (uint8_t *)tx, rx, len, 100);
    /* CS 拉高 */
    return (st == HAL_OK) ? 0 : -1;
}

void br_spi_listen(uint8_t enable)
{
    /* 被动监听 SPI 需从机模式或逻辑抓取；暂留 TODO。 */
    (void)enable;
}

/* ---- 逻辑抓取（TIM+DMA 采样 GPIO，待 CubeMX 配置后实现）---- */
void br_logic_cfg(uint32_t hz, uint8_t mask, uint8_t trig_ch, uint8_t trig_edge)
{
    (void)hz; (void)mask; (void)trig_ch; (void)trig_edge;
    /* TODO：配置 TIM 触发频率 = hz，DMA 采样 GPIOx->IDR 到环形缓冲 */
}

void br_logic_start(void)
{
    /* TODO：启动 TIM+DMA */
}

void br_logic_stop(void)
{
    /* TODO：停止并分块经 LOGIC_DATA 回传（在 br_app_poll 里检查缓冲） */
}

int br_logic_get(uint8_t *out, uint16_t max, uint16_t *count, uint16_t *block_seq)
{
    (void)out; (void)max; (void)count; (void)block_seq;
    return 0;   /* TODO: TIM+DMA 采样 */
}

/* ---- 目标外设数据上报入口（供各 HAL 回调调用）---- */
void br_hal_report_data(uint8_t channel, uint8_t dir, const uint8_t *data, uint16_t len)
{
    if (g_cb)
        g_cb(channel, dir, br_timestamp_us(), data, len);
}
