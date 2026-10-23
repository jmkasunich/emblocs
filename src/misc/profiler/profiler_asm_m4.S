/*
 * profiler_asm_m4.S - assembly implementation of the PC sampler.
 * Thumb-2 (Cortex-M4).
 * Built only when PROFILER_SAMPLER_ASM is defined.
 * Layout and configuration come from profiler_asm.h, which must match
 * profile_t in profiler.c.
 */
#include "profiler_config.h"
#include "profiler_priv.h"

#ifdef PROFILER_SAMPLER_ASM

/* log2 of the bin size in bytes, for scaling a bin index into an offset */
#if PROFILER_COUNT_SIZE == 1
#define PROFILER_COUNT_SHIFT 0
#elif PROFILER_COUNT_SIZE == 2
#define PROFILER_COUNT_SHIFT 1
#else
#define PROFILER_COUNT_SHIFT 2
#endif

    .syntax unified
    .thumb
    .text
    .global profiler_irq_handler
    .type   profiler_irq_handler, %function
    .thumb_func
profiler_irq_handler:
    /* hardware has stacked r0-r3, r12, lr, pc, xPSR; lr is EXC_RETURN */
    ldr     r0, [sp, #24]                   @ stacked PC
    ldr     r3, =profile                    @ &profile
    ldr     r2, [r3, #PROFILER_BASE_ADDR_OFFSET]
    ldr     r1, [r3, #PROFILER_TOTAL_SAMPLES_OFFSET]
    adds    r1, r1, #1                      @ count every sample
    str     r1, [r3, #PROFILER_TOTAL_SAMPLES_OFFSET]
    subs    r0, r0, r2                      @ pc - base_addr
    ldrb    r2, [r3, #PROFILER_SHIFT_COUNT_OFFSET]
    lsr     r0, r0, r2                      @ bin index
    movw    r2, #PROFILER_NUM_BINS
    cmp     r0, r2
    bhs     .Lret                           @ out of range: ignore

    add     r1, r3, r0, lsl #PROFILER_COUNT_SHIFT   @ address of bin

#if PROFILER_COUNT_SIZE == 1
    ldrb    r2, [r1, #PROFILER_BINS_OFFSET]
    adds    r2, r2, #1
    uxtb    r2, r2
    strb    r2, [r1, #PROFILER_BINS_OFFSET]
    cmp     r2, #0xFF
#elif PROFILER_COUNT_SIZE == 2
    ldrh    r2, [r1, #PROFILER_BINS_OFFSET]
    adds    r2, r2, #1
    uxth    r2, r2
    strh    r2, [r1, #PROFILER_BINS_OFFSET]
    movw    r0, #0xFFFF
    cmp     r2, r0
#else
    ldr     r2, [r1, #PROFILER_BINS_OFFSET]
    adds    r2, r2, #1
    str     r2, [r1, #PROFILER_BINS_OFFSET]
    cmn     r2, #1                          @ r2 == 0xFFFFFFFF ?
#endif
    bne     .Lret                           /* bin not full */

    /* bin reached its maximum: record FULL and stop the interrupt */
    movs    r2, #PROFILER_STATE_FULL
    strb    r2, [r3, #PROFILER_STATE_OFFSET]
    push    {r3, lr}                        @ keep lr (EXC_RETURN) and 8-byte alignment
    bl      profiler_irq_disable
    pop     {r3, pc}                        @ pop into pc performs the exception return

.Lret:
    bx      lr                              @ exception return via EXC_RETURN

    .ltorg                                  @ literal pool for =profile
    .size   profiler_irq_handler, . -