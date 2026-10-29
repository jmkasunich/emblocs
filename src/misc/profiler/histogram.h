/**
 * @file histogram.h
 * @brief API for histogram data collection.
 * 
 * This API is non-reentrant; a histogram object should only be
 * accessed from a single thread.
 */

#ifndef HISTOGRAM_H
#define HISTOGRAM_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

/** @brief Union used for bin boundaries, etc. */
typedef union {
    uint32_t u32;
    int32_t  s32;
    float    f32;
} histogram_value_t;

/** @brief Type of values binned and counted in the histogram. */
typedef enum __attribute__((__packed__)) {
    HISTOGRAM_VALUE_U32 = 0,
    HISTOGRAM_VALUE_S32 = 1,
    HISTOGRAM_VALUE_F32 = 2
} histogram_value_type_t;

/** @brief  Counter Width.
 *
 * Bin counters can be 1, 2, or 4 bytes wide; this allows
 * balancing maximum count, number of bins, and RAM usage.
*/
typedef enum __attribute__((__packed__)) {
    HISTOGRAM_COUNT_U8 = 1,     /**< max bin count 255 */
    HISTOGRAM_COUNT_U16 = 2,    /**< max bin count 65,535 */
    HISTOGRAM_COUNT_U32 = 4     /**< max bin count 4,294,967,295 */
} histogram_counter_width_t;

/** @brief Current histogram state. */
typedef enum __attribute__((__packed__)) {
    HISTOGRAM_STATE_INIT = 0,       /**< not ready to count samples */
    HISTOGRAM_STATE_CAN_COUNT = 1,  /**< configured and ready to count */
    HISTOGRAM_STATE_FULL = 2        /**< counting stopped to avoid overflow */
} histogram_state_t;


/**
 * @brief Histogram data structure.
 *
 * Callers are responsible for allocating this structure, can be
 * static or malloc.  Should be zeroed before first API call.
 *
 * All structure fields should be considered read-only.
 * Use API functions to configure/change the structure.
 *
 * For u32 and s32, @c bin_end is the last value inside the last
 * bin.  For float, it is the first value outside the last bin.
 */
typedef struct {
    histogram_value_type_t val_type;         /**< type of values we are counting */
    histogram_counter_width_t counter_width; /**< width of counters: 1, 2, or 4 bytes */
    histogram_state_t state;                 /**< current state */
    histogram_value_t bin_start;             /**< first bin starts here */
    histogram_value_t bin_end;               /**< last bin ends here */
    histogram_value_t bin_width;             /**< width of each bin */
    uint32_t num_bins;                       /**< number of bins in buffer */
    float reciprocal_width;                  /**< speedup for f32 */
    uint32_t total_count;                    /**< total number of values counted */
    uint32_t above_count;                    /**< number of values above bin range */
    uint32_t below_count;                    /**< number of values below bin range */
    void *buffer;                            /**< memory for bin counters */
    size_t buf_len;                          /**< buffer size in bytes (not bins) */
} histogram_t;


/** @brief Assigns memory for counters.
 *
 * Tells the histogram to use @p buf_len bytes located at
 * @p buf for the bin counters.
 *
 * Caller is responsible for allocating the buffer, which can
 * be static or malloc.
 *
 * @pre @p buf must be word-aligned.
 * @pre @p buf_len must be a multiple of four.
 *
 */
void histogram_set_buffer(histogram_t *h, void *buf, size_t buf_len);


/** @brief Determines maximum bin count.
 *
 * Tells the histogram to use 1-, 2-, or 4-byte wide counters.
 * For a given buffer, smaller counters will allow more bins but
 * will fill up faster.
 *
 * @pre @p width must be a valid @ref histogram_counter_width_t.
 *
 */
void histogram_set_counter_width(histogram_t *h, histogram_counter_width_t width);


/** @defgroup histogram_config Histogram Configuration
 *
 * These functions configure the mapping between histogram bins
 * and actual values.  The first bin starts at @p bin_base, the
 * second bin starts at @p bin_base + @p bin_width, and so on.
 *
 * @p bin_width must be positive and non-zero.
 *
 * If successful, calls @ref histogram_reset_counts before returning.
 *
 * @pre @ref histogram_set_buffer and @ref histogram_set_counter_width
 *   have been called successfully at least once, so @c num_bins
 *   can be calculated.
 *
 * All return @c true on success, @c false if @p bin_width is invalid.
 * @{
 */
bool histogram_set_range_u32(histogram_t *h, uint32_t bin_base, uint32_t bin_width);
bool histogram_set_range_s32(histogram_t *h, int32_t bin_base, int32_t bin_width);
bool histogram_set_range_f32(histogram_t *h, float bin_base, float bin_width);
/** @} */


/** @brief Zeros all bins and counters
 *
 * Clears @c total_count, @c above_count, @c below_count, all bin
 * counters and the FULL state.  Does not change configuration.
 *
 * @pre @ref histogram_set_buffer has been called successfully at
 *           least once, so there are counters to clear.
 */
void histogram_reset_counts(histogram_t *h);


/** @defgroup histogram_count Histogram Counting
 *
 * These functions determine if @p value falls above, below, or
 * inside the bin range established by @ref histogram_config
 * and increment the relevant counter.  @c total_count is
 * incremented regardless of value.
 *
 * If @c total_count, @c above_count, @c below_count, or any bin
 * counter would overflow, state becomes HISTOGRAM_STATE_FULL
 * and subsequent calls return immediately.
 *
 * Floating point histograms do not count NaN or +/-infinity
 * but still increment @c total_count.  A mismatch between
 * @c total_count and the sum of @c above_count, @c below_count
 * and the sum of all bins can be used to detect "bad" values.
 * @{
 */
void histogram_count_value_u32(histogram_t *h, uint32_t value);
void histogram_count_value_s32(histogram_t *h, int32_t value);
void histogram_count_value_f32(histogram_t *h, float value);
/** @} */


#endif // HISTOGRAM_H
