#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#include "histogram.h"

bool histogram_set_buffer(histogram_t *h, void *buffer, size_t buf_len)
{
    // buffer must be 32-bit aligned and a multiple of 4 bytes long
    if ( ( buffer == NULL ) ||
         ( ( (uintptr_t)buffer & 3 ) != 0 ) ||
         ( ( buf_len & 3 ) != 0 ) ) {
        return false;
    }
    h->buffer = buffer;
    h->buf_len = buf_len;
    h->state = HISTOGRAM_STATE_INIT;
    return true;
}

bool histogram_set_count_type(histogram_t *h, histogram_counter_width_t width)
{
    if ( ( width != HISTOGRAM_COUNT_U8 ) &&
         ( width != HISTOGRAM_COUNT_U16 ) &&
         ( width != HISTOGRAM_COUNT_U32 ) ) {
        return false;
    }
    h->counter_width = width;
    h->state = HISTOGRAM_STATE_INIT;
    return true;
}

bool histogram_set_range_u32(histogram_t *h, uint32_t bin_base, uint32_t bin_width)
{
    if ( ( h->buffer == NULL ) ||
         ( h->buf_len == 0 ) ||
         ( h->counter_width == 0 ) ||
         ( bin_width == 0 ) ) {
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
    h->state = HISTOGRAM_STATE_CAN_COUNT;
    histogram_reset_counts(h);
    return true;
}

bool histogram_set_range_s32(histogram_t *h, int32_t bin_base, int32_t bin_width)
{

}

bool histogram_set_range_f32(histogram_t *h, float bin_base, float bin_width)
{

}

bool histogram_reset_counts(histogram_t *h)
{
    if ( ( h->buffer == NULL ) ||
         ( h->buf_len == 0 ) ) {
        return false;
    }
    memset(h->buffer, 0, h->buf_len);
    h->total_count = 0;
    h->above_count = 0;
    h->below_count = 0;
    if ( h->state == HISTOGRAM_STATE_FULL ) {
        h->state = HISTOGRAM_STATE_CAN_COUNT;
    }
    return true;
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
            break;
        }
    }
}

void histogram_count_value_u32(histogram_t *h, uint32_t value)
{
    uint32_t bin_num;

    if ( h->state != HISTOGRAM_STATE_CAN_COUNT ) {
        return;
    }
    if ( h->total_count  < UINT32_MAX ) {
        h->total_count++;
    } else {
        h->state = HISTOGRAM_STATE_FULL;
        return;
    }
    if ( value < h->bin_start.u32 ) {
        h->below_count++;
        return;
    }
    if ( value > h->bin_end.u32 ) {
        h->above_count++;
        return;
    }
    bin_num = (value - h->bin_start.u32) / h->bin_width.u32;
    increment_bin_counter(h, bin_num);
}

void histogram_count_value_s32(histogram_t *h, int32_t value)
{

}

void histogram_count_value_f32(histogram_t *h, float value)
{

}

