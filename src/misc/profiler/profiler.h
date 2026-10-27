/**
 * @file profiler.h
 * @brief API for sample-based profiling.
 * 
 * @section profiler_config Configuration
 *
 * Config is set by #define's in profiler_config.h; users should
 * put a copy of this file somewhere in their project include
 * path and edit as needed.  There are two configuration items:
 *
 * @c PROFILER_NUM_BINS - the number of bins in the histogram.
 *       From 4 to 16777215 (0xFFFFFF).
 * @c PROFILER_COUNT_SIZE - the width of each bin counter, in bytes.
 *       Must be 1, 2, or 4; determines how soon the bins become full.
 *
 * RAM used by the histogram is approximately
 * PROFILER_COUNT_SIZE * PROFILER_NUM_BINS + 24 bytes.
 *
 * @section profiler_threading  Multi-Core and Thread Safety
 *
 * The profiler is intended to profile code running on a single core.
 * The API is not reentrant and is not safe for use from more than one
 * core.  Call all functions from a single thread of control, not an
 * interrupt handler.  The only asynchronous activity is the sampling
 * interrupt, which must be serviced by the same core that calls the
 * API.
 *
 * @section profiler_states Profiler States
 *
 * The profiler is always in one of the following states:
 *
 * - @c RESET   - before the first successful call to profiler_setup()
 * - @c READY   - ready to begin or resume sampling
 * - @c RUNNING - actively sampling
 * - @c FULL    - stopped because one or more bins or
 *                statistics counters would have overflowed
 */

#ifndef PROFILER_H
#define PROFILER_H

#include <stdint.h>
#include <stdbool.h>
#include <profiler_config.h>

/**
 * @brief Type of each in-range histogram bin counter.
 *
 * The width is set by @ref PROFILER_COUNT_SIZE: uint8_t for 1 byte,
 * uint16_t for 2 bytes, or uint32_t for 4 bytes.  A counter holds values
 * from 0 to the maximum of its type.  If a bin or statistics counter
 * would overflow, the profiler enters @c FULL (see @ref profiler_states).
 *
 * Counters for samples outside the bin range are always 4 bytes wide,
 * regardless of this type.
 */
#if PROFILER_COUNT_SIZE == 1
typedef uint8_t profiler_count_t;
#elif PROFILER_COUNT_SIZE == 2
typedef uint16_t profiler_count_t;
#elif PROFILER_COUNT_SIZE == 4
typedef uint32_t profiler_count_t;
#else
#error "PROFILER_COUNT_SIZE must be 1, 2, or 4 bytes; see profiler_config.h"
#endif

#if ( (PROFILER_NUM_BINS < 4) || \
      (PROFILER_NUM_BINS > 0xFFFFFF ) )
#error "PROFILER_NUM_BINS must be >= 4 and <= 0xFFFFFF; see profiler_config.h"
#endif

/**
 * @brief Prepares the profiler to sample the program counter and
 *        build a histogram.
 *
 * The histogram has @c PROFILER_NUM_BINS bins.  Each bin covers
 * @p bin_width bytes of address space, starting at @p base_address.
 * Each bin counts the samples that fall inside its address range.
 *
 * If the profiler is running, it is stopped first.
 *
 * @param[in] base_address  Start of the histogram address range.
 *                          Must be a multiple of @p bin_width.
 * @param[in] bin_width     Bytes covered by each bin.  Must be a
 *                          power of 2, from 2 to 2^30 inclusive.
 *
 * @return true on success; false if an argument is illegal.  On false,
 *         the profiler's state is unchanged.
 *
 * @pre  Any profiler state is acceptable (see @ref profiler_states).
 * @post On success, the profiler is in state @c READY and the
 *       histogram and all statistics counters are zero.
 *
 * @note The bin counters are 1, 2, or 4 bytes wide, as set by
 *       @c PROFILER_COUNT_SIZE.  Samples above and below the bin
 *       range are counted in separate 4-byte counters regardless
 *       of @c PROFILER_COUNT_SIZE.
 *
 * @see PROFILER_NUM_BINS
 * @see PROFILER_COUNT_SIZE
 */
