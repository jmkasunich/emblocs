// EMBLOCS component - two input multiplexor

#include "emblocs.h"

// instance data structure - one copy per instance in RAM
typedef struct {
    bl_inst_header_t header;
    bl_float_t *in0;
	bl_float_t *in1;
	bl_float_t *out;
	bl_bit_t *sel;
} bl_mux2_inst_t;

// realtime code - one copy in FLASH
static void bl_mux2_funct(bl_inst_header_t *ptr)
{
    bl_mux2_inst_t *p = (bl_mux2_inst_t *)ptr;
    if ( *(p->sel) ) {
        *(p->out) = *(p->in1);
    } else {
        *(p->out) = *(p->in0);
    }
}

// pin definitions - one copy in FLASH
static bl_pin_def_t const bl_mux2_pins[] = {
    { "in0", BL_PINTYPE_FLOAT, BL_PINDIR_IN, offsetof(bl_mux2_inst_t, in0)},
    { "in1", BL_PINTYPE_FLOAT, BL_PINDIR_IN, offsetof(bl_mux2_inst_t, in1)},
    { "out", BL_PINTYPE_FLOAT, BL_PINDIR_OUT, offsetof(bl_mux2_inst_t, out)},
    { "sel", BL_PINTYPE_BIT, BL_PINDIR_IN, offsetof(bl_mux2_inst_t, sel)}
};

// function definitions - one copy in FLASH
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

