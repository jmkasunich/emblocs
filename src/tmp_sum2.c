// EMBLOCS component - two input summer

#include "emblocs.h"

// instance data structure - one copy per instance in RAM
typedef struct bl_sum2_inst_s {
    bl_pin_float_t in0;
    bl_pin_float_t gain0;
	bl_pin_float_t in1;
    bl_pin_float_t gain1;
    bl_pin_float_t offset;
	bl_pin_float_t out;
} bl_sum2_inst_t;

_Static_assert((sizeof(bl_sum2_inst_t) < 32767), "instance structure too large");

// array of pin definitions - one copy in FLASH
static bl_pin_def_t const bl_sum2_pins[] = {
    { "in0", BL_TYPE_FLOAT, BL_DIR_IN, offsetof(bl_sum2_inst_t, in0)},
    { "gain0", BL_TYPE_FLOAT, BL_DIR_IN, offsetof(bl_sum2_inst_t, gain0)},
    { "in1", BL_TYPE_FLOAT, BL_DIR_IN, offsetof(bl_sum2_inst_t, in1)},
    { "gain1", BL_TYPE_FLOAT, BL_DIR_IN, offsetof(bl_sum2_inst_t, gain1)},
    { "offset", BL_TYPE_FLOAT, BL_DIR_IN, offsetof(bl_sum2_inst_t, offset)},
    { "out", BL_TYPE_FLOAT, BL_DIR_OUT, offsetof(bl_sum2_inst_t, out)}
};

static void bl_sum2_funct(void *ptr);

/*
// array of function definitions - one copy in FLASH
static bl_funct_def_t const bl_sum2_functs[] = {
    { "funct", &bl_sum2_funct }
};
*/

// component definition - one copy in FLASH
bl_comp_def_t const bl_sum2_def = { 
    "sum2",
    NULL,
    sizeof(bl_sum2_inst_t),
    _countof(bl_sum2_pins),
//    ARRAYCOUNT(bl_sum2_functs),
    &(bl_sum2_pins[0])
//    &(bl_sum2_functs[0])
};

// realtime code - one copy in FLASH
static void bl_sum2_funct(void *ptr)
{
    bl_sum2_inst_t *p = (bl_sum2_inst_t *)ptr;
    *(p->out) = *(p->in0) * *(p->gain0) + *(p->in1) * *(p->gain1) + *(p->offset);
}

