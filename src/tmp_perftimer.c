// EMBLOCS component - performance timer
//
// add 'stop' and 'start' functions at the appropriate points in a thread
// the 'time' pin outputs the time (in clocks) between calls to 'start' and 'stop'

#include "emblocs.h"
#include "platform.h"

// instance data structure - one copy per instance in RAM
typedef struct bl_mux2_inst_s {
    bl_inst_header_t header;
    bl_u32_t *time;
	uint32_t tsc;
} bl_perftimer_inst_t;

_Static_assert((sizeof(bl_perftimer_inst_t) < 32767), "instance structure too large");

// array of pin definitions - one copy in FLASH
static bl_pin_def_t const bl_perftimer_pins[] = {
    { "time", BL_PINTYPE_UINT, BL_PINDIR_OUT, BL_OFFSET(bl_perftimer_inst_t, time)}
};

static void bl_perftimer_start_funct(bl_inst_header_t *ptr);
static void bl_perftimer_stop_funct(bl_inst_header_t *ptr);

// array of function definitions - one copy in FLASH
static bl_funct_def_t const bl_perftimer_functs[] = {
    { "start", &bl_perftimer_start_funct },
    { "start", &bl_perftimer_stop_funct }
};

// component definition - one copy in FLASH
bl_comp_def_t const bl_perftimer_def = { 
    "perftimer",
    ARRAYCOUNT(bl_perftimer_pins),
    ARRAYCOUNT(bl_perftimer_functs),
    sizeof(bl_perftimer_inst_t),
    &(bl_perftimer_pins[0]),
    &(bl_perftimer_functs[0])
};

// realtime code - one copy in FLASH
static void bl_perftimer_start_funct(bl_inst_header_t *ptr)
{
    bl_perftimer_inst_t *p = (bl_perftimer_inst_t *)ptr;

    p->tsc = tsc_read();
}

static void bl_perftimer_stop_funct(bl_inst_header_t *ptr)
{
    bl_perftimer_inst_t *p = (bl_perftimer_inst_t *)ptr;

    *(p->time) = tsc_read() - p->tsc;
}

