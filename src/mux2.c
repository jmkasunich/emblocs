/*************************************************************
 * EMBLOCS component - two input multiplexor
 */

#include "emblocs_comp.h"

/* instance data structure - one copy per instance in realtime RAM */
typedef struct bl_mux2_inst_s {
    bl_pin_float_t in0;
	bl_pin_float_t in1;
	bl_pin_float_t out;
	bl_pin_bit_t sel;
} bl_mux2_inst_t;

_Static_assert((sizeof(bl_mux2_inst_t) < BL_INSTANCE_DATA_MAX_SIZE), "instance structure too large");


/* array of pin definitions - one copy in FLASH */
static bl_pin_def_t const bl_mux2_pins[] = {
    { "in0", BL_TYPE_FLOAT, BL_DIR_IN, offsetof(bl_mux2_inst_t, in0)},
    { "in1", BL_TYPE_FLOAT, BL_DIR_IN, offsetof(bl_mux2_inst_t, in1)},
    { "out", BL_TYPE_FLOAT, BL_DIR_OUT, offsetof(bl_mux2_inst_t, out)},
    { "sel", BL_TYPE_BIT, BL_DIR_IN, offsetof(bl_mux2_inst_t, sel)}
};

_Static_assert((_countof(bl_mux2_pins) < BL_PIN_COUNT_MAX), "too many pins");


static void bl_mux2_function(void *ptr, uint32_t period_ns);

// array of function definitions - one copy in FLASH
static bl_function_def_t const bl_mux2_functions[] = {
    { "update", BL_HAS_FP, &bl_mux2_function }
};

_Static_assert((_countof(bl_mux2_functions) < BL_FUNCTION_COUNT_MAX), "too many functions");


// component definition - one copy in FLASH
bl_comp_def_t const bl_mux2_def = { 
    "mux2",
    NULL,
    sizeof(bl_mux2_inst_t),
    _countof(bl_mux2_pins),
    _countof(bl_mux2_functions),
    bl_mux2_pins,
    bl_mux2_functions
};

// realtime code - one copy in FLASH
static void bl_mux2_function(void *ptr, uint32_t period_ns)
{
    (void)period_ns;  // unused in this component

    bl_mux2_inst_t *p = (bl_mux2_inst_t *)ptr;
    if ( *(p->sel) ) {
        *(p->out) = *(p->in1);
    } else {
        *(p->out) = *(p->in0);
    }
}

