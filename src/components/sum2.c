// EMBLOCS component - two input summer

#include "emblocs_comp.h"

// block data structure - one copy per block in RAM
typedef struct bl_sum2_block_s {
    bl_pin_float_t in0;
    bl_pin_float_t gain0;
	bl_pin_float_t in1;
    bl_pin_float_t gain1;
    bl_pin_float_t offset;
	bl_pin_float_t out;
} bl_sum2_block_t;

_Static_assert((sizeof(bl_sum2_block_t) < BL_BLOCK_DATA_MAX_SIZE), "block structure too large");


// array of pin definitions - one copy in FLASH
static bl_pin_def_t const bl_sum2_pins[] = {
    { "in0", BL_TYPE_FLOAT, BL_DIR_IN, offsetof(bl_sum2_block_t, in0)},
    { "gain0", BL_TYPE_FLOAT, BL_DIR_IN, offsetof(bl_sum2_block_t, gain0)},
    { "in1", BL_TYPE_FLOAT, BL_DIR_IN, offsetof(bl_sum2_block_t, in1)},
    { "gain1", BL_TYPE_FLOAT, BL_DIR_IN, offsetof(bl_sum2_block_t, gain1)},
    { "offset", BL_TYPE_FLOAT, BL_DIR_IN, offsetof(bl_sum2_block_t, offset)},
    { "out", BL_TYPE_FLOAT, BL_DIR_OUT, offsetof(bl_sum2_block_t, out)}
};

_Static_assert((_countof(bl_sum2_pins) < BL_PIN_COUNT_MAX), "too many pins");


static void bl_sum2_function(void *ptr, uint32_t period_ns);

// array of function definitions - one copy in FLASH
static bl_function_def_t const bl_sum2_functions[] = {
    { "update", BL_HAS_FP, &bl_sum2_function }
};

_Static_assert((_countof(bl_sum2_functions) < BL_FUNCTION_COUNT_MAX), "too many functions");


// component definition - one copy in FLASH
bl_comp_def_t const bl_sum2_def = { 
    "sum2",
    NULL,
    sizeof(bl_sum2_block_t),
    BL_NO_PERSONALITY,
    _countof(bl_sum2_pins),
    _countof(bl_sum2_functions),
    bl_sum2_pins,
    bl_sum2_functions
};

// realtime code - one copy in FLASH
static void bl_sum2_function(void *ptr, uint32_t period_ns)
{
    (void)period_ns;  // unused in this component

    bl_sum2_block_t *p = (bl_sum2_block_t *)ptr;
    *(p->out) = *(p->in0) * *(p->gain0) + *(p->in1) * *(p->gain1) + *(p->offset);
}

