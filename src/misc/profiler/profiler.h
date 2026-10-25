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
 * The profiler can be in one of three states, as follows:
 *
 * READY   - ready to begin or resume sampling
 * RUNNING - actively sampling
 * FULL    - stopped because one or more bins or
 *           statistics counters would have overflowed
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
 * 'bin_width' must be a power of 2, between 2 and 2^30,
 * and 'base_address' must be a multiple of 'bin_width';
 * illegal values will return false and have no effect
 * on the profiler's state.
 * The counters can be 1-, 2-, or 4-bytes wide, as set
 * by PROFILER_COUNT_SIZE.  The profiler also counts
 * samples above and below the bin range - those counters
 * are 4-bytes wide regardless of PROFILER_COUNT_SIZE.
 * This function can be called regardless of profiler
 * state; if the profiler is running, it will be stopped.
 * On successful return, state will be READY, and the
 * histogram and statistics counters will all be zero.
 */
bool profiler_setup(uint32_t base_address, uint32_t bin_width);

/**************************************************************
 * Begins sampling the program counter 'sample_frequency'
 * times per second.  The resulting samples are used to build
 * the histogram.  Samples that fall outside of the range
 * covered by the histogram bins are counted as 'above'
 * or 'below'; those counts are accessible by calling
 * 'profiler_read_statistics()'.
 * Can only be called when the profiler is READY, returns
 * false if called while in any other state, or if
 * 'sample_frequency' is zero or is not supported by
 * the system.
 * On successful return, state will be RUNNING.
 * Once running, sampling can be stopped by profiler_stop()
 * and will automatically stop when a sample would cause
 * any bin counter or statistics counter to overflow;
 * that sample is discarded.  This can be detected by
 * calling profiler_is_full().
 */
bool profiler_start(uint32_t sample_frequency);

/**************************************************************
 * Reports if the profiler has stopped sampling due to one
 * or more bins or statistics counters being full.  Use
 * profiler_setup() to reset before starting another run.
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
 * Reads the sample count for a single histogram bin.
 * Returns the specified count, or zero if 'bin_num' is
 * out of range.
 * Can be called when profiler is in any state.
 * Does not stop profiler or change state.
 */
profiler_count_t profiler_read_bin(uint32_t bin_num);

/**************************************************************
 * Reads profiler statistics.  For each non-NULL argument,
 * the value is written to the address given.
 * Can be called when profiler is in any state.
 * 'total' is the sum of all bins plus 'above' and 'below',
 * so it needs to loop over all bins; pass NULL unless it
 * is really needed.  Note that 'total' is a 64-bit number,
 * since 'above', 'below', and bins can all contribute
 * counts.
 * If called while the profiler is running the values are
 * not from the same instant; for accurate results stop
 * the profiler first.
 * Does not stop profiler or change state.
 */
void profiler_read_statistics(uint32_t *above, uint32_t *below,
                              uint64_t *total);

/**************************************************************
 * Reads profiler information.  For each non-NULL argument,
 * the value is written to the address given.
 * 'base_addr' is the starting address of bin 0, and
 * will be a multiple of 'bin_width'.
 * 'bin_width' is the width of each bin, and will be
 * a power of 2.
 * 'num_bins' is the number of bins, and is constant.
 * 'data_addr' is the location of the bin counters.
 * The data is a static array:
 *    profiler_count_t data[PROFILER_NUM_BINS]
 * so data_addr never changes (but the array contents do).
 * Can be called when profiler is in any state.
 * The data is modified by the profiler when it is
 * running and cleared by profiler_setup(); callers
 * should only access when READY or FULL.
 */
void profiler_read_info(uint32_t *base_addr, uint32_t *bin_width,
                        uint32_t *num_bins, const profiler_count_t **data_addr);


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
 * a timer interrupt at 'sample_frequency'.  Must clear
 * any pending interrupt before enabling.  Must return
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
