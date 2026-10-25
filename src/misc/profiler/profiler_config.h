#ifndef PROFILER_CONFIG_H
#define PROFILER_CONFIG_H

/* configuration - should be defined by the build system */
/* note that RAM usage is approximately
 *    PROFILER_COUNT_SIZE * PROFILER_NUM_BINS + 24 bytes
 */

// each bin counter can be 1, 2, or 4 bytes
// this is a tradeoff between memory usage and maximum count
#ifndef PROFILER_COUNT_SIZE
#warning "PROFILER_COUNT_SIZE undefined, defaulting to 1 byte"
#define PROFILER_COUNT_SIZE 1
#endif

// more bins provide more information but require more RAM
#ifndef PROFILER_NUM_BINS
#warning "PROFILER_NUM_BINS undefined, defaulting to 200 bins"
#define PROFILER_NUM_BINS 200
#endif

// the C implementation emphasizes portability, the assembly focuses on speed
#if !defined PROFILER_SAMPLER_C && !defined PROFILER_SAMPLER_ASM
#warning "Neither PROFILER_SAMPLER_C nor PROFILER_SAMPLER_ASM defined, defaulting to PROFILER_SAMPLER_C"
#define PROFILER_SAMPLER_C
#endif

/* validate the configuration data */
#if ( (PROFILER_COUNT_SIZE != 1) &&  \
      (PROFILER_COUNT_SIZE != 2) &&  \
      (PROFILER_COUNT_SIZE != 4) )
#error "PROFILER_COUNT_SIZE must be 1, 2, or 4 bytes"
#endif

#if PROFILER_NUM_BINS < 4
#error "PROFILER_NUM_BINS must be at least 4"
#endif

#if PROFILER_NUM_BINS > 0xFFFFFF
#error "PROFILER_NUM_BINS cannot exceed 0xFFFFFF"
#endif

#if defined(PROFILER_SAMPLER_C) && defined(PROFILER_SAMPLER_ASM)
#error "Define only one of PROFILER_SAMPLER_C or PROFILER_SAMPLER_ASM"
#endif

#endif // PROFILER_CONFIG_H
