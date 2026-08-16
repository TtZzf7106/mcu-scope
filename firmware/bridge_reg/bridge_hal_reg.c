/* bridge_hal_reg.c — STM32F103 寄存器级外设实现（无 HAL、无 CubeMX）
 *
 * 时钟：复位默认 HSI 8MHz（与 target_m1 一致，不依赖外部晶振）。
 * 引脚：
 *   USART1 PA9=TX / PA10=RX  → PC（经 USB-TTL）
 *   USART2 PA2=TX / PA3=RX   → 目标 UART
 *   I2C1   PB6=SCL / PB7=SDA → 目标 I2C
 *   SPI1   PA5=SCK / PA6=MISO / PA7=MOSI，CS 用 PA4 软件控制
 * 时间戳：DWT 周期计数器（HCLK 8MHz → /8 得 µs）。
 */
#include "bridge_hal.h"
#include "bridge_app.h"
#include "bridge_payloads.h"

/* ================= RCC ================= */
#define RCC_BASE     0x40021000UL
#define RCC_APB2ENR  (*(volatile uint32_t *)(RCC_BASE + 0x18))
#define RCC_APB1ENR  (*(volatile uint32_t *)(RCC_BASE + 0x1C))

/* ================= GPIO ================= */
#define GPIOA 0x40010800UL
#define GPIOB 0x40010C00UL
#define G_CRL(b)  (*(volatile uint32_t *)((b) + 0x00))
#define G_CRH(b)  (*(volatile uint32_t *)((b) + 0x04))
#define G_IDR(b)  (*(volatile uint32_t *)((b) + 0x08))
#define G_ODR(b)  (*(volatile uint32_t *)((b) + 0x0C))
#define G_BSRR(b) (*(volatile uint32_t *)((b) + 0x10))

/* ================= USART ================= */
#define USART1 0x40013800UL
#define USART2 0x40004400UL
#define U_SR(b)  (*(volatile uint32_t *)((b) + 0x00))
#define U_DR(b)  (*(volatile uint32_t *)((b) + 0x04))
#define U_BRR(b) (*(volatile uint32_t *)((b) + 0x08))
#define U_CR1(b) (*(volatile uint32_t *)((b) + 0x0C))

/* ================= SPI1 ================= */
#define SPI1 0x40013000UL
#define S_CR1(b) (*(volatile uint32_t *)((b) + 0x00))
#define S_SR(b)  (*(volatile uint32_t *)((b) + 0x08))
#define S_DR(b)  (*(volatile uint32_t *)((b) + 0x0C))

/* ================= I2C1 ================= */
#define I2C1 0x40005400UL
#define I2_CR1(b)   (*(volatile uint32_t *)((b) + 0x00))
#define I2_CR2(b)   (*(volatile uint32_t *)((b) + 0x04))
#define I2_DR(b)    (*(volatile uint32_t *)((b) + 0x10))
#define I2_SR1(b)   (*(volatile uint32_t *)((b) + 0x14))
#define I2_SR2(b)   (*(volatile uint32_t *)((b) + 0x18))
#define I2_CCR(b)   (*(volatile uint32_t *)((b) + 0x1C))
#define I2_TRISE(b) (*(volatile uint32_t *)((b) + 0x20))

/* ================= DWT ================= */
#define DEMCR      (*(volatile uint32_t *)0xE000EDFCUL)
#define DWT_CTRL   (*(volatile uint32_t *)0xE0001000UL)
#define DWT_CYCCNT (*(volatile uint32_t *)0xE0001004UL)

#define SYSCLK_HZ 8000000UL

static BrDataCallback g_cb = 0;

/* ---- 逻辑抓取状态 ---- */
#define LOGIC_MAX 2000
static uint8_t g_logic_buf[LOGIC_MAX];
static uint16_t g_logic_count = 0;
static uint16_t g_logic_block_seq = 0;
static volatile uint8_t g_logic_ready = 0;
static uint8_t g_logic_mask = 0xFF;
static uint32_t g_logic_delay_ticks = 80;   /* 默认 ~10µs/样本 @8MHz */

