// profiler_sampler_rv32.S - assembly implementation of the PC sampler
// this file is intended to be included from profiler_sampler.S

    .text

    .global profiler_irq_handler
    .type   profiler_irq_handler, @function

profiler_irq_handler:
    // make space on stack to save registers
    addi    sp, sp, -16
    // save a0-a3
    sw      a0, 0(sp)
    sw      a1, 4(sp)
    sw      a2, 8(sp)
    sw      a3, 12(sp)
    // get structure address
    la      a1, profile
    // get PC sample from mepc register
    csrr    a0, mepc
    // get base address from structure;
    lw      a3, PROFILER_BASE_ADDR_OFFSET(a1)
    // get NUM_BINS and shift_count from structure
    lw      a2, PROFILER_PACKED_VALS_OFFSET(a1)
    // check if PC is below base_addr, branch if yes
    bltu    a0, a3, .Lbelow
    // make bottom of bin 0 = 0
    sub     a0, a0, a3
    // convert PC into a bin number; shift count is in low byte of A2
    srl     a0, a0, a2
    // discard shift count, get NUM_BINs in A2
    srli    a2, a2, 8
    // check if above top bin, branch if yes
    bgeu    a0, a2, .Labove
    // adjust for bin counter width
#if PROFILER_COUNT_SIZE == 4
    slli    a0, a0, 2
#elif PROFILER_COUNT_SIZE == 2
    slli    a0, a0, 1
#endif
    // make A0 = profile + scaled bin number
    add     a0, a0, a1
    // fetch bin counter value
    // and sign extend if narrower than 32-BINS_OFFSET
    // note: counts are unsigned, but sign extension lets us detect wrap
#if PROFILER_COUNT_SIZE == 4
    lw      a2, PROFILER_BINS_OFFSET(a0)
#elif PROFILER_COUNT_SIZE == 2
    lh      a2, PROFILER_BINS_OFFSET(a0)
#elif PROFILER_COUNT_SIZE == 1
    lb      a2, PROFILER_BINS_OFFSET(a0)
#endif
    // increment the bin counter
    addi    a2, a2, 1
    // branch on overflow, don't save the value
    beqz    a2, .Lfull
    // store result back to bin
#if PROFILER_COUNT_SIZE == 4
    sw      a2, PROFILER_BINS_OFFSET(a0)
#elif PROFILER_COUNT_SIZE == 2
    sh      a2, PROFILER_BINS_OFFSET(a0)
#elif PROFILER_COUNT_SIZE == 1
    sb      a2, PROFILER_BINS_OFFSET(a0)
#endif
.Ldone:
    // done; restore saved registers
    lw      a0,  0(sp)
    lw      a1,  4(sp)
    lw      a2,  8(sp)
    lw      a3, 12(sp)
    // discard stack frame
    addi    sp, sp, 16
    // return from ISR
    mret

.Labove:
    // fetch 'above_count'
    lw      a2, PROFILER_ABOVE_COUNT_OFFSET(a1)
    // increment the bin counter
    addi    a2, a2, 1
    // branch on overflow, don't save the value
    beqz    a2, .Lfull
    // store result back to bin
    sw      a2, PROFILER_ABOVE_COUNT_OFFSET(a1)
     // done; return from ISR
    j       .Ldone

.Lbelow:
    // fetch 'below_count'
    lw      a2, PROFILER_BELOW_COUNT_OFFSET(a1)
    // increment the bin counter
    addi    a2, a2, 1
    // branch on overflow, don't save the value
    beqz    a2, .Lfull
    // store result back to bin
    sw      a2, PROFILER_BELOW_COUNT_OFFSET(a1)
     // done; return from ISR
    j       .Ldone

.Lfull:
    // set state to FULL
    li      a2, PROFILER_FULL
    sb      a2, PROFILER_STATE_OFFSET(a1)
    // shut down sampling
    // we're going to call C, so we need to save more state
    // a0-a3 were already saved
    // Allocate additional stack frame: 12 registers x 4 bytes
    addi    sp, sp, -48
    // Conservatively save every register that a C function
    // is allowed to destroy according to the ABI
    sw      ra, 0(sp)
    sw      a4, 4(sp)
    sw      a5, 8(sp)
    sw      a6, 12(sp)
    sw      a7, 16(sp)
    sw      t0, 20(sp)
    sw      t1, 24(sp)
    sw      t2, 28(sp)
    sw      t3, 32(sp)
    sw      t4, 36(sp)
    sw      t5, 40(sp)
    sw      t6, 44(sp)
    // disable the interrupt
    call    profiler_irq_disable
    // restore saved registers
    lw      ra, 0(sp)
    lw      a4, 4(sp)
    lw      a5, 8(sp)
    lw      a6, 12(sp)
    lw      a7, 16(sp)
    lw      t0, 20(sp)
    lw      t1, 24(sp)
    lw      t2, 28(sp)
    lw      t3, 32(sp)
    lw      t4, 36(sp)
    lw      t5, 40(sp)
    lw      t6, 44(sp)
    // discard second stack frame
    addi    sp, sp, 48
    // restore a0-a3 and return to interrupted code
    j       .Ldone

    .size   profiler_irq_handler, . - profiler_irq_handler
