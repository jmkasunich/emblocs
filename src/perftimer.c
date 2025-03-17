// EMBLOCS component - performance timer
//
// add 'stop' and 'start' functions at the appropriate points in a thread
// the 'time' pin outputs the time (in clocks) between calls to 'start' and 'stop'

#include "emblocs_comp.h"
#include "platform.h"

// instance data structure - one copy per instance in RAM
typedef struct bl_perftimer_inst_s {
    bl_pin_u32_t time;
	uint32_t tsc;
} bl_perftimer_inst_t;

_Static_assert((sizeof(bl_perftimer_inst_t) < BL_INSTANCE_DATA_MAX_SIZE), "instance structure too large");


// array of pin definitions - one copy in FLASH
static bl_pin_def_t const bl_perftimer_pins[] = {
    { "time", BL_TYPE_U32, BL_DIR_OUT, offsetof(bl_perftimer_inst_t, time)}
};

_Static_assert((_countof(bl_perftimer_pins) < BL_PIN_COUNT_MAX), "too many pins");


static void bl_perftimer_start_function(void *ptr, uint32_t period_ns);
static void bl_perftimer_stop_function(void *ptr, uint32_t period_ns);

// array of function definitions - one copy in FLASH
static bl_function_def_t const bl_perftimer_functions[] = {
    { "start", BL_NO_FP, &bl_perftimer_start_function },
    { "stop", BL_NO_FP, &bl_perftimer_stop_function }
};

_Static_assert((_countof(bl_perftimer_functions) < BL_FUNCTION_COUNT_MAX), "too many functions");


// component definition - one copy in FLASH
bl_comp_def_t const bl_perftimer_def = { 
    "perftimer",
    NULL,
    sizeof(bl_perftimer_inst_t),
    _countof(bl_perftimer_pins),
    _countof(bl_perftimer_functions),
    bl_perftimer_pins,
    bl_perftimer_functions
};

// realtime code - one copy in FLASH
static void bl_perftimer_start_function(void *ptr, uint32_t period_ns)
{
    (void)period_ns;  // unused in this component

    bl_perftimer_inst_t *p = (bl_perftimer_inst_t *)ptr;

    p->tsc = tsc_read();
}

static void bl_perftimer_stop_function(void *ptr, uint32_t period_ns)
{
    (void)period_ns;  // unused in this component

    bl_perftimer_inst_t *p = (bl_perftimer_inst_t *)ptr;

    *(p->time) = tsc_read() - p->tsc;
}