static void delay_ticks(uint32_t ticks)
{
    uint32_t start = DWT_CYCCNT;
    while ((DWT_CYCCNT - start) < ticks) { }
}

/* ---- 工具 ---- */
static uint32_t usart_brr(uint32_t fck, uint32_t baud)
{
    return (fck + baud / 2u) / baud;
}

static void usart_init(uint32_t base, uint32_t baud)
{
    U_BRR(base) = usart_brr(SYSCLK_HZ, baud);
    U_CR1(base) = (1u << 13) | (1u << 3) | (1u << 2);  /* UE | TE | RE */
}

static void usart_tx(uint32_t base, const uint8_t *data, uint16_t len)
{
    for (uint16_t i = 0; i < len; i++) {
        while (!(U_SR(base) & (1u << 7))) { }  /* 等 TXE */
        U_DR(base) = data[i];
    }
}

/* ---- I2C 基本操作 ---- */
static int i2c_start(void)
{
    I2_CR1(I2C1) |= (1u << 8);                    /* START */
    for (uint32_t t = 0; t < 10000u; t++) {
        if (I2_SR1(I2C1) & (1u << 0)) return 0;   /* SB 已置 */
    }
    return -1;                                     /* 超时（总线浮空等） */
}

static void i2c_stop(void)
{
    I2_CR1(I2C1) |= (1u << 9);                    /* STOP */
}

static int i2c_wait_addr(void)
{
    for (uint32_t t = 0; t < 10000u; t++) {
        if (I2_SR1(I2C1) & (1u << 1)) {           /* ADDR */
            (void)I2_SR2(I2C1);                   /* 读 SR2 清 ADDR */
            return 0;
        }
        if (I2_SR1(I2C1) & (1u << 9)) {           /* AF = 无应答 */
            i2c_stop();
            return -1;
        }
    }
    i2c_stop();
    return -1;
}

/* ================= 接口实现 ================= */
void br_hal_init(void)
{
    DEMCR |= (1u << 24);                          /* TRCENA */
    DWT_CYCCNT = 0;
    DWT_CTRL |= (1u << 0);                        /* CYCCNTENA */

    /* 时钟：GPIOA、GPIOB、SPI1、USART1 (APB2)；USART2、I2C1 (APB1) */
    RCC_APB2ENR |= (1u << 2) | (1u << 3) | (1u << 12) | (1u << 14);
    RCC_APB1ENR |= (1u << 17) | (1u << 21);

    /* PA0 = 逻辑抓取自测输出（推挽 2MHz） */
    G_CRL(GPIOA) &= ~(0xFu << 0);
    G_CRL(GPIOA) |= (0x2u << 0);

    /* USART1：PA9 TX (AF 推挽)，PA10 RX (输入上拉) */
    G_CRH(GPIOA) &= ~(0xFFu << 4);
    G_CRH(GPIOA) |= (0xBu << 4) | (0x8u << 8);
    G_ODR(GPIOA) |= (1u << 10);
    usart_init(USART1, 115200);

    /* USART2：PA2 TX，PA3 RX */
    G_CRL(GPIOA) &= ~(0xFFu << 8);
    G_CRL(GPIOA) |= (0xBu << 8) | (0x8u << 12);
    G_ODR(GPIOA) |= (1u << 3);
    usart_init(USART2, 115200);

    /* SPI1：PA5 SCK、PA7 MOSI (AF 推挽)，PA6 MISO (浮空输入)，PA4 CS (输出) */
    G_CRL(GPIOA) &= ~(0xFu << 16);
    G_CRL(GPIOA) |= (0x2u << 16);                 /* PA4 输出 2MHz */
    G_CRL(GPIOA) &= ~(0xFFu << 20);
    G_CRL(GPIOA) |= (0xBu << 20) | (0x4u << 24);  /* PA5 AF PP, PA6 输入 */
    G_CRL(GPIOA) &= ~(0xFu << 28);
    G_CRL(GPIOA) |= (0xBu << 28);                 /* PA7 AF PP */
    G_ODR(GPIOA) |= (1u << 4);                    /* CS 默认高 */
    S_CR1(SPI1) = (1u << 2) | (1u << 9) | (1u << 8) | (1u << 6);  /* MSTR,SSM,SSI,SPE */

    /* I2C1：PB6 SCL、PB7 SDA (AF 开漏) */
    G_CRL(GPIOB) &= ~(0xFFu << 24);
    G_CRL(GPIOB) |= (0xFu << 24) | (0xFu << 28);
    I2_CR2(I2C1) = 8;                             /* FREQ = PCLK1 MHz */
    I2_CCR(I2C1) = 40;                            /* 100kHz 标准模式 */
    I2_TRISE(I2C1) = 9;                           /* TRISE = FREQ + 1 */
    I2_CR1(I2C1) = (1u << 0);                     /* PE */
}

