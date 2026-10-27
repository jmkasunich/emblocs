#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "profiler.h"
#include "profiler_priv.h"

typedef struct {
    uint32_t base_addr;  // first bin starts here
    volatile uint8_t  state;
    uint8_t  shift_count;
    uint32_t packed_vals;  // bin count and shift count, packed into uint32_t
    uint32_t magic_number; // used by optimized assembly sample counter
    uint32_t above_count;
    uint32_t below_count;
    profiler_count_t bins[PROFILER_NUM_BINS];
} profile_t;

_Static_assert(PROFILER_RESET == 0,
               "profiler_priv.h: PROFILER_RESET must be zero so struct lives in .bss");

// declare the actual structure - there is only one
profile_t profile = {.state=PROFILER_RESET};

// and make sure the structure offsets match the actual structure
_Static_assert(PROFILER_STATE_OFFSET         == offsetof(profile_t, state),
               "profiler_priv.h: PROFILER_STATE_OFFSET does not match profile_t");
_Static_assert(PROFILER_SHIFT_COUNT_OFFSET   == offsetof(profile_t, shift_count),
               "profiler_priv.h: PROFILER_SHIFT_COUNT_OFFSET does not match profile_t");
_Static_assert(PROFILER_MAGIC_NUMBER_OFFSET  == offsetof(profile_t, magic_number),
               "profiler_priv.h: PROFILER_MAGIC_NUMBER_OFFSET does not match profile_t");
_Static_assert(PROFILER_PACKED_VALS_OFFSET   == offsetof(profile_t, packed_vals),
               "profiler_priv.h: PROFILER_PACKED_VALS_OFFSET does not match profile_t");
_Static_assert(PROFILER_ABOVE_COUNT_OFFSET   == offsetof(profile_t, above_count),
               "profiler_priv.h: PROFILER_ABOVE_COUNT_OFFSET does not match profile_t");
_Static_assert(PROFILER_BELOW_COUNT_OFFSET   == offsetof(profile_t, below_count),
               "profiler_priv.h: PROFILER_BELOW_COUNT_OFFSET does not match profile_t");
_Static_assert(PROFILER_BINS_OFFSET          == offsetof(profile_t, bins),
               "profiler_priv.h: PROFILER_BINS_OFFSET does not match profile_t");


#define COUNT_MAX ((profiler_count_t)0xFFFFFFFF)

/*
 * C sample binning function
 * This implementation is used when no target-specific all-assembly
 * sampler is avaiable.  A short assembly stub grabs the PC and
 * calls this function which does the actual work of updating bins.
 */

void profiler_bin_sample(uint32_t pc)
{
    profile_t *p = &profile;
    uint32_t bin;

    if ( pc < p->base_addr ) {
        if ( p->below_count == UINT32_MAX ) {
            profiler_irq_disable();
            p->state = PROFILER_FULL;
        } else {
            p->below_count++;
        }
        return;
    }
    bin = (pc - p->base_addr) >> p->shift_count;
    if ( bin >= PROFILER_NUM_BINS ) {
        if ( p->above_count == UINT32_MAX ) {
            profiler_irq_disable();
            p->state = PROFILER_FULL;
        } else {
            p->above_count++;
        }
        return;
    }
    if ( p->bins[bin] == COUNT_MAX ) {
        profiler_irq_disable();
        p->state = PROFILER_FULL;
    } else {
        p->bins[bin]++;
    }
}

bool profiler_setup(uint32_t base_addr, uint32_t bin_width)
{
    // test for between 2 and 2^30 and a power of 2
    if ( ( bin_width < 2 ) || ( bin_width > (1UL<<30)) ||
         ( ( bin_width & ( bin_width - 1 ) ) != 0 ) ) {
        return false;
    }
    // test for base_addr a multiple of bin_width
    if ( (base_addr % bin_width) != 0 ) {
        return false;
    }
    if ( profile.state == PROFILER_RUNNING ) {
        profiler_stop();
    }
    profile.base_addr = base_addr;
    uint8_t shift_count = 0;
    while ( bin_width > 1 ) {
        bin_width >>= 1;
        shift_count++;
    }
    profile.shift_count = shift_count;
    // these are for optimized access by assembly language sampler ISR
    profile.packed_vals = (PROFILER_NUM_BINS << 8) | shift_count;
    profile.magic_number = (0u - ((base_addr >> shift_count) + PROFILER_NUM_BINS));
    // reset statistics
    profile.above_count = 0;
    profile.below_count = 0;
    for ( uint32_t n = 0 ; n < PROFILER_NUM_BINS ; n++ ) {
        profile.bins[n] = 0;
    }
    profile.state = PROFILER_READY;
    return true;
}

bool profiler_start(uint32_t sample_frequency)
{
    if ( ( profile.state != PROFILER_READY ) ||
         ( sample_frequency < 1 ) ) {
        return false;
    }
    profile.state = PROFILER_RUNNING;
    if ( ! profiler_irq_enable(sample_frequency) ) {
        profile.state = PROFILER_READY;
        return false;
    }
    return true;
}

bool profiler_stop(void)
{
    if ( profile.state != PROFILER_RUNNING ) {
        return false;
    }
    profiler_irq_disable();
    if ( profile.state != PROFILER_FULL ) {
        profile.state = PROFILER_READY;
    }
    return true;
}

bool profiler_is_stopped(void)
{
    return ( (profile.state == PROFILER_READY) ||
             (profile.state == PROFILER_FULL) );
}

bool profiler_is_running(void)
{
    return (profile.state == PROFILER_RUNNING);
}

bool profiler_is_full(void)
{
    return (profile.state == PROFILER_FULL);
}

void profiler_read_info(uint32_t *base_addr, uint32_t *bin_width,
                        uint32_t *num_bins, const profiler_count_t **data_addr)
{
    if ( base_addr != NULL ) {
        *base_addr = profile.base_addr;
    }
    if ( bin_width != NULL ) {
        *bin_width = 1u << profile.shift_count;
    }
    if ( num_bins != NULL ) {
        *num_bins = PROFILER_NUM_BINS;
    }
    if ( data_addr != NULL ) {
        *data_addr = profile.bins;
    }
}

void profiler_read_statistics(uint32_t *above, uint32_t *below,
                              uint32_t *total)
{
    if ( above != NULL ) {
        *above = profile.above_count;
    }
    if ( below != NULL ) {
        *below = profile.below_count;
    }
    if ( total != NULL ) {
        /* Track remaining capacity below UINT32_MAX. Subtracting only
         * when the term fits means nothing can wrap; once a term does
         * not fit, the sum saturates and the rest is skipped. */
        uint32_t remaining = UINT32_MAX;
        remaining -= profile.above_count;
        if ( remaining >= profile.below_count ) {
            remaining -= profile.below_count;
        } else {
            remaining = 0;
        }
        for ( uint32_t n = 0 ; n < PROFILER_NUM_BINS ; n++ ) {
            if ( remaining >= profile.bins[n] ) {
                remaining -= profile.bins[n];
            } else {
                remaining = 0;
                break;
            }
        }
        *total = UINT32_MAX - remaining;
    }
}

uint64_t profiler_read_total(void)
{
    uint64_t total = 0;

    total += profile.above_count;
    total += profile.below_count;
    for ( uint32_t n = 0 ; n < PROFILER_NUM_BINS ; n++ ) {
        total += profile.bins[n];
    }
    return total;
}

profiler_count_t profiler_read_bin(uint32_t bin_num)
{
    if ( bin_num >= PROFILER_NUM_BINS ) {
        return 0;
    }
    return profile.bins[bin_num];
}

