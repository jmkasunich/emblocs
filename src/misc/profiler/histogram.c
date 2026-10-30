#include "histogram.h"
#include <float.h>
#include <limits.h>
#include <math.h>
#include <string.h>
#include <assert.h>

void histogram_set_buffer(histogram_t *h, void *buffer, size_t buf_len)
{
    assert(h != NULL);
    assert( buffer != NULL );
    assert( ( (uintptr_t)buffer & 3 ) == 0 );  // 32-bit aligned
    assert( ( buf_len & 3 ) == 0 );  // multiple of 4 bytes long
    h->buffer = buffer;
    h->buf_len = buf_len;
    h->state = HISTOGRAM_STATE_INIT;
}

void histogram_set_counter_width(histogram_t *h, histogram_counter_width_t width)
{
    assert(h != NULL);
    assert( ( width == HISTOGRAM_COUNT_U8 ) ||
            ( width == HISTOGRAM_COUNT_U16 )  ||
            ( width == HISTOGRAM_COUNT_U32 ) );
    h->counter_width = width;
    h->state = HISTOGRAM_STATE_INIT;
}

bool histogram_set_range_u32(histogram_t *h, uint32_t bin_base, uint32_t bin_width)
{
    assert(h != NULL);
    assert( h->buffer != NULL );
    assert( h->buf_len != 0 );
    assert( h->counter_width != 0 );
    if ( bin_width == 0 ) {
        return false;
    }
    h->num_bins = h->buf_len / h->counter_width;
    h->bin_start.u32 = bin_base;
    h->bin_width.u32 = bin_width;
    uint64_t end = (uint64_t)bin_base + (uint64_t)bin_width * h->num_bins - 1;
    if ( end > UINT32_MAX ) {
        h->bin_end.u32 = UINT32_MAX;
    } else {
        h->bin_end.u32 = (uint32_t)end;
    }
    h->val_type = HISTOGRAM_VALUE_U32;
    histogram_reset_counts(h);
    h->state = HISTOGRAM_STATE_CAN_COUNT;
    return true;
}

bool histogram_set_range_s32(histogram_t *h, int32_t bin_base, int32_t bin_width)
{
    assert(h != NULL);
    assert( h->buffer != NULL );
    assert( h->buf_len != 0 );
    assert( h->counter_width != 0 );
    if ( bin_width <= 0 ) {
        return false;
    }
    h->num_bins = h->buf_len / h->counter_width;
    h->bin_start.s32 = bin_base;
    h->bin_width.s32 = bin_width;
    int64_t end = (int64_t)bin_base + (int64_t)bin_width * h->num_bins - 1;
    if (end > INT32_MAX) {
        h->bin_end.s32 = INT32_MAX;
    } else {
        h->bin_end.s32 = (int32_t)end;
    }
    h->val_type = HISTOGRAM_VALUE_S32;
    histogram_reset_counts(h);
    h->state = HISTOGRAM_STATE_CAN_COUNT;
    return true;
}


bool histogram_set_range_f32(histogram_t *h, float bin_base, float bin_width)
{
    float reciprocal_width;

    assert(h != NULL);
    assert( h->buffer != NULL );
    assert( h->buf_len != 0 );
    assert( h->counter_width != 0 );
    if ( !(bin_width > 0.0f) ) {
        return false;
    }
    reciprocal_width = 1.0f / bin_width;
    if ( !isfinite(reciprocal_width) ) {
        return false;
    }
    h->num_bins = h->buf_len / h->counter_width;
    h->bin_start.f32 = bin_base;
    h->bin_width.f32 = bin_width;
    h->reciprocal_width = reciprocal_width;
    double end = (double)bin_base + (double)bin_width * h->num_bins;
    if (end > FLT_MAX) {
        h->bin_end.f32 = FLT_MAX;
    } else {
        h->bin_end.f32 = (float)end;
    }
    h->val_type = HISTOGRAM_VALUE_F32;
    histogram_reset_counts(h);
    h->state = HISTOGRAM_STATE_CAN_COUNT;
    return true;
}

void histogram_reset_counts(histogram_t *h)
{
    assert(h != NULL);
    assert( h->buffer != NULL );
    assert( h->buf_len != 0 );
    memset(h->buffer, 0, h->buf_len);
    h->above_count = 0;
    h->below_count = 0;
    if ( h->state == HISTOGRAM_STATE_FULL ) {
        h->state = HISTOGRAM_STATE_CAN_COUNT;
    }
}

static void increment_above_counter(histogram_t *h)
{
    if ( h->above_count  < UINT32_MAX ) {
        h->above_count++;
    } else {
        h->state = HISTOGRAM_STATE_FULL;
    }
}

static void increment_below_counter(histogram_t *h)
{
    if ( h->below_count  < UINT32_MAX ) {
        h->below_count++;
    } else {
        h->state = HISTOGRAM_STATE_FULL;
    }
}

