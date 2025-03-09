// EMBLOCS component - two input summer

#include "emblocs_comp.h"

// instance data structure - one copy per instance in RAM
typedef struct bl_sum2_inst_s {
    bl_pin_float_t in0;
    bl_pin_float_t gain0;
	bl_pin_float_t in1;
    bl_pin_float_t gain1;
    bl_pin_float_t offset;
	bl_pin_float_t out;
} bl_sum2_inst_t;

_Static_assert((sizeof(bl_sum2_inst_t) < BL_INST_DATA_MAX_SIZE), "instance structure too large");


// array of pin definitions - one copy in FLASH
static bl_pin_def_t const bl_sum2_pins[] = {
    { "in0", BL_TYPE_FLOAT, BL_DIR_IN, offsetof(bl_sum2_inst_t, in0)},
    { "gain0", BL_TYPE_FLOAT, BL_DIR_IN, offsetof(bl_sum2_inst_t, gain0)},
    { "in1", BL_TYPE_FLOAT, BL_DIR_IN, offsetof(bl_sum2_inst_t, in1)},
    { "gain1", BL_TYPE_FLOAT, BL_DIR_IN, offsetof(bl_sum2_inst_t, gain1)},
    { "offset", BL_TYPE_FLOAT, BL_DIR_IN, offsetof(bl_sum2_inst_t, offset)},
    { "out", BL_TYPE_FLOAT, BL_DIR_OUT, offsetof(bl_sum2_inst_t, out)}
};

_Static_assert((_countof(bl_sum2_pins) < BL_PIN_COUNT_MAX), "too many pins");


static void bl_sum2_funct(void *ptr, uint32_t period_ns);

// array of function definitions - one copy in FLASH
static bl_funct_def_t const bl_sum2_functs[] = {
    { "update", BL_HAS_FP, &bl_sum2_funct }
};

_Static_assert((_countof(bl_sum2_functs) < BL_FUNCT_COUNT_MAX), "too many functions");


// component definition - one copy in FLASH
bl_comp_def_t const bl_sum2_def = { 
    "sum2",
    NULL,
    sizeof(bl_sum2_inst_t),
    _countof(bl_sum2_pins),
    _countof(bl_sum2_functs),
    bl_sum2_pins,
    bl_sum2_functs
};

// realtime code - one copy in FLASH
static void bl_sum2_funct(void *ptr, uint32_t period_ns)
{
    (void)period_ns;  // unused in this component

    bl_sum2_inst_t *p = (bl_sum2_inst_t *)ptr;
    *(p->out) = *(p->in0) * *(p->gain0) + *(p->in1) * *(p->gain1) + *(p->offset);
}

