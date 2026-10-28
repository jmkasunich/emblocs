/**
 * @file histogram.h
 * @brief API for histogram data collection.
 * 
 * @section histogram_threading  Multi-Core and Thread Safety
 *
 * This API is non-reentrant; a histogram object should only be accessed
 * from a single thread.
 */

#ifndef HISTOGRAM_H
#define HISTOGRAM_H

#include <stdint.h>
#include <stdbool.h>

typedef union {
    uint32_t u32;
    int32_t  s32;
    float    f32;
} histogram_value_t;

typedef enum __attribute__((__packed__)) {
    HISTOGRAM_VALUE_U32 = 0,
    HISTOGRAM_VALUE_S32 = 1,
    HISTOGRAM_VALUE_F32 = 2
} histogram_value_type_t;

typedef enum __attribute__((__packed__)) {
    HISTOGRAM_COUNT_UNKNOWN = 0,
    HISTOGRAM_COUNT_U8 = 1,
    HISTOGRAM_COUNT_U16 = 2,
    HISTOGRAM_COUNT_U32 = 4
} histogram_counter_width_t;

typedef enum __attribute__((__packed__)) {
    HISTOGRAM_STATE_INIT = 0,
    HISTOGRAM_STATE_CAN_COUNT = 1,
    HISTOGRAM_STATE_FULL = 2
} histogram_state_t;


typedef struct {
    histogram_value_t bin_start;             // first bin starts here
    histogram_value_t bin_end;               // last bin ends here
    histogram_value_t bin_width;             // width of each bin
    histogram_value_type_t val_type;         // type of values we are counting
    histogram_counter_width_t counter_width; // width of counters
    histogram_state_t state;                 // current state
    uint32_t num_bins;                       // number of bins in buffer
    uint32_t total_count;                    // number of values counted
    uint32_t above_count;                    // number of values above bin range
    uint32_t below_count;                    // number of values below bin range
    void *buffer;                            // buffer for bins
    size_t buf_len;                          // buffer size in bytes (not bins)
} histogram_t;


bool histogram_set_buffer(histogram_t *h, void *buf, size_t buf_size);

bool histogram_set_counter_width(histogram_t *h, histogram_counter_width_t width);

bool histogram_set_range_u32(histogram_t *h, uint32_t bin_base, uint32_t bin_width);
bool histogram_set_range_s32(histogram_t *h, int32_t bin_base, int32_t bin_width);
bool histogram_set_range_f32(histogram_t *h, float bin_base, float bin_width);

bool histogram_reset_counts(histogram_t *h);

void histogram_count_value_u32(histogram_t *h, uint32_t value);
void histogram_count_value_s32(histogram_t *h, int32_t value);
void histogram_count_value_f32(histogram_t *h, float value);

#endif // HISTOGRAM_H
