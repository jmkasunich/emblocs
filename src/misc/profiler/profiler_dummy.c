// profiler_dummy.c - provides stubs for test build/link
#include <stdint.h>
#include <stdbool.h>

bool profiler_irq_enable(uint32_t sample_frequency)
{
    (void)sample_frequency;
    return true;
}

void profiler_irq_disable(void)
{
}
