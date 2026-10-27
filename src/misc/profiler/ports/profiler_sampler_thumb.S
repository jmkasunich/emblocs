// profiler_sampler_thumb.S - assembly implementation of the PC sampler
// this file is intended to be included from profiler_sampler.S

    .syntax unified
    .thumb
    .text

    .global profiler_irq_handler
    .type   profiler_irq_handler, %function

    .thumb_func
profiler_irq_handler:
    /* hardware has stacked r0-r3, r12, lr, pc, xPSR; lr is EXC_RETURN */
    // get structure address from literal pool
    ldr     r1, =profile
    // get PC sample from stack frame
    ldr     r0, [sp, #24]
    // get NUM_BINS and shift_count from structure
    ldr     r2, [r1, #PROFILER_PACKED_VALS_OFFSET]
    // magic number from structure;
    // magic = (0u - ((base_addr >> shift_count) + PROFILER_NUM_BINS))
    ldr     r3, [r1, #PROFILER_MAGIC_NUMBER_OFFSET]
    // convert PC into a bin number; shift count is in low byte of R2
    lsrs    r0, r0, r2
    // discard shift count, get NUM_BINs in R2
    lsrs    r2, r2, #8
    // move valid bins to 0xFFFFFFFF-(NUM_BINS-1) thru 0xFFFFFFFF
    // setting carry if address is above valid bins
    adds    r0, r0, r3
    // branch if above valid bins
    bcs     .Labove
    // move valid bins to 0 thru NUM_BINS-1
    // setting carry if valid
    adds    r0, r0, r2
    // branch if below valid bins
    bcc     .Lbelow
    // make R1 point to bins array inside the structure
    adds    r1, r1, #PROFILER_BINS_OFFSET
    // adjust for bin counter width
#if PROFILER_COUNT_SIZE == 4
    lsls    r0, r0, #2
#elif PROFILER_COUNT_SIZE == 2
    lsls    r0, r0, #1
#endif
    // fetch bin counter value
    // and sign extend if narrower than 32-BINS_OFFSET
    // note: counts are unsigned, but sign extension lets us detect wrap
#if PROFILER_COUNT_SIZE == 4
    ldr     r2, [r1, r0]
#elif PROFILER_COUNT_SIZE == 2
    ldrsh   r2, [r1, r0]
#elif PROFILER_COUNT_SIZE == 1
    ldrsb   r2, [r1, r0]
#endif
    // increment, and set carry on overflow
    adds    r2, r2, #1
    // branch on overflow, don't save the value
    bcs     .Lfull
    // store result back to bin
#if PROFILER_COUNT_SIZE == 4
    str     r2, [r1, r0]
#elif PROFILER_COUNT_SIZE == 2
    strh    r2, [r1, r0]
#elif PROFILER_COUNT_SIZE == 1
    strb    r2, [r1, r0]
#endif
    // done; return from ISR
    bx      lr

.Labove:
    // fetch 'above_count'
    ldr     r2, [r1, #PROFILER_ABOVE_COUNT_OFFSET]
     // increment, and set carry on overflow
    adds    r2, r2, #1
    // branch on overflow, don't save the value
    bcs     .Lfull
    // store result back to bin
    str     r2, [r1, #PROFILER_ABOVE_COUNT_OFFSET]
     // done; return from ISR
    bx      lr

.Lbelow:
    // fetch 'below_count'
    ldr     r2, [r1, #PROFILER_BELOW_COUNT_OFFSET]
     // increment, and set carry on overflow
    adds    r2, r2, #1
    // branch on overflow, don't save the value
    bcs     .Lfull
    // store result back to bin
    str     r2, [r1, #PROFILER_BELOW_COUNT_OFFSET]
     // done; return from ISR
    bx      lr

.Lfull:
    // set state to FULL
    movs    r2, #PROFILER_FULL
    strb    r2, [r1, #PROFILER_STATE_OFFSET]
    // shut down sampling
    // bl clobbers LR, save it and keep 8-byte alignment
    push    {r3, lr}
    bl      profiler_irq_disable
    // pop into PC performs the exception return
    pop     {r3, pc}

    .size   profiler_irq_handler, . - profiler_irq_handler
