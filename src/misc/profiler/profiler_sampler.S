// profiler_sampler.S
#include <profiler_config.h>   // PROFILER_NUM_BINS and PROFILER_COUNT_WIDTH
#include "profiler_priv.h"     // structure member offsets as #defines

// check for a dedicated all-assembly sampler implementation
#if defined(__ARM_ARCH_ISA_THUMB)
    #include "ports/profiler_sampler_thumb.S"

#elif (0)
    #include "ports/profiler_sampler_rv32.S"

#else
    // no dedicated sampler; as a fallback, use a stub IRQ
    // to capture the PC, then pass it to the C binner function

    #if (defined(__ARM_ARCH_PROFILE) && (__ARM_ARCH_PROFILE == 'M'))
        #include "ports/profiler_stub_arm.S"

    #elif (defined(__riscv) && (__riscv_xlen == 32))
        #include "ports/profiler_stub_rv32.S"

    #else
        #error "unsupported architecture"

    #endif  // stub selection
#endif  // sampler selection
