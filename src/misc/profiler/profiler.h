/**
 * @file profiler.h
 * @brief API for sample-based profiling.
 *
 * A profiler that samples the program counter and builds a
 * histogram of the sampled values, to visualize where an MCU
 * is spending most of its time.  The result is a generic
 * histogram as defined in histogram.h, so any tool that reads
 * a histogram can read the profile.
 * 
 * Differences from a generic histogram:
 * - Bin count and counter width are fixed at compile time.
 * - All memory and structures are statically allocated.
 * - Bin width is restricted to a power of 2.
 * - Base address must be a multiple of bin width.
 *
 * @section profiler_usage Profiler Usage
 *
 * Step 1) Call @ref profiler_init to configure the bins and clear
 *    all counts.  Go to step 2.
 *
 * Step 2) Call @ref profiler_start to begin sampling.  Go to step 3.
 *
 * Step 3) Call @ref profiler_stop to stop sampling.  Go to step 4.
 *
 * Step 4) Do any of the following:
 *
 *    - Call @ref profiler_start to resume sampling.  (Only if
 *      @ref profiler_is_full returns false.)  Go to step 3.
 *    - Call @ref profiler_is_full to check whether the run ended
 *      early because a counter saturated.  Remain at step 4.
 *    - Read the data using the histogram_t pointer returned by
 *      @ref profiler_get_histogram.  Remain at step 4.
 *    - Call @ref profiler_reset_counts to clear counts; base
 *      address and bin width are unchanged.  Go to step 2.
 *    - Call @ref profiler_init to clear counts and change
 *      base address and/or bin width.  Go to step 2.
 *
 * @ref profiler_is_full can be called even while the profiler is
 * sampling; if it returns true, sampling has stopped automatically,
 * so you are at step 4.
 *
 * @ref profiler_init and @ref profiler_reset_counts can also be
 * called while the profiler is sampling; they will stop sampling
 * and discard all sampled data, leaving you at step 2.
 *
 * @section profiler_config Compile-Time Configuration
 *
 * Config is set by #define's in profiler_config.h; users should
 * put a copy of this file somewhere in their project include
 * path and edit as needed.  There are two configuration items:
 *
 * - @c PROFILER_NUM_BINS - the number of bins in the histogram.
 *      From 8 to 16,777,215 (0xFFFFFF).
 * - @c PROFILER_COUNTER_WIDTH - the width of each bin counter,
 *      in bytes.  Must be 1, 2, or 4; determines how soon the
 *      bins become full.
 *
 * RAM used by the histogram is approximately
 * PROFILER_COUNTER_WIDTH * PROFILER_NUM_BINS + some fixed overhead.
 *
 * @section profiler_threading  Multi-Core and Thread Safety
 *
 * The profiler is intended to profile code running on a single core.
 * The API is not reentrant and is not safe for use from more than one
 * core.  Call all functions from a single thread of control, not an
 * interrupt handler.  The only asynchronous activity is the sampling
 * interrupt, which must be serviced by the same core that calls the
 * API.
 */

#ifndef PROFILER_H
#define PROFILER_H

#include <stdint.h>
#include <stdbool.h>
#include <histogram.h>
#include <profiler_config.h>

/**
 * @brief Prepares the profiler to sample the program counter and
 *        build a histogram.
 *
 * The histogram has @c PROFILER_NUM_BINS bins.  Each bin covers
 * @p bin_width bytes of address space, starting at @p range_min.
 * Each bin counts the samples that fall inside its address range.
 *
 * @param[in] range_min  Start of the histogram address range.
 *                       Must be a multiple of @p bin_width.
 * @param[in] bin_width  Bytes covered by each bin.  Must be a
 *                       power of 2, from 2 to 2^30 inclusive.
 *
 * @p range_min and @p bin_width are validated first; invalid
 * values return false and change nothing.  Otherwise, if the
 * profiler is sampling, it is stopped.  Then it is reconfigured
 * with the new parameters, all counters are cleared, and it
 * returns true.
 */
bool profiler_init(uint32_t range_min, uint32_t bin_width);

/**
 * @brief Resets the profiler counters without changing bin width
 *        or base address.
 *
 * If the profiler is running, it is stopped first.
 *
 * @pre @ref profiler_init has been called successfully at
 *      least once, so there are counters to clear.
 */
