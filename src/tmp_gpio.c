// EMBLOCS component - GPIO driver
//

#include "emblocs.h"
#include "platform.h"
#include "tmp_gpio.h"


// instance data structure - one copy per instance in RAM
typedef struct bl_gpio_inst_s {
    bl_pin_bit_t *output_pins;
    bl_pin_bit_t *out_ena_pins;
    uint16_t output_bitmask;
    uint16_t out_ena_bitmask;
    bl_pin_bit_t *input_pins;
    uint16_t input_bitmask;
	uint32_t tsc;
} bl_gpio_inst_t;

_Static_assert((sizeof(bl_gpio_inst_t) < 32767), "instance structure too large");

// pin name strings
// (pin definitions are created dynamically, but the strings must exist in flash)
char const * const pin_names_in[16] = {
    "00_in", "01_in", "02_in", "03_in",
    "04_in", "05_in", "06_in", "07_in",
    "08_in", "09_in", "10_in", "11_in",
    "12_in", "13_in", "14_in", "15_in"
};

char const * const pin_names_out[16] = {
    "00_out", "01_out", "02_out", "03_out",
    "04_out", "05_out", "06_out", "07_out",
    "08_out", "09_out", "10_out", "11_out",
    "12_out", "13_out", "14_out", "15_out"
};

char const * const pin_names_io[16] = {
    "00_io", "01_io", "02_io", "03_io",
    "04_io", "05_io", "06_io", "07_io",
    "08_io", "09_io", "10_io", "11_io",
    "12_io", "13_io", "14_io", "15_io"
};


// array of pin definitions - one copy in FLASH
static bl_pin_def_t const bl_gpio_pins[] = {
    { "time", BL_TYPE_U32, BL_DIR_OUT, offsetof(bl_gpio_inst_t, tsc)}
};

static void bl_gpio_read_funct(void *ptr, uint32_t period_ns);
static void bl_gpio_write_funct(void *ptr, uint32_t period_ns);

// array of function definitions - one copy in FLASH
static bl_funct_def_t const bl_gpio_functs[] = {
    { "read", BL_NO_FP, &bl_gpio_read_funct },
    { "write", BL_NO_FP, &bl_gpio_write_funct }
};


/* component-specific setup function */
bl_inst_meta_t * gpio_setup(char const *inst_name, struct bl_comp_def_s const *comp_def, void const *personality);


// component definition - one copy in FLASH
bl_comp_def_t const bl_gpio_def = { 
    "gpio",
    gpio_setup,
    sizeof(bl_gpio_inst_t),
    _countof(bl_gpio_pins),
    _countof(bl_gpio_functs),
    bl_gpio_pins,
    bl_gpio_functs
};


/* component-specific setup function */
bl_inst_meta_t * gpio_setup(char const *inst_name, struct bl_comp_def_s const *comp_def, void const *personality)
{

}


static volatile uint16_t IDR;

// realtime code - one copy in FLASH
static void bl_gpio_read_funct(void *ptr, uint32_t period_ns)
{
    (void)period_ns;  // not used
    bl_gpio_inst_t *p = (bl_gpio_inst_t *)ptr;
    uint32_t shifter;
    bl_pin_bit_t *pin;

    // read the hardware into low half of shifter
    shifter = IDR;
    // put bitmask in high half of shifter
    shifter |= ((uint32_t)(p->input_bitmask) << 16);
    pin = p->input_pins;
    while ( shifter & 0xFFFF0000 ) {
        if ( shifter & 0x00010000) {
            // a blocs pin exists, set its value
            **pin = shifter & 0x00000001;
            pin++;
        }
        shifter >>= 1;
    }
}




static volatile uint32_t BSRR;

static void bl_gpio_write_funct(void *ptr, uint32_t period_ns)
{
    (void)period_ns;  // not used
    bl_gpio_inst_t *p = (bl_gpio_inst_t *)ptr;
    uint32_t bitmask, active_bit, bsrr;
    bl_pin_bit_t *pin;

    bitmask = p->output_bitmask;
    active_bit = 1;
    bsrr = 0;
    pin = p->output_pins;
    while ( bitmask != 0 ) {
        if ( bitmask & active_bit ) {
            // a blocs pin exists
            if ( **(pin++) ) {    // test pin and update ptr for next one
                // write to set half of BSRR
                bsrr |= active_bit;
            } else {
                // write to reset half of BSRR
                bsrr |= (active_bit << 16);
            }
            bitmask &= ~active_bit;
        }
        active_bit <<= 1;
    }
    BSRR = bsrr;
    p->tsc = tsc_read() - p->tsc;
}

