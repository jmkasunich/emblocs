#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "profiler.h"
#include "profiler_priv.h"

// validate configuration
#if   ( PROFILER_COUNTER_WIDTH == 1 )
typedef uint8_t  profiler_count_t;
#elif ( PROFILER_COUNTER_WIDTH == 2 )
typedef uint16_t profiler_count_t;
#elif ( PROFILER_COUNTER_WIDTH == 4 )
typedef uint32_t profiler_count_t;
#else
#error "PROFILER_COUNT_WIDTH must be 1, 2, or 4; see profiler_config.h"
#endif

#if ( (PROFILER_NUM_BINS < 8) || (PROFILER_NUM_BINS > 0xFFFFFF ) )
#error "PROFILER_NUM_BINS must be >= 8 and <= 0xFFFFFF; see profiler_config.h"
#endif

#if ( ( (PROFILER_NUM_BINS * PROFILER_COUNTER_WIDTH) & 3) != 0 )
#error "PROFILER_NUM_BINS * PROFILER_COUNTER_WIDTH must be a multiple of 4"
#endif

// define the profiler structure
typedef struct {
    histogram_t histo;
    uint8_t  shift_count;
    uint32_t packed_vals;  // bin count and shift count, packed into uint32_t
    uint32_t magic_number; // used by optimized assembly sample counter
    profiler_count_t bins[PROFILER_NUM_BINS];
} profile_t;

_Static_assert(PROFILER_STATE_FULL == HISTOGRAM_STATE_FULL,
               "profiler_priv.h: PROFILER_STATE_FULL must match HISTOGRAM_STATE_FULL");

// declare the actual structure - there is only one
profile_t profile;

// and make sure the structure offsets match the actual structure
_Static_assert(PROFILER_STATE_OFFSET         == offsetof(profile_t, histo.state),
               "profiler_priv.h: PROFILER_STATE_OFFSET does not match profile_t");
_Static_assert(PROFILER_SHIFT_COUNT_OFFSET   == offsetof(profile_t, shift_count),
               "profiler_priv.h: PROFILER_SHIFT_COUNT_OFFSET does not match profile_t");
_Static_assert(PROFILER_MAGIC_NUMBER_OFFSET  == offsetof(profile_t, magic_number),
               "profiler_priv.h: PROFILER_MAGIC_NUMBER_OFFSET does not match profile_t");
_Static_assert(PROFILER_PACKED_VALS_OFFSET   == offsetof(profile_t, packed_vals),
               "profiler_priv.h: PROFILER_PACKED_VALS_OFFSET does not match profile_t");
_Static_assert(PROFILER_ABOVE_COUNT_OFFSET   == offsetof(profile_t, histo.above_count),
               "profiler_priv.h: PROFILER_ABOVE_COUNT_OFFSET does not match profile_t");
_Static_assert(PROFILER_BELOW_COUNT_OFFSET   == offsetof(profile_t, histo.below_count),
               "profiler_priv.h: PROFILER_BELOW_COUNT_OFFSET does not match profile_t");
_Static_assert(PROFILER_BINS_OFFSET          == offsetof(profile_t, bins),
               "profiler_priv.h: PROFILER_BINS_OFFSET does not match profile_t");

// becomes 0xFF, 0xFFFF, or 0xFFFFFFFF depending on counter width
#define COUNT_MAX ((profiler_count_t)0xFFFFFFFF)


void profiler_count_sample(uint32_t pc); // silence -Wmissing-prototypes

/*
 * C sample counting function.  Used when no target-specific assembly
 * language sampler is available.  A short assembly stub grabs the PC
 * and calls this function which does the actual work of updating bins.
 *
 * Global instead of static because the stub calls it by name, but not
 * part of the public API defined in profiler.h.
 */
void profiler_count_sample(uint32_t pc)
{
    profile_t *p = &profile;
    uint32_t bin;

    if ( pc < p->histo.range_min.u32 ) {
        if ( p->histo.below_count == UINT32_MAX ) {
            profiler_irq_disable();
            p->histo.state = HISTOGRAM_STATE_FULL;
        } else {
            p->histo.below_count++;
        }
        return;
    }
    bin = (pc - p->histo.range_min.u32) >> p->shift_count;
    if ( bin >= PROFILER_NUM_BINS ) {
        if ( p->histo.above_count == UINT32_MAX ) {
            profiler_irq_disable();
            p->histo.state = HISTOGRAM_STATE_FULL;
        } else {
            p->histo.above_count++;
        }
        return;
    }
    if ( p->bins[bin] == COUNT_MAX ) {
        profiler_irq_disable();
        p->histo.state = HISTOGRAM_STATE_FULL;
    } else {
        p->bins[bin]++;
    }
}

bool profiler_init(uint32_t range_min, uint32_t bin_width)
{
    // test for between 2 and 2^30 and a power of 2
    if ( ( bin_width < 2 ) || ( bin_width > (1UL<<30)) ||
         ( ( bin_width & ( bin_width - 1 ) ) != 0 ) ) {
        return false;
    }
    // test for range_min a multiple of bin_width
    if ( (range_min % bin_width) != 0 ) {
        return false;
    }
    // stop interrupt; this is idempotent, so do it regardless of state
    profiler_irq_disable();
    // set up the generic histogram
    histogram_set_buffer(&(profile.histo), &(profile.bins),
                         sizeof(profile.bins) );
    histogram_set_counter_width(&(profile.histo), PROFILER_COUNTER_WIDTH);
    // validated above, will not fail
    histogram_set_range_u32(&(profile.histo), range_min, bin_width);
    // set up profiler specific stuff
    uint8_t shift_count = 0;
    while ( bin_width > 1 ) {
        bin_width >>= 1;
        shift_count++;
    }
    profile.shift_count = shift_count;
    // these are for optimized access by assembly language sampler ISR
    profile.packed_vals = (PROFILER_NUM_BINS << 8) | shift_count;
    profile.magic_number = (0u - ((range_min >> shift_count) + PROFILER_NUM_BINS));
    return true;
}

void profiler_reset_counts(void)
{
    profiler_irq_disable();
    histogram_reset_counts(&(profile.histo));
}

bool profiler_start(uint32_t sample_frequency)
{
    if ( ( profile.histo.state != HISTOGRAM_STATE_CAN_COUNT ) ||
         ( sample_frequency < 1 ) ) {
        return false;
    }
    return profiler_irq_enable(sample_frequency);
}

void profiler_stop(void)
{
    profiler_irq_disable();
}

bool profiler_is_full(void)
{
    return (profile.histo.state == HISTOGRAM_STATE_FULL);
}

const histogram_t *profiler_get_histogram(void)
{
    return &(profile.histo);
}
