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

// these defaults give bins that cover the
// full 0x0 to 0xFFFFFFFF address range
#define DEFAULT_SHIFT_COUNT  (1u + __builtin_clz(PROFILER_NUM_BINS))
#define DEFAULT_BIN_WIDTH    (1u << DEFAULT_SHIFT_COUNT)

// declare the actual structure - there is only one
profile_t profile = {
    .base_addr = 0,
    .state=PROFILER_READY,
    .shift_count = DEFAULT_SHIFT_COUNT,
    .packed_vals = (PROFILER_NUM_BINS << 8) | (DEFAULT_SHIFT_COUNT & 0xFF),
    .magic_number = (uint32_t)(0u - PROFILER_NUM_BINS),
    .above_count = 0,
    .below_count = 0
};


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


#ifdef PROFILER_SAMPLER_C

#define COUNT_MAX ((profiler_count_t)0xFFFFFFFF)

/*
 * Sampling functions - this is called by an assembly stub
 * which extracts the PC from the stack.  This function does
 * the actual work of updating bins.
 */

__attribute__((used)) static void profiler_sample(uint32_t pc)
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

/*
 * Naked vector target. Hardware has already stacked the frame, so the
 * stacked PC is at [sp, #24]. Load it into r0 and tail-branch into the body.
 * The body returns straight to the interrupted code via the EXC_RETURN in lr.
 */

 __attribute__((naked, used)) void profiler_irq_handler(void)
{
    __asm volatile(
        "ldr r0, [sp, #24]\n\t"
        "b   profiler_sample\n\t"
        );
}

#endif // PROFILER_SAMPLER_C

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

bool profiler_is_full(void)
{
    return profile.state == PROFILER_FULL;
}

bool profiler_stop(void)
{
    if ( profile.state != PROFILER_RUNNING ) {
        return false;
    }
    profiler_irq_disable();
    profile.state = PROFILER_READY;
    return true;
}

profiler_count_t profiler_read_bin(uint32_t bin_num)
{
    if ( bin_num >= PROFILER_NUM_BINS ) {
        return 0;
    }
    return profile.bins[bin_num];
}

void profiler_read_statistics(uint32_t *above, uint32_t *below,
                              uint64_t *total)
{
    if ( above != NULL ) {
        *above = profile.above_count;
    }
    if ( below != NULL ) {
        *below = profile.below_count;
    }
    if ( total != NULL ) {
        uint64_t tmp = 0;
        for ( uint32_t n = 0 ; n < PROFILER_NUM_BINS ; n++ ) {
            tmp += profile.bins[n];
        }
        tmp += profile.above_count;
        tmp += profile.below_count;
        *total = tmp;
    }
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
