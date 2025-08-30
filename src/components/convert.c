/*************************************************************
 * EMBLOCS component - signal type converters
 */

#include "emblocs_comp.h"

/* instance data structure - one copy per instance in realtime RAM */
typedef struct bl_conv_s2u_inst_s {
    bl_pin_s32_t in;
	bl_pin_u32_t out;
} bl_conv_s2u_inst_t;

_Static_assert((sizeof(bl_conv_s2u_inst_t) < BL_INSTANCE_DATA_MAX_SIZE), "instance structure too large");


/* array of pin definitions - one copy in FLASH */
static bl_pin_def_t const bl_conv_s2u_pins[] = {
    { "in", BL_TYPE_S32, BL_DIR_IN, offsetof(bl_conv_s2u_inst_t, in)},
    { "out", BL_TYPE_U32, BL_DIR_OUT, offsetof(bl_conv_s2u_inst_t, out)}
};

_Static_assert((_countof(bl_conv_s2u_pins) < BL_PIN_COUNT_MAX), "too many pins");


static void bl_conv_s2u_function(void *ptr, uint32_t period_ns);

// array of function definitions - one copy in FLASH
static bl_function_def_t const bl_conv_s2u_functions[] = {
    { "update", BL_HAS_FP, &bl_conv_s2u_function }
};

_Static_assert((_countof(bl_conv_s2u_functions) < BL_FUNCTION_COUNT_MAX), "too many functions");


// component definition - one copy in FLASH
bl_comp_def_t const bl_conv_s2u_def = { 
    "conv_s2u",
    NULL,
    sizeof(bl_conv_s2u_inst_t),
    BL_NO_PERSONALITY,
    _countof(bl_conv_s2u_pins),
    _countof(bl_conv_s2u_functions),
    bl_conv_s2u_pins,
    bl_conv_s2u_functions
};

// realtime code - one copy in FLASH
static void bl_conv_s2u_function(void *ptr, uint32_t period_ns)
{
    (void)period_ns;  // unused in this component

    bl_conv_s2u_inst_t *p = (bl_conv_s2u_inst_t *)ptr;
    int32_t in = *(p->in);
    if ( in > 0 ) {
        *(p->out) = (uint32_t)in;
    } else {
        *(p->out) = 0;
    }
}