void profiler_reset_counts(void);

/**
 * @brief Starts sampling the program counter.
 *
 * Samples the program counter @p sample_frequency times per second.
 * Each sample inside a histogram bin's address range increments that
 * bin's counter.  Samples outside the bin range are counted as "above"
 * or "below".
 *
 * Sampling continues until @ref profiler_stop() is called, or until
 * a sample would overflow any bin or above/below counter.  That sample
 * is discarded, and @ref profiler_is_full() reports the condition.
 * Once full, sampling stops and cannot be restarted until
 * @ref profiler_reset or @ref profiler_init is called to reset
 * the counters.
 *
 * If sampling is already running, will attempt to change to the
 * specified frequency.  Whether sampling stops during the change
 * is implementation dependent.
 *
 * @param[in] sample_frequency  Samples per second.  Must be nonzero and
 *                              supported by the system.
 *
 * @pre @ref profiler_init has been called successfully at
 *      least once, so the number and size of bins are known.
 *
 * @return true if sampling at the requested frequency, false if
 *         not sampling.  Can fail because @p sample_frequency is
 *         zero or unsupported by the system, or if the profiler
 *         is full.
 */
bool profiler_start(uint32_t sample_frequency);

/**
 * @brief Stops sampling the program counter.
 *
 * Histogram and above/below counters hold their values.
 *
 * If already stopped, does nothing.
 *
 */
void profiler_stop(void);

/**
 * @brief Reports whether the profiler has filled up.
 *
 * Returns true if sampling has stopped automatically because
 * @c above_count, @c below_count, or a bin would have overflowed.
 *
 * @return true if the profiler is full, false otherwise.
 */
bool profiler_is_full(void);

/**
 * @brief Returns a pointer to the profile histogram.
 *
 * Returns a pointer to a histogram_t object.  The object contains
 * the bin counts as well as @c above_count, @c below_count, and
 * the histogram configuration.  The API defined by histogram.h
 * can be used to read (but not modify) the data.  Any modifications
 * to the histogram object must be made through the profiler API,
 * not the histogram API.
 *
 * The histogram object is modified by an interrupt handler while
 * sampling; access it only after sampling has stopped.
 */
const histogram_t *profiler_get_histogram(void);



/**
 * @defgroup platform_hooks Platform Interface
 * @brief Interface between the profiler and the platform.
 *
 * The platform must place @ref profiler_irq_handler() in
 * the interrupt vector table and provide platform-specific
 * implementations of @ref profiler_irq_enable() and
 * @ref profiler_irq_disable().
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
 * discarded and sampling is stopped.
 *
 * Must be placed in the interrupt vector table.  Do not call directly.
 */
void profiler_irq_handler(void);

/**
 * @brief Enables the platform timer interrupt that drives sampling.
 *
 * Provided by the platform.  Called by @ref profiler_start().
 * Must arrange for profiler_irq_handler() to be called from a timer
 * interrupt at @p sample_frequency samples per second.  Any pending
 * interrupt from this timer must be cleared before the interrupt is
 * enabled, so that a stale sample is not captured.
 *
 * Must be safe to call even if the interrupt and timer are already
 * enabled.  In that case, if the requested frequency is the same,
 * it should do nothing and return true.  If the requested frequency
 * has changed, it should either change to the new frequency and
 * return true (if possible), or turn off the interrupt and return
 * false.  Temporarily turning off the interrupt during a frequency
 * change is allowed but not required.
 *
 * Do not call directly.
 *
 * @param[in] sample_frequency  Samples per second.  Will be nonzero
 *                              when called by the profiler.
 *
 * @return true if @ref profiler_irq_handler is being called at
 *         @p sample_frequency.  false if the platform cannot operate
 *         at that frequency, in which case @ref profiler_irq_handler
 *         must be disabled.
 */
extern bool profiler_irq_enable(uint32_t sample_frequency);

/**
 * @brief Disables the platform timer interrupt that drives sampling.
 *
 * Provided by the platform.  Called by @ref profiler_stop() and
 * by @ref profiler_irq_handler() when a counter would overflow.
 * Must be callable from interrupt context.  Must clear any pending
 * interrupts.  Must be safe to call even if the interrupt is
 * already disabled.
 *
 * Do not call directly.
 */
extern void profiler_irq_disable(void);

/** @} */

#endif // PROFILER_H