bool profiler_setup(uint32_t base_address, uint32_t bin_width);

/**
 * @brief Starts sampling the program counter.
 *
 * Samples the program counter @p sample_frequency times per second.
 * Each sample inside a histogram bin's address range increments that
 * bin's counter.  Samples outside the bin range are counted as "above"
 * or "below"; read these counts with @ref profiler_read_statistics().
 *
 * Sampling continues until @ref profiler_stop() is called.  It also stops
 * automatically if a sample would overflow any bin or statistics counter.
 * That sample is discarded, and @ref profiler_is_full() reports the
 * condition.  Once full, sampling cannot be restarted until
 * @ref profiler_setup() is called to reset the counters.
 *
 * @param[in] sample_frequency  Samples per second.  Must be nonzero and
 *                              supported by the system.
 *
 * @return true if sampling started.  false if @p sample_frequency is zero
 *         or unsupported, or if the profiler is not in state @c READY.
 *
 * @pre  Profiler is in state @c READY (see @ref profiler_states).
 * @post Profiler is in state @c RUNNING.
 */
bool profiler_start(uint32_t sample_frequency);

/**
 * @brief Stops sampling the program counter.
 *
 * Histogram and statistics counters hold their values, so they can
 * be read.  Counting can be resumed from the present values by
 * calling @ref profiler_start(), or @ref profiler_setup() can be
 * called to clear the counters and prepare for a new run.
 *
 * @return true if sampling was stopped.  false if the profiler is not
 *         in state @c RUNNING, in which case nothing changes.
 *
 * @pre  Profiler is in state @c RUNNING (see @ref profiler_states).
 * @post Profiler is in state @c READY.
 */
bool profiler_stop(void);

/**
 * @brief Reports whether sampling has stopped and the data can be read.
 *
 * Returns true in state @c READY or @c FULL.  Returns false in state
 * @c RESET, where no sampling has been set up, and in state @c RUNNING,
 * where the counters may change at any moment.
 *
 * @return true if the profiler is @c READY or @c FULL.
 */
bool profiler_is_stopped(void);

/**
 * @brief Reports whether the profiler is sampling.
 *
 * @return true if the profiler is in state @c RUNNING.
 */
bool profiler_is_running(void);

/**
 * @brief Reports whether the profiler has filled up.
 *
 * Returns true in state @c FULL, which means sampling stopped
 * automatically because a bin or statistics counter would have
 * overflowed.  The sample that would have overflowed was discarded,
 * so the counters are still valid and can be read.
 *
 * A full profiler cannot resume sampling.  Call @ref profiler_setup()
 * to clear the counters and begin a new run.
 *
 * @return true if the profiler is in state @c FULL.
 */
bool profiler_is_full(void);

/**
 * @brief Reads the histogram layout.
 *
 * Each non-NULL argument receives its value.  @p base_addr and
 * @p bin_width are set by @ref profiler_setup().  @p num_bins
 * and @p data_addr are constant for the build.
 *
 * @param[out] base_addr  First address in bin 0.  A multiple of @p bin_width.
 * @param[out] bin_width  Number of bytes covered by each bin.  A power of 2.
 * @param[out] num_bins   Number of bins, equal to @ref PROFILER_NUM_BINS.
 * @param[out] data_addr  Location of the array of bin counters.  The data
 *                        values at this address change while the profiler
 *                        is running, and @ref profiler_setup() clears them.
 *                        Read the counters only in state @c READY or
 *                        @c FULL (see @ref profiler_is_stopped()).
 */
void profiler_read_info(uint32_t *base_addr, uint32_t *bin_width,
                        uint32_t *num_bins, const profiler_count_t **data_addr);

