/*
 * profiler_asm_m0.S - assembly implementation of the PC sampler.
 * Thumb-1 (Cortex-M0+).
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

    /* count every sample, before the range check */
    ldr     r1, [r3, #PROFILER_TOTAL_SAMPLES_OFFSET]
    adds    r1, r1, #1
    str     r1, [r3, #PROFILER_TOTAL_SAMPLES_OFFSET]

    /* index = (pc - base_addr) >> shift_count */
    ldr     r2, [r3, #PROFILER_BASE_ADDR_OFFSET]
    subs    r0, r0, r2
    ldrb    r1, [r3, #PROFILER_SHIFT_COUNT_OFFSET]
    lsrs    r0, r1                          @ register shift, sets flags

    /* out of range: ignore */
    ldr     r1, =PROFILER_NUM_BINS
    cmp     r0, r1
    bhs     .Lret

#if PROFILER_COUNT_SHIFT != 0
    lsls    r0, r0, #PROFILER_COUNT_SHIFT   @ index -> byte offset in bins
#endif
    adds    r1, r3, r0                      @ r1 = address of bin (minus BINS_OFFSET)

    /*
     * Increment the bin. A bin is full when its value wraps to zero,
     * which only happens from its maximum value. Same test as the C
     * sampler, without a literal load for the maximum.
     */
#if PROFILER_COUNT_SIZE == 1
    ldrb    r2, [r1, #PROFILER_BINS_OFFSET]
    adds    r2, r2, #1
    uxtb    r2, r2
    strb    r2, [r1, PROFILER_#BINS_OFFSET]
    cmp     r2, #0
    bne     .Lret
#elif PROFILER_COUNT_SIZE == 2
    ldrh    r2, [r1, #PROFILER_BINS_OFFSET]
    adds    r2, r2, #1
    uxth    r2, r2
    strh    r2, [r1, #PROFILER_BINS_OFFSET]
    cmp     r2, #0
    bne     .Lret
#else
    ldr     r2, [r1, #PROFILER_BINS_OFFSET]
    adds    r2, r2, #1
    str     r2, [r1, #PROFILER_BINS_OFFSET]
    cmp     r2, #0
    bne     .Lret
#endif

    /* bin reached its maximum: record FULL and stop the interrupt */
.Lfull:
    movs    r2, #PROFILER_STATE_FULL
    strb    r2, [r3, #PROFILER_STATE_OFFSET]
    push    {r3, lr}                        @ bl clobbers lr; keeps 8-byte alignment
    bl      profiler_irq_disable
    pop     {r3, pc}                        @ pop into pc performs the exception return

.Lret:
    bx      lr                              @ exception return via EXC_RETURN

    .ltorg                                  @ literal pool for =profile and =NUM_BINS
    .size   profiler_irq_handler, . - profiler_irq_handler

#endif // PROFILER_SAMPLER_ASM
