/* profiler_config.h
 *
 * This file is a template - it should be copied to your project
 * and edited as needed.  Remove the #warn statement and add your
 * own values for PROFILER_COUNT_SIZE and PROFILER_NUM_BINS.
 */
#ifndef PROFILER_CONFIG_H
#define PROFILER_CONFIG_H

/* remove this warning after copying the template */
#warning "Using template profiler_config.h; copy and edit for your project"

/* Width in bytes of each in-range bin counter: 1, 2, or 4.
 * Wider counters hold larger counts but use more RAM.
 */
#define PROFILER_COUNT_SIZE 2

/* Number of histogram bins. More bins give finer resolution
 * but use more RAM. Must be at least 4 and at most 0xFFFFFF.
 */
#define PROFILER_NUM_BINS 256

#endif // PROFILER_CONFIG_H
