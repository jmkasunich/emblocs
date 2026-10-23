#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "profiler.h"
#include "profiler_priv.h"

typedef struct {
    uint32_t base_addr;
    uint8_t  shift_count;
    uint8_t  state;
    uint32_t total_samples;
    profiler_count_t bins[PROFILER_NUM_BINS];
} profile_t;

// declare the actual structure - there is only one
volatile profile_t profile = { .state=PROFILER_RESET };


// and make sure the structure offsets match the actual structure
_Static_assert(PROFILER_BASE_ADDR_OFFSET     == offsetof(profile_t, base_addr),
               "profiler_priv.h: PROFILER_BASE_ADDR_OFFSET does not match profile_t");
_Static_assert(PROFILER_SHIFT_COUNT_OFFSET   == offsetof(profile_t, shift_count),
               "profiler_priv.h: PROFILER_SHIFT_COUNT_OFFSET does not match profile_t");
_Static_assert(PROFILER_STATE_OFFSET         == offsetof(profile_t, state),
               "profiler_priv.h: PROFILER_STATE_OFFSET does not match profile_t");
_Static_assert(PROFILER_TOTAL_SAMPLES_OFFSET == offsetof(profile_t, total_samples),
               "profiler_priv.h: PROFILER_TOTAL_SAMPLES_OFFSET does not match profile_t");
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
    volatile profile_t *p = &profile;

    p->total_samples++;
    pc = (pc - p->base_addr) >> p->shift_count;
    if (pc >= PROFILER_NUM_BINS) return;

    if ( ++p->bins[pc] == COUNT_MAX ) {
        profiler_irq_disable();
        profile.state = PROFILER_FULL;
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

bool profiler_setup(uint32_t base_address, uint32_t bin_width)
{
    // test for between 2 and 2^24 and a power of 2
    if ( ( bin_width < 2 ) || ( bin_width > (1UL<<24)) ||
         ( ( bin_width & ( bin_width - 1 ) ) != 0 ) ) {
        return false;
    }
    if ( base_address & 0x01 ) {
        return false;
    }
    if ( profile.state == PROFILER_RUNNING ) {
        profiler_stop();
    }
    profile.base_addr = base_address;
    profile.shift_count = 0;
    while ( bin_width > 1 ) {
        bin_width >>= 1;
        profile.shift_count++;
    }
    profile.total_samples = 0;
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

profiler_count_t *profiler_read(void)
{
    if ( profile.state == PROFILER_RESET ) {
        return NULL;
    }
    if ( profile.state == PROFILER_RUNNING ) {
        profiler_irq_disable();
    }
    if ( profile.state != PROFILER_READOUT ) {
        // do any required translation here
        profile.state = PROFILER_READOUT;
    }
    // IRQ is stopped, can (and must) discard volatile
    return (profiler_count_t *)profile.bins;
}

profiler_count_t profiler_read_bin(uint32_t bin_num)
{
    profiler_count_t count;

    if ( ( profile.state == PROFILER_RESET ) ||
         ( bin_num >= PROFILER_NUM_BINS ) ) {
        return 0;
    }
    count = profile.bins[bin_num];
    if ( profile.state != PROFILER_READOUT ) {
        // do any required translation here
    }
    return count;
}

uint32_t profiler_read_total(void)
{
    if ( profile.state == PROFILER_RESET ) {
        return 0;
    }
    return profile.total_samples;
}

