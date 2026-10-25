/**
 * @file profiler_config.h
 * Build-time configuration for the profiler.
 *
 * Each option below can be set by the build system, for example with
 * -D on the compiler command line. If an option is not set, its default
 * is used and a warning is issued. Every final value is checked at the
 * end of this file, whatever its source.
 *
 * This header is included by both C and assembly sources, so it
 * contains only preprocessor directives and comments.
 *
 * RAM used by the histogram is approximately
 * PROFILER_COUNT_SIZE * PROFILER_NUM_BINS + 24 bytes.
 */
#ifndef PROFILER_CONFIG_H
#define PROFILER_CONFIG_H

/**
 * Width in bytes of each in-range bin counter: 1, 2, or 4.
 * Wider counters hold larger counts but use more RAM.
 * Default: 1.
 */
#ifndef PROFILER_COUNT_SIZE
#warning "PROFILER_COUNT_SIZE not defined; using default from profiler_config.h"
#define PROFILER_COUNT_SIZE 1
#endif

/**
 * Number of histogram bins. More bins give finer resolution
 * but use more RAM. Must be at least 4 and at most 0xFFFFFF.
 * Default: 200.
 */
#ifndef PROFILER_NUM_BINS
#warning "PROFILER_NUM_BINS not defined; using default from profiler_config.h"
#define PROFILER_NUM_BINS 200
#endif

/**
 * Selects the sampler implementation. Define exactly one of:
 *   - @c PROFILER_SAMPLER_C: portable C implementation.
 *   - @c PROFILER_SAMPLER_ASM: assembly implementation, optimized for speed.
 * Only whether each macro is defined matters; its value is ignored.
 * Default: @c PROFILER_SAMPLER_C.
 */
#if !defined PROFILER_SAMPLER_C && !defined PROFILER_SAMPLER_ASM
#warning "No sampler selected; using PROFILER_SAMPLER_C from profiler_config.h"
#define PROFILER_SAMPLER_C
#endif

/* Validation: applies to the final value of each option, whatever its source. */

#if ( (PROFILER_COUNT_SIZE != 1) &&  \
      (PROFILER_COUNT_SIZE != 2) &&  \
      (PROFILER_COUNT_SIZE != 4) )
#error "PROFILER_COUNT_SIZE must be 1, 2, or 4 bytes"
#endif

/* some of the math breaks down for bin counts less than four;
   any realistic histogram will have many more bins */
#if PROFILER_NUM_BINS < 4
#error "PROFILER_NUM_BINS must be at least 4"
#endif

/* we pack PROFILER_NUM_BINS and shift_count into a single word;
   NUM_BINS gets three bytes, shift_count gets one */
#if PROFILER_NUM_BINS > 0xFFFFFF
#error "PROFILER_NUM_BINS cannot exceed 0xFFFFFF"
#endif

#if defined(PROFILER_SAMPLER_C) && defined(PROFILER_SAMPLER_ASM)
#error "Define only one of PROFILER_SAMPLER_C or PROFILER_SAMPLER_ASM"
#endif

#endif /* PROFILER_CONFIG_H */
