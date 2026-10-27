// profiler_stub_arm.S  - ARM Cortex-M stub
// this file is intended to be included from profiler_sampler.S

    .syntax unified
    .thumb
    .text

    .global profiler_irq_handler
    .type   profiler_irq_handler, %function

profiler_irq_handler:
    // Cortex-M saves context in hardware
    // capture the program counter
    ldr     r0, [sp, #24]  // PC is at SP + 24 on Cortex-M
    // Branch to C function
    // it will return directly to the interrupted code
    b       profiler_bin_sample

    .size profiler_irq_handler, .-profiler_irq_handler