static void increment_bin_counter(histogram_t *h, uint32_t bin_num)
{
    switch (h->counter_width) {
        case HISTOGRAM_COUNT_U8: {
            uint8_t *buf = (uint8_t *)(h->buffer);
            if ( buf[bin_num] < UINT8_MAX ) {
                buf[bin_num]++;
            } else {
                h->state = HISTOGRAM_STATE_FULL;
            }
            break;
        }
        case HISTOGRAM_COUNT_U16: {
            uint16_t *buf = (uint16_t *)(h->buffer);
            if ( buf[bin_num] < UINT16_MAX ) {
                buf[bin_num]++;
            } else {
                h->state = HISTOGRAM_STATE_FULL;
            }
            break;
        }
        case HISTOGRAM_COUNT_U32: {
            uint32_t *buf = (uint32_t *)(h->buffer);
            if ( buf[bin_num] < UINT32_MAX ) {
                buf[bin_num]++;
            } else {
                h->state = HISTOGRAM_STATE_FULL;
            }
            break;
        }
        default: {
            assert(0);
            break;
        }
    }
}

void histogram_count_value_u32(histogram_t *h, uint32_t value)
{
    uint32_t bin_num;

    assert(h != NULL);
    assert(h->val_type == HISTOGRAM_VALUE_U32);
    if ( h->state != HISTOGRAM_STATE_CAN_COUNT ) {
        return;
    }
    if ( value > h->bin_end.u32 ) {
        increment_above_counter(h);
        return;
    }
    if ( value < h->bin_start.u32 ) {
        increment_below_counter(h);
        return;
    }
    bin_num = (value - h->bin_start.u32) / h->bin_width.u32;
    increment_bin_counter(h, bin_num);
}

void histogram_count_value_s32(histogram_t *h, int32_t value)
{
    uint32_t bin_num;

    assert(h != NULL);
    assert(h->val_type == HISTOGRAM_VALUE_S32);
    if ( h->state != HISTOGRAM_STATE_CAN_COUNT ) {
        return;
    }
    if (value > h->bin_end.s32) {
        increment_above_counter(h);
        return;
    }
    if (value < h->bin_start.s32) {
        increment_below_counter(h);
        return;
    }
    bin_num = (((uint32_t)value) - ((uint32_t)h->bin_start.s32)) /
                ((uint32_t)h->bin_width.s32);
    increment_bin_counter(h, bin_num);
}

void histogram_count_value_f32(histogram_t *h, float value)
{
    uint32_t bin_num;

    assert(h != NULL);
    assert(h->val_type == HISTOGRAM_VALUE_F32);
    if ( h->state != HISTOGRAM_STATE_CAN_COUNT ) {
        return;
    }
    if ( !isfinite(value) ) {
        // don't count infinities or NaNs
        return;
    }
    if (value >= h->bin_end.f32) {
        increment_above_counter(h);
        return;
    }
    if  (value < h->bin_start.f32) {
        increment_below_counter(h);
        return;
    }
    bin_num = (value - h->bin_start.f32) * h->reciprocal_width;
    // catch any rounding errors
    if (bin_num >= h->num_bins) {
        increment_above_counter(h);
        return;
    }
    increment_bin_counter(h, bin_num);
}


static uint32_t get_bin_count(const histogram_t *h, uint32_t bin_num)
{
    switch (h->counter_width) {
        case HISTOGRAM_COUNT_U8:
            return ((uint8_t *)h->buffer)[bin_num];
        case HISTOGRAM_COUNT_U16:
            return ((uint16_t *)h->buffer)[bin_num];
        case HISTOGRAM_COUNT_U32:
            return ((uint32_t *)h->buffer)[bin_num];
        default:
            assert(0);
            return 0;
    }
}


uint32_t histogram_get_bin_count(const histogram_t *h, uint32_t bin_num)
{
    assert(h != NULL);
    assert(h->num_bins != 0);
    assert(h->buffer != NULL);
    if ( bin_num < h->num_bins ) {
        return get_bin_count(h, bin_num);
    } else {
        return 0;
    }
}


uint32_t histogram_get_total_32(const histogram_t *h)
{
    /* Track remaining capacity below UINT32_MAX. Subtracting only
        * when the term fits means nothing can wrap; once a term does
        * not fit, the sum saturates and the rest is skipped. */
    uint32_t remaining = UINT32_MAX;
    uint32_t bin_count;

    assert(h != NULL);
    assert(h->buffer != NULL);
    remaining -= h->above_count;
    if ( remaining >= h->below_count ) {
        remaining -= h->below_count;
    } else {
        remaining = 0;
    }
    for ( uint32_t n = 0 ; n < h->num_bins ; n++ ) {
        bin_count = get_bin_count(h, n);
        if ( remaining >= bin_count ) {
            remaining -= bin_count;
        } else {
            remaining = 0;
            break;
        }
    }
    return UINT32_MAX - remaining;
}


uint64_t histogram_get_total_64(const histogram_t *h)
{
    uint64_t total = h->above_count + h->below_count;

    assert(h != NULL);
    assert(h->buffer != NULL);
    for ( uint32_t n = 0 ; n < h->num_bins ; n++ ) {
        total += get_bin_count(h, n);
    }
    return total;
}