void br_hal_set_data_callback(BrDataCallback cb) { g_cb = cb; }

void br_pc_tx(const uint8_t *data, uint16_t len) { usart_tx(USART1, data, len); }

uint32_t br_timestamp_us(void) { return DWT_CYCCNT / (SYSCLK_HZ / 1000000u); }

void br_target_uart_cfg(uint32_t baud, uint8_t data_bits, uint8_t parity, uint8_t stop_bits)
{
    (void)data_bits; (void)parity; (void)stop_bits;   /* 简化：仅波特率 */
    usart_init(USART2, baud);
}
void br_target_uart_write(const uint8_t *data, uint16_t len) { usart_tx(USART2, data, len); }
void br_target_uart_listen(uint8_t enable) { (void)enable; }

int br_i2c_scan(uint8_t *found, uint8_t max)
{
    int n = 0;
    for (uint16_t addr = 0x08; addr <= 0x77 && n < max; addr++) {
        if (i2c_start() != 0) continue;           /* 总线浮空，跳过 */
        I2_DR(I2C1) = (uint8_t)(addr << 1);
        if (i2c_wait_addr() == 0)
            found[n++] = (uint8_t)addr;
        i2c_stop();
    }
    return n;
}

int br_i2c_write(uint8_t addr7, const uint8_t *data, uint16_t len)
{
    if (i2c_start() != 0) return -1;
    I2_DR(I2C1) = (uint8_t)(addr7 << 1);
    if (i2c_wait_addr() != 0) return -1;
    for (uint16_t i = 0; i < len; i++) {
        while (!(I2_SR1(I2C1) & (1u << 7))) { }    /* TxE */
        I2_DR(I2C1) = data[i];
    }
    while (!(I2_SR1(I2C1) & (1u << 2))) { }        /* BTF */
    i2c_stop();
    return 0;
}

int br_i2c_read(uint8_t addr7, uint16_t len, uint8_t *out)
{
    if (len == 0) return 0;
    if (i2c_start() != 0) return -1;
    I2_DR(I2C1) = (uint8_t)((addr7 << 1) | 1u);
    if (i2c_wait_addr() != 0) return -1;

    if (len == 1) {
        I2_CR1(I2C1) &= ~(1u << 10);               /* 单字节：NACK */
        I2_CR1(I2C1) |= (1u << 9);                 /* STOP */
        while (!(I2_SR1(I2C1) & (1u << 6))) { }    /* RxNE */
        out[0] = (uint8_t)I2_DR(I2C1);
        return 0;
    }

    I2_CR1(I2C1) |= (1u << 10);                    /* ACK=1 收前 len-1 字节 */
    for (uint16_t i = 0; i < len - 1; i++) {
        while (!(I2_SR1(I2C1) & (1u << 6))) { }    /* RxNE */
        out[i] = (uint8_t)I2_DR(I2C1);
    }
    I2_CR1(I2C1) &= ~(1u << 10);                   /* 末字节 NACK */
    I2_CR1(I2C1) |= (1u << 9);                     /* STOP */
    while (!(I2_SR1(I2C1) & (1u << 6))) { }        /* RxNE */
    out[len - 1] = (uint8_t)I2_DR(I2C1);
    return 0;
}
void br_i2c_listen(uint8_t enable) { (void)enable; }