/**
 * @brief Reads the above, below, and total sample counts.
 *
 * Each non-NULL argument receives its value.
 * If the profiler is running, the values are not from the same instant.
 * Stop the profiler first for a consistent snapshot.
 *
 * @param[out] above  32-bit count of samples above the histogram range.
 * @param[out] below  32-bit count of samples below the histogram range.
 * @param[out] total  32-bit count of all samples captured; computed by
 *                    summing all bins plus @p above and @p below.  The
 *                    actual total can exceed 2^32; this sum saturates at
 *                    0xFFFFFFFF, at which point @ref profiler_read_total()
 *                    should be called to get the true total as a 64-bit
 *                    number.  Computing the total is O(num_bins) since
 *                    it requires summing every bin; pass NULL unless
 *                    it is needed.
 */
void profiler_read_statistics(uint32_t *above, uint32_t *below,
                              uint32_t *total);

/**
 * @brief Reads the total sample count as a 64-bit number.
 *
 * Long sampling runs (for example, 72 minutes at 1MHz) can acquire more
 * than 2^32 samples.  This function sums all bins plus @c above and
 * @c below into a 64-bit number that will not overflow.
 * Stop the profiler first for an accurate count.
 *
 * @return The sum of all bins, @c above, and @c below.
 */
uint64_t profiler_read_total(void);

/**
 * @brief Reads the sample count for one histogram bin.
 *
 * @param[in] bin_num  Index of the bin, from 0 to @ref PROFILER_NUM_BINS minus 1.
 *
 * @return The count for bin @p bin_num, or 0 if @p bin_num is out of range.
 *         Check @c num_bins from @ref profiler_read_info() to avoid calling
 *         this function on an out-of-range bin.
 */
profiler_count_t profiler_read_bin(uint32_t bin_num);

/**
 * @defgroup platform_hooks Platform Interface
 * @brief Interface between the profiler and the platform.
 *
 * The platform must place profiler_irq_handler() in the
 * interrupt vector table and provide platform-specific
 * implementations of profiler_irq_enable() and
 * profiler_irq_disable().
 * Applications do not call any of these directly.
 * @{
 */

/**
 * @brief Samples the program counter and updates the histogram.
 *
 * Provided by the profiler.  Called by a timer interrupt to
 * sample the program counter.
 * Records the sampled program counter in the matching bin, or
 * in the above or below counter if it is outside the histogram
 * range.  If the sample would overflow any counter, the sample is
 * discarded, sampling is stopped, and the profiler enters state
 * @c FULL.
 *
 * Must be placed in the interrupt vector table.  Do not call directly.
 */
void profiler_irq_handler(void);

/**
 * @brief Enables the platform timer interrupt that drives sampling.
 *
 * Provided by the platform.  Called by @ref profiler_start().
 * Arranges for profiler_irq_handler() to be called from a timer
 * interrupt at @p sample_frequency samples per second.  Any pending
 * interrupt from this timer must be cleared before the interrupt is
 * enabled, so that a stale sample is not delivered.
 * Do not call directly.
 *
 * @param[in] sample_frequency  Samples per second.  Will be nonzero
 *                              when called by the profiler.
 *
 * @return true if sampling is enabled at @p sample_frequency.  false if
 *         the platform cannot operate at that frequency, in which case
 *         no interrupts are enabled.
 *
 * @post Timer interrupts occur at @p sample_frequency, and each one calls
 *       profiler_irq_handler().
 */
extern bool profiler_irq_enable(uint32_t sample_frequency);

/**
 * @brief Disables the platform timer interrupt that drives sampling.
 *
 * Provided by the platform.  Called by @ref profiler_stop() and
 * by @ref profiler_irq_handler() when a counter would overflow.
 * Must be callable from interrupt context.  Must clear any pending
 * interrupts.
 * Do not call directly.
 *
 * @post @ref profiler_irq_handler() is not called again until
 *       @ref profiler_irq_enable() is called.
 */
extern void profiler_irq_disable(void);

/** @} */

#endif // PROFILER_H
