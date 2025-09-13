// EMBLOCS component - position& velocity limiter

#include "emblocs_comp.h"

// instance data structure - one copy per instance in RAM
typedef struct bl_limit2_inst_s {
    bl_pin_float_t in;
    bl_pin_float_t max;
	bl_pin_float_t min;
	bl_pin_float_t max_v;
	bl_pin_float_t out;
} bl_limit2_inst_t;

_Static_assert((sizeof(bl_limit2_inst_t) < BL_INSTANCE_DATA_MAX_SIZE), "instance structure too large");


// array of pin definitions - one copy in FLASH
static bl_pin_def_t const bl_limit2_pins[] = {
    { "in", BL_TYPE_FLOAT, BL_DIR_IN, offsetof(bl_limit2_inst_t, in)},
    { "max", BL_TYPE_FLOAT, BL_DIR_IN, offsetof(bl_limit2_inst_t, max)},
    { "min", BL_TYPE_FLOAT, BL_DIR_IN, offsetof(bl_limit2_inst_t, min)},
    { "max_v", BL_TYPE_FLOAT, BL_DIR_IN, offsetof(bl_limit2_inst_t, max_v)},
    { "out", BL_TYPE_FLOAT, BL_DIR_OUT, offsetof(bl_limit2_inst_t, out)}
};

_Static_assert((_countof(bl_limit2_pins) < BL_PIN_COUNT_MAX), "too many pins");


static void bl_limit2_function(void *ptr, uint32_t period_ns);

// array of function definitions - one copy in FLASH
static bl_function_def_t const bl_limit2_functions[] = {
    { "update", BL_HAS_FP, &bl_limit2_function }
};

_Static_assert((_countof(bl_limit2_functions) < BL_FUNCTION_COUNT_MAX), "too many functions");


// component definition - one copy in FLASH
bl_comp_def_t const bl_limit2_def = { 
    "limit2",
    NULL,
    sizeof(bl_limit2_inst_t),
    BL_NO_PERSONALITY,
    _countof(bl_limit2_pins),
    _countof(bl_limit2_functions),
    bl_limit2_pins,
    bl_limit2_functions
};

// realtime code - one copy in FLASH
static void bl_limit2_function(void *ptr, uint32_t period_ns)
{
    (void)period_ns;  // unused in this component
    float tmp_in, tmp_lim, prev_out, max_step;

    bl_limit2_inst_t *p = (bl_limit2_inst_t *)ptr;
    tmp_in = *(p->in);
    if ( tmp_in > (tmp_lim = *(p->max)) ) {
        tmp_in = tmp_lim;
    } else if ( tmp_in < (tmp_lim = *(p->min)) ) {
        tmp_in = tmp_lim;
    }
    if ( *(p->max_v ) < 0.0f ) {
        *(p->max_v) = -*(p->max_v);
    }
    max_step = *(p->max_v) * (float)period_ns * 0.000000001f;
    prev_out = *(p->out);
    if ( tmp_in > (prev_out + max_step) ) {
        *(p->out) = prev_out + max_step;
    } else if ( tmp_in < (prev_out - max_step) ) {
        *(p->out) = prev_out - max_step;
    } else {
        *(p->out) = tmp_in;
    }
}

