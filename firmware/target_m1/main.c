/* main.c — M1 目标端回环+上报固件（寄存器级，无 HAL）
 *
 * 功能：
 *   1. USART1 (PA9=TX, PA10=RX) 115200-8-N-1 回环（收到即发回）；
 *   2. 每 500ms 上报 "ping N\r\n"；
 *   3. PC13 板载 LED 心跳闪烁（证明固件在运行）。
 * 时钟：HSE 8MHz → PLL ×9 = 72MHz（SysTick 1ms）。
 */
#include <stdint.h>

/* ---- RCC ---- */
#define RCC_BASE     0x40021000UL
#define RCC_CR       (*(volatile uint32_t *)(RCC_BASE + 0x00))
#define RCC_CFGR     (*(volatile uint32_t *)(RCC_BASE + 0x04))
#define RCC_APB2ENR  (*(volatile uint32_t *)(RCC_BASE + 0x18))

/* ---- FLASH ---- */
#define FLASH_ACR    (*(volatile uint32_t *)0x40022000UL)

/* ---- GPIOA ---- */
#define GPIOA_BASE   0x40010800UL
#define GPIOA_CRL    (*(volatile uint32_t *)(GPIOA_BASE + 0x00))
#define GPIOA_CRH    (*(volatile uint32_t *)(GPIOA_BASE + 0x04))
#define GPIOA_ODR    (*(volatile uint32_t *)(GPIOA_BASE + 0x0C))

/* ---- GPIOC（板载 LED PC13）---- */
#define GPIOC_BASE   0x40011000UL
#define GPIOC_CRH    (*(volatile uint32_t *)(GPIOC_BASE + 0x04))
#define GPIOC_ODR    (*(volatile uint32_t *)(GPIOC_BASE + 0x0C))

/* ---- USART1 ---- */
#define USART1_BASE  0x40013800UL
#define USART1_SR    (*(volatile uint32_t *)(USART1_BASE + 0x00))
#define USART1_DR    (*(volatile uint32_t *)(USART1_BASE + 0x04))
#define USART1_BRR   (*(volatile uint32_t *)(USART1_BASE + 0x08))
#define USART1_CR1   (*(volatile uint32_t *)(USART1_BASE + 0x0C))

/* ---- SysTick ---- */
#define STK_CTRL     (*(volatile uint32_t *)0xE000E010UL)
#define STK_LOAD     (*(volatile uint32_t *)0xE000E014UL)
#define STK_VAL      (*(volatile uint32_t *)0xE000E018UL)

volatile uint32_t g_tick_ms = 0;

void SystemInit(void)
{
    /* 使用复位默认的 HSI 8MHz（最稳，不依赖外部晶振）。
       若后续要精确 115200 且确认板上有 8MHz 晶振，再在此配置 HSE+PLL 72MHz。 */
}

static void uart_send_byte(uint8_t b)
{
    while (!(USART1_SR & (1u << 7))) { }  /* 等 TXE */
    USART1_DR = b;
}

static void uart_send_str(const char *s)
{
    while (*s)
        uart_send_byte((uint8_t)*s++);
}

static void uart_send_num(uint32_t n)
{
    char buf[12];
    int i = 0;
    if (n == 0) {
        uart_send_byte('0');
        return;
    }
    while (n > 0) {
        buf[i++] = (char)('0' + (n % 10));
        n /= 10;
    }
    while (i > 0)
        uart_send_byte((uint8_t)buf[--i]);
}

void SysTick_Handler(void)
{
    g_tick_ms++;
}

int main(void)
{
    uint32_t last_ping = 0;
    uint32_t counter = 0;

    /* 使能 GPIOA、GPIOC、USART1 时钟（均在 APB2） */
    RCC_APB2ENR |= (1u << 2) | (1u << 4) | (1u << 14);  /* IOPA, IOPC, USART1 */

    /* PA9 = TX (AF 推挽 50MHz)，PA10 = RX (输入上拉) */
    GPIOA_CRH &= ~(0xFFu << 4);
    GPIOA_CRH |= (0xBu << 4) | (0x8u << 8);
    GPIOA_ODR |= (1u << 10);   /* PA10 上拉 */

    /* PC13 = 输出推挽 2MHz（板载 LED） */
    GPIOC_CRH &= ~(0xFu << 20);
    GPIOC_CRH |= (0x2u << 20);

    /* USART1: 115200 8N1，TE + RE + UE */
    USART1_BRR = 0x45;            /* 8MHz / 115200 ≈ 69 (实际 115942, 误差 0.6%) */
    USART1_CR1 = (1u << 13) | (1u << 3) | (1u << 2);

    /* SysTick 1ms */
    STK_LOAD = 8000000u / 1000u - 1u;
    STK_VAL = 0;
    STK_CTRL = (1u << 2) | (1u << 1) | (1u << 0);   /* 内核时钟, 中断, 使能 */

    for (;;) {
        /* 回环 */
        if (USART1_SR & (1u << 5)) {          /* RXNE */
            uint8_t b = (uint8_t)(USART1_DR & 0xFFu);
            uart_send_byte(b);
        }

        /* 周期上报 + LED 心跳 */
        if (g_tick_ms - last_ping >= 500) {
            last_ping = g_tick_ms;
            GPIOC_ODR ^= (1u << 13);           /* 翻转 LED */
            uart_send_str("ping ");
            uart_send_num(counter++);
            uart_send_str("\r\n");
        }
    }
}