void br_spi_cfg(uint32_t hz, uint8_t mode, uint8_t bit_order)
{
    (void)hz; (void)mode; (void)bit_order;         /* 简化：固定 8MHz/16=500kHz */
}

int br_spi_transfer(uint8_t cs, const uint8_t *tx, uint16_t len, uint8_t *rx)
{
    (void)cs;
    G_ODR(GPIOA) &= ~(1u << 4);                    /* CS 拉低 */
    for (uint16_t i = 0; i < len; i++) {
        while (!(S_SR(SPI1) & (1u << 1))) { }      /* TXE */
        S_DR(SPI1) = tx ? tx[i] : 0xFFu;
        while (!(S_SR(SPI1) & (1u << 0))) { }      /* RXNE */
        if (rx) rx[i] = (uint8_t)S_DR(SPI1);
    }
    G_ODR(GPIOA) |= (1u << 4);                     /* CS 拉高 */
    return 0;
}
void br_spi_listen(uint8_t enable) { (void)enable; }

void br_logic_cfg(uint32_t hz, uint8_t mask, uint8_t trig_ch, uint8_t trig_edge)
{
    (void)trig_ch; (void)trig_edge;
    g_logic_mask = mask;
    uint32_t ticks = SYSCLK_HZ / hz;              /* 每样本 tick 数（近似） */
    g_logic_delay_ticks = ticks > 20 ? ticks - 20 : 1;
    g_logic_count = 0;
    g_logic_ready = 0;
}

void br_logic_start(void)
{
    g_logic_count = 0;
    g_logic_ready = 0;
    for (uint16_t i = 0; i < LOGIC_MAX; i++) {
        /* 自测信号：每 50 样本翻转 PA0，产生 ~周期 100 样本的方波 */
        if ((i % 100) < 50)
            G_BSRR(GPIOA) = (1u << 0);            /* PA0 高 */
        else
            G_BSRR(GPIOA) = (1u << 16);           /* PA0 低 */
        g_logic_buf[i] = (uint8_t)(G_IDR(GPIOA) & g_logic_mask);
        delay_ticks(g_logic_delay_ticks);
    }
    g_logic_count = LOGIC_MAX;
    g_logic_ready = 1;
}

void br_logic_stop(void)
{
    /* 阻塞式抓取在 start 内完成，stop 为空操作 */
}

int br_logic_get(uint8_t *out, uint16_t max, uint16_t *count, uint16_t *block_seq)
{
    if (!g_logic_ready)
        return 0;
    uint16_t n = g_logic_count < max ? g_logic_count : max;
    for (uint16_t i = 0; i < n; i++)
        out[i] = g_logic_buf[i];
    *count = n;
    *block_seq = g_logic_block_seq++;
    g_logic_ready = 0;
    return 1;
}

/* ---- 轮询：USART1 RX → 调度器；USART2 RX → 数据回调(EVENT) ---- */
void bridge_hal_reg_poll(void)
{
    while (U_SR(USART1) & (1u << 5)) {             /* RXNE */
        uint8_t b = (uint8_t)U_DR(USART1);
        br_app_on_pc_bytes(&b, 1);
    }
    while (U_SR(USART2) & (1u << 5)) {             /* RXNE */
        uint8_t b = (uint8_t)U_DR(USART2);
        if (g_cb)
            g_cb(BP_CH_UART, BP_DIR_RX, br_timestamp_us(), &b, 1);
    }
}
