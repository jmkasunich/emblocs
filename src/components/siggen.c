/*************************************************************
 * EMBLOCS component - signal generator
 */

#include "emblocs_comp.h"
#include <math.h>

/* instance data structure - one copy per instance in realtime RAM */
typedef struct bl_siggen_inst_s {
    double theta_d;
    bl_pin_bit_t reset;
    bl_pin_float_t freq;
	bl_pin_float_t amplitude_f;
	bl_pin_float_t offset_f;
    bl_pin_float_t angle_f;
    bl_pin_float_t square_f;
    bl_pin_float_t triangle_f;
    bl_pin_float_t sin_f;
    bl_pin_float_t cos_f;
	bl_pin_s32_t amplitude_i;
	bl_pin_s32_t offset_i;
    bl_pin_s32_t square_i;
    bl_pin_s32_t triangle_i;
    bl_pin_s32_t sin_i;
    bl_pin_s32_t cos_i;
} bl_siggen_inst_t;

_Static_assert((sizeof(bl_siggen_inst_t) < BL_INSTANCE_DATA_MAX_SIZE), "instance structure too large");


/* array of pin definitions - one copy in FLASH */
static bl_pin_def_t const bl_siggen_pins[] = {
    { "reset", BL_TYPE_BIT, BL_DIR_IN, offsetof(bl_siggen_inst_t, reset)},
    { "freq", BL_TYPE_FLOAT, BL_DIR_IN, offsetof(bl_siggen_inst_t, freq)},
    { "amplitude_f", BL_TYPE_FLOAT, BL_DIR_IN, offsetof(bl_siggen_inst_t, amplitude_f)},
    { "offset_f", BL_TYPE_FLOAT, BL_DIR_IN, offsetof(bl_siggen_inst_t, offset_f)},
    { "angle_f", BL_TYPE_FLOAT, BL_DIR_OUT, offsetof(bl_siggen_inst_t, angle_f)},
    { "square_f", BL_TYPE_FLOAT, BL_DIR_OUT, offsetof(bl_siggen_inst_t, square_f)},
    { "traingle_f", BL_TYPE_FLOAT, BL_DIR_OUT, offsetof(bl_siggen_inst_t, triangle_f)},
    { "sin_f", BL_TYPE_FLOAT, BL_DIR_OUT, offsetof(bl_siggen_inst_t, sin_f)},
    { "cos_f", BL_TYPE_FLOAT, BL_DIR_OUT, offsetof(bl_siggen_inst_t, cos_f)},
    { "amplitude_i", BL_TYPE_S32, BL_DIR_IN, offsetof(bl_siggen_inst_t, amplitude_i)},
    { "offset_i", BL_TYPE_S32, BL_DIR_IN, offsetof(bl_siggen_inst_t, offset_i)},
    { "square_i", BL_TYPE_S32, BL_DIR_OUT, offsetof(bl_siggen_inst_t, square_i)},
    { "traingle_i", BL_TYPE_S32, BL_DIR_OUT, offsetof(bl_siggen_inst_t, triangle_i)},
    { "sin_i", BL_TYPE_S32, BL_DIR_OUT, offsetof(bl_siggen_inst_t, sin_i)},
    { "cos_i", BL_TYPE_S32, BL_DIR_OUT, offsetof(bl_siggen_inst_t, cos_i)}
};

_Static_assert((_countof(bl_siggen_pins) < BL_PIN_COUNT_MAX), "too many pins");


static void bl_siggen_function(void *ptr, uint32_t period_ns);

// array of function definitions - one copy in FLASH
static bl_function_def_t const bl_siggen_functions[] = {
    { "update", BL_HAS_FP, &bl_siggen_function }
};

_Static_assert((_countof(bl_siggen_functions) < BL_FUNCTION_COUNT_MAX), "too many functions");


// component definition - one copy in FLASH
bl_comp_def_t const bl_siggen_def = { 
    "siggen",
    NULL,
    sizeof(bl_siggen_inst_t),
    BL_NO_PERSONALITY,
    _countof(bl_siggen_pins),
    _countof(bl_siggen_functions),
    bl_siggen_pins,
    bl_siggen_functions
};

// realtime code - one copy in FLASH
static void bl_siggen_function(void *ptr, uint32_t period_ns)
{
    float dt, dtheta, theta;
    float ampl_f, off_f, ampl_if;
    int32_t ampl_i, off_i;
    float tmp;

    bl_siggen_inst_t *p = (bl_siggen_inst_t *)ptr;
    /* calculate the time since last execution */
    dt = (float)period_ns * 0.000000001f;
    /* calculate how much of an output cycle that has passed */
    dtheta = *(p->freq) * dt;
    /* limit frequency to ensure it is less than 1/2 of Nyquist limit */
    if ( dtheta > 0.25f ) {
    	*(p->freq) = (0.25f/dt);
    	dtheta = 0.25;
    }
    /* angle_f ramps from 0.0 to 0.99999 for each output cycle */
    if ( *(p->reset) ) {
        p->theta_d = 0.0;
        theta = 0.0f;
    } else {
        p->theta_d += (double)dtheta;
        theta = (float)p->theta_d;
        if ( theta >= 1.0f ) {
            p->theta_d -= 1.0;
            theta = (float)p->theta_d;
        }
    }
  	*(p->angle_f) = theta;
    // generate the outputs
    ampl_f = *(p->amplitude_f);
    off_f = *(p->offset_f);
    ampl_i = *(p->amplitude_i);
    ampl_if = (float)ampl_i;
    off_i = *(p->offset_i);
    if ( theta > 0.5f ) {
        *(p->square_f) = off_f + ampl_f;
        *(p->square_i) = off_i + ampl_i;
        tmp = 3.0f - (4.0f * theta);
    } else {
        *(p->square_f) = off_f - ampl_f;
        *(p->square_i) = off_i - ampl_i;
        tmp = -1.0f + (4.0f * theta);
    }
    *(p->triangle_f) = ampl_f * tmp + off_f;
    *(p->triangle_i) = (int32_t)(ampl_if * tmp) + off_i;
    theta *= 6.283185307f;
    tmp = (float)sin(theta);
    *(p->sin_f) = ampl_f * tmp + off_f;
    *(p->sin_i) = (int32_t)(ampl_if * tmp) + off_i;
    tmp = (float)cos(theta);
    *(p->cos_f) = ampl_f * tmp + off_f;
    *(p->cos_i) = (int32_t)(ampl_if * tmp) + off_i;
}

