// EMBLOCS component - two input multiplexor

#include "emblocs.h"

// instance data structure - one copy per instance in realtime RAM
typedef struct bl_mux2_inst_s {
    bl_pin_float_t in0;
	bl_pin_float_t in1;
	bl_pin_float_t out;
	bl_pin_bit_t sel;
} bl_mux2_inst_t;

_Static_assert((sizeof(bl_mux2_inst_t) < 32767), "instance structure too large");

// array of pin definitions - one copy in FLASH
static bl_pin_def_t const bl_mux2_pins[] = {
    { "in0", BL_TYPE_FLOAT, BL_DIR_IN, BL_OFFSET(bl_mux2_inst_t, in0)},
    { "in1", BL_TYPE_FLOAT, BL_DIR_IN, BL_OFFSET(bl_mux2_inst_t, in1)},
    { "out", BL_TYPE_FLOAT, BL_DIR_OUT, BL_OFFSET(bl_mux2_inst_t, out)},
    { "sel", BL_TYPE_BIT, BL_DIR_IN, BL_OFFSET(bl_mux2_inst_t, sel)}
};

static void bl_mux2_funct(void *ptr);

// array of function definitions - one copy in FLASH
static bl_funct_def_t const bl_mux2_functs[] = {
    { "funct", &bl_mux2_funct }
};

// component definition - one copy in FLASH
bl_comp_def_t const bl_mux2_def = { 
    "mux2",
    ARRAYCOUNT(bl_mux2_pins),
    ARRAYCOUNT(bl_mux2_functs),
    sizeof(bl_mux2_inst_t),
    &(bl_mux2_pins[0]),
    &(bl_mux2_functs[0])
};

// realtime code - one copy in FLASH
static void bl_mux2_funct(void *ptr)
{
    bl_mux2_inst_t *p = (bl_mux2_inst_t *)ptr;
    if ( *(p->sel.pin) ) {
        *(p->out.pin) = *(p->in1.pin);
    } else {
        *(p->out.pin) = *(p->in0.pin);
    }
}

