/*************************************************************
 * EMBLOCS component - inverter
 */

#include "emblocs_comp.h"

/* instance data structure - one copy per instance in realtime RAM */
typedef struct bl_not_inst_s {
    bl_pin_bit_t in;
    bl_pin_bit_t out;
} bl_not_inst_t;

_Static_assert((sizeof(bl_not_inst_t) < BL_INSTANCE_DATA_MAX_SIZE), "instance structure too large");


/* array of pin definitions - one copy in FLASH */
static bl_pin_def_t const bl_not_pins[] = {
    { "in", BL_TYPE_BIT, BL_DIR_IN, offsetof(bl_not_inst_t, in)},
    { "out", BL_TYPE_BIT, BL_DIR_OUT, offsetof(bl_not_inst_t, out)}
};

_Static_assert((_countof(bl_not_pins) < BL_PIN_COUNT_MAX), "too many pins");


static void bl_not_function(void *ptr, uint32_t period_ns);

// array of function definitions - one copy in FLASH
static bl_function_def_t const bl_not_functions[] = {
    { "update", BL_NO_FP, &bl_not_function }
};

_Static_assert((_countof(bl_not_functions) < BL_FUNCTION_COUNT_MAX), "too many functions");


// component definition - one copy in FLASH
bl_comp_def_t const bl_not_def = {
    "not",
    NULL,
    sizeof(bl_not_inst_t),
    BL_NO_PERSONALITY,
    _countof(bl_not_pins),
    _countof(bl_not_functions),
    bl_not_pins,
    bl_not_functions
};

// realtime code - one copy in FLASH
static void bl_not_function(void *ptr, uint32_t period_ns)
{
    (void)period_ns;  // unused in this component

    bl_not_inst_t *p = (bl_not_inst_t *)ptr;
    if ( *(p->in) ) {
        *(p->out) = 0;
    } else {
        *(p->out) = 1;
    }
}

