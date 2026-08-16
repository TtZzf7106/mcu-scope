/* bridge_app.h — 桥接应用调度器 */
#ifndef BRIDGE_APP_H
#define BRIDGE_APP_H

#include <stdint.h>

void br_app_init(void);

/* 把 PC 发来的字节喂入（在 USART1 RX 回调或主循环里调用） */
void br_app_on_pc_bytes(const uint8_t *data, uint32_t len);

/* 周期性任务（主循环调用；逻辑抓取数据分块上传等） */
void br_app_poll(void);

#endif /* BRIDGE_APP_H */
