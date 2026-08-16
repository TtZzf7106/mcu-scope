/* main_bridge.c — 桥接固件入口（寄存器级，无 HAL）
 *
 * 主循环：轮询 USART1(PC) RX 喂调度器，USART2(目标) RX 上报，调调度器 poll。
 */
#include "bridge_app.h"

void bridge_hal_reg_poll(void);

void SystemInit(void)
{
    /* 复位默认 HSI 8MHz，无需额外时钟配置（与 target_m1 一致） */
}

int main(void)
{
    br_app_init();
    for (;;) {
        bridge_hal_reg_poll();
        br_app_poll();
    }
}
