/* startup_stm32f103c8.s — 最小启动文件（向量表 + Reset_Handler） */
.syntax unified
.cpu cortex-m3
.thumb

.section .isr_vector, "a", %progbits
.word _estack
.word Reset_Handler
.word NMI_Handler
.word HardFault_Handler
.word MemManage_Handler
.word BusFault_Handler
.word UsageFault_Handler
.word 0
.word 0
.word 0
.word 0
.word SVC_Handler
.word DebugMon_Handler
.word 0
.word PendSV_Handler
.word SysTick_Handler
.rept 60
.word Default_Handler
.endr

.section .text
.thumb_func
.global Reset_Handler
.type Reset_Handler, %function
Reset_Handler:
    ldr r0, =_estack
    mov sp, r0

    /* 复制 .data（加载地址 → 运行地址） */
    ldr r0, =_sdata
    ldr r1, =_edata
    ldr r2, =_sidata
    b .Lcopy_cond
.Lcopy:
    ldr r3, [r2], #4
    str r3, [r0], #4
.Lcopy_cond:
    cmp r0, r1
    bne .Lcopy

    /* 清零 .bss */
    ldr r0, =_sbss
    ldr r1, =_ebss
    movs r2, #0
    b .Lzero_cond
.Lzero:
    str r2, [r0], #4
.Lzero_cond:
    cmp r0, r1
    bne .Lzero

    bl SystemInit
    bl main
    b .

.thumb_func
.weak Default_Handler
.type Default_Handler, %function
Default_Handler:
    b .

.weak NMI_Handler
.thumb_set NMI_Handler, Default_Handler
.weak HardFault_Handler
.thumb_set HardFault_Handler, Default_Handler
.weak MemManage_Handler
.thumb_set MemManage_Handler, Default_Handler
.weak BusFault_Handler
.thumb_set BusFault_Handler, Default_Handler
.weak UsageFault_Handler
.thumb_set UsageFault_Handler, Default_Handler
.weak SVC_Handler
.thumb_set SVC_Handler, Default_Handler
.weak DebugMon_Handler
.thumb_set DebugMon_Handler, Default_Handler
.weak PendSV_Handler
.thumb_set PendSV_Handler, Default_Handler
.weak SysTick_Handler
.thumb_set SysTick_Handler, Default_Handler
