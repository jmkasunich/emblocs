/**************************************************************
 * profiler.h - API for sample based profiling
 * 
 */
#ifndef PROFILER_H
#define PROFILER_H

#include <stdint.h>
#include <stdbool.h>
// configuration is by -D options from the build system
// profiler_config.h validates and provides defaults
#include "profiler_config.h"


#if PROFILER_COUNT_SIZE == 1
typedef uint8_t profiler_count_t;
#elif PROFILER_COUNT_SIZE == 2
typedef uint16_t profiler_count_t;
#elif PROFILER_COUNT_SIZE == 4
typedef uint32_t profiler_count_t;
#endif

/**************************************************************
 * The profiler can be in one of several states, as follows:
 *
 * RESET   - uninitialized; before first profiler_setup() call
 * READY   - ready to begin or resume sampling
 * RUNNING - actively sampling
 * FULL    - stopped; one or more bins reached max count
 * READOUT - data is ready for bulk readout
 *
 * Some of the API functions only work in certain states, as
 * documented in the function descriptions below.
 *
 */

/**************************************************************
 * Prepares the profiler to sample the program counter and
 * build a histogram with PROFILER_NUM_BINS bins, each
 * covering 'bin_width' bytes of address space starting
 * at 'base_address'.  Each bin counts the number of samples
 * inside that address range. 
 * 'bin_width' must be a power of 2, between 2 and 2^24,
 * and 'base_address' must be even; illegal values will
 * return false and have no effect on profiler state.
 * Can be called regardless of profiler state; if the
 * profiler is running, it will be stopped.
 * On successful return, state will be READY, and the
 * histogram and total sample counters will all be zero.
 */
bool profiler_setup(uint32_t base_address, uint32_t bin_width);

/**************************************************************
 * Begins sampling the program counter 'sample_frequency'
 * times per second.  The resulting samples are used to build
 * the histogram.  Samples that fall outside of the range
 * covered by the histogram bins are ignored, but the total
 * number of samples is tracked in a 32-bit counter.
 * Can only be called when the profiler is READY, returns
 * false if called while in any other state, or if
 * 'sample_frequency' is not supported by the system.
 * On successful return, state will be RUNNING.
 * Once running, sampling will stop if any bin counter
 * reaches its limit; this may be checked by calling
 * profiler_is_full().
 */
bool profiler_start(uint32_t sample_frequency);

/**************************************************************
 * Reports if the profiler has stopped sampling due to one
 * or more bins being full.
 */
bool profiler_is_full(void);

/**************************************************************
 * Stops sampling the program counter.
 * Only meaningful when state is RUNNING; returns false
 * and does nothing if called while in any other state.
 * On successful return, state will be READY.
 */
bool profiler_stop(void);

/**************************************************************
 * Prepares sample count histogram for readout.
 * Returns a pointer to an array of PROFILER_NUM_BINS
 * count values.
 * Can be called when profiler is in any state except
 * RESET; returns NULL if called while in reset state.
 * If the profiler is running, it will be stopped.
 * On successful return the state is READOUT.
 * The returned pointer can be used until profiler_setup()
 * is called to prepare for the next acquisition.
 */
profiler_count_t *profiler_read(void);

/**************************************************************
 * Reads the sample count for a single histogram bin.
 * Returns the specified count, or zero if 'bin_num' is
 * out of range.
 * Can be called when profiler is in any state except
 * RESET; returns zero if called while in reset state.
 * Does not stop profiler or change state.
 */
profiler_count_t profiler_read_bin(uint32_t bin_num);

/**************************************************************
 * Reads the total number of samples captured, including
 * those that fall outside the histogram bins.
 * Can be called when profiler is in any state except
 * RESET; returns zero if called while in reset state.
 * Note that at a 100KHz rate this counter will wrap modulo
 * 2^32 in about 11 hours; this is not detected or handled.
 * Does not stop profiler or change state.
 */
uint32_t profiler_read_total(void);


/**************************************************************
 * The following are used to implement the profiler.
 * The IRQ is provided by the profiler, the two helper
 * functions must be provided by the platform.
 */

/**************************************************************
 * The IRQ that handles sampling of the PC.  This function
 * must be placed in the interrupt vector table and should
 * not be called directly.
 */
void profiler_irq_handler(void);

/**************************************************************
 * Helper function that must be provided by the platform.
 * Do not call directly.
 * Must result in profiler_irq_handler() being called from
 * a timer interrupt at 'sample_frequency'.  Should clear
 * any pending interrupt before enabling.  Should return
 * false if the platform cannot operate at the requested
 * frequency.
 */
extern bool profiler_irq_enable(uint32_t sample_frequency);

/**************************************************************
 * Helper function that must be provided by the platform.
 * Do not call directly.
 * Must stop calls to profiler_irq_handler().  Must be
 * callable from interrupt context.
 */
extern void profiler_irq_disable(void);

#endif // PROFILER_H
