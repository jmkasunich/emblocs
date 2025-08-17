// EMBLOCS component - GPIO driver for RP2040
//

#include "emblocs_comp.h"
#include "rp2040_gpio.h"
#include "pico/stdlib.h"
#include "hardware/gpio.h"

// instance data structure - one copy per instance in RAM
typedef struct bl_rp2040_gpio_instance_s {
    bl_pin_bit_t *output_pins;
    bl_pin_bit_t *out_ena_pins;
    uint32_t output_bitmask;
    uint32_t out_ena_bitmask;
    bl_pin_bit_t *input_pins;
    uint32_t input_bitmask;
} bl_rp2040_gpio_instance_t;

// we can have up to 3 blocs pins (in, out, output enable) per hardware pin
// and 30 hardware pins on the RP2040
#define GPIO_MAX_HW_PINS (30)
#define GPIO_MAX_BL_PINS (3*GPIO_MAX_HW_PINS)
#define GPIO_MAX_INSTANCE_SIZE (sizeof(bl_rp2040_gpio_instance_t)+GPIO_MAX_BL_PINS*sizeof(bl_pin_t))

_Static_assert((GPIO_MAX_BL_PINS < BL_PIN_COUNT_MAX), "too many pins");
_Static_assert((GPIO_MAX_INSTANCE_SIZE < BL_INSTANCE_DATA_MAX_SIZE), "instance structure too large");

// pin name strings
// (pin definitions are created dynamically, but the strings must exist in flash)
static char const pin_names_in[30][6] = {
    "p00in", "p01in", "p02in", "p03in",
    "p04in", "p05in", "p06in", "p07in",
    "p08in", "p09in", "p10in", "p11in",
    "p12in", "p13in", "p14in", "p15in",
    "p16in", "p17in", "p18in", "p19in",
    "p20in", "p21in", "p22in", "p23in",
    "p24in", "p25in", "p26in", "p27in",
    "p28in", "p29in"
};

static char const pin_names_out[30][7] = {
    "p00out", "p01out", "p02out", "p03out",
    "p04out", "p05out", "p06out", "p07out",
    "p08out", "p09out", "p10out", "p11out",
    "p12out", "p13out", "p14out", "p15out",
    "p16out", "p17out", "p18out", "p19out",
    "p20out", "p21out", "p22out", "p23out",
    "p24out", "p25out", "p26out", "p27out",
    "p28out", "p29out"
};

static char const pin_names_oe[30][6] = {
    "p00oe", "p01oe", "p02oe", "p03oe",
    "p04oe", "p05oe", "p06oe", "p07oe",
    "p08oe", "p09oe", "p10oe", "p11oe",
    "p12oe", "p13oe", "p14oe", "p15oe",
    "p16oe", "p17oe", "p18oe", "p19oe",
    "p20oe", "p21oe", "p22oe", "p23oe",
    "p24oe", "p25oe", "p26oe", "p27oe",
    "p28oe", "p29oe"
};


static void bl_gpio_read_function(void *ptr, uint32_t period_ns);
static void bl_gpio_write_function(void *ptr, uint32_t period_ns);

// array of function definitions - one copy in FLASH
static bl_function_def_t const bl_gpio_functions[] = {
    { "read", BL_NO_FP, &bl_gpio_read_function },
    { "write", BL_NO_FP, &bl_gpio_write_function }
};


/* component-specific setup function */
struct bl_instance_meta_s *rp2040_gpio_setup(char const *instance_name, struct bl_comp_def_s const *comp_def, void const *personality);


// component definition - one copy in FLASH
bl_comp_def_t const bl_rp2040_gpio_def = {
    "rp2040_gpio",
    rp2040_gpio_setup,
    sizeof(bl_rp2040_gpio_instance_t),
    BL_NEEDS_PERSONALITY,
    0,
    _countof(bl_gpio_functions),
    NULL,
    bl_gpio_functions
};

#pragma GCC optimize ("no-strict-aliasing")
/* component-specific setup function */
struct bl_instance_meta_s *rp2040_gpio_setup(char const *instance_name, struct bl_comp_def_s const *comp_def, void const *personality)
{
    rp2040_gpio_config_t *p = (rp2040_gpio_config_t *)personality;
    uint pins_in, pins_out, pins_oe, pins_total;
    uint32_t input_bitmask, output_bitmask, used_bitmask, bidir_bitmask, active_bit;
    bl_rp2040_gpio_instance_t *data;
    struct bl_instance_meta_s *meta;
    bl_pin_t *next_pin;
    bl_pin_def_t pindef;
    bool result;

    CHECK_NULL(comp_def);
    CHECK_NULL(personality);
    // configure the hardware and find out how many blocs pins we need
    pins_in = pins_out = pins_oe = 0;
    input_bitmask = p->input_pins;
    output_bitmask = p->output_pins;
    used_bitmask = input_bitmask | output_bitmask;
    bidir_bitmask = input_bitmask & output_bitmask;
    // loop through config info
    active_bit = 1;
    for ( uint n = 0 ; n < GPIO_MAX_HW_PINS ; n++ ) {
        if ( used_bitmask & active_bit ) {
            gpio_init(n);
            if ( input_bitmask & active_bit ) {
                gpio_set_dir(n, 0);
                pins_in++;
            }
            if ( output_bitmask & active_bit ) {
                gpio_set_dir(n, 1);
                pins_out++;
            }
            if ( bidir_bitmask & active_bit ) {
                gpio_set_dir(n, 0);
                pins_oe++;
            }
        }
        active_bit <<= 1;
    }
    // now the emblocs setup - create an instance of the proper size to include all pins
    pins_total = pins_in + pins_out + pins_oe;
    meta = bl_instance_create(instance_name, comp_def, comp_def->data_size+pins_total*sizeof(bl_pin_t));
    CHECK_RETURN(meta);
    data = bl_instance_data_addr(meta);
    CHECK_RETURN(data);
    // fill in instance data fields
    data->input_bitmask = input_bitmask;
    data->output_bitmask = output_bitmask;
    data->out_ena_bitmask = bidir_bitmask;
    // prepare for pin creation
    // dynamic pins follow the main instance data structure
    next_pin = (bl_pin_t *)((char *)data + sizeof(bl_rp2040_gpio_instance_t));
    pindef.data_type = BL_TYPE_BIT;
    // hardware input pins result in data flow out of the driver
    pindef.pin_dir = BL_DIR_OUT;
    data->input_pins = (bl_pin_bit_t *)next_pin;
    active_bit = 1;
    for ( uint n = 0 ; n < GPIO_MAX_HW_PINS ; n++ ) {
        if ( input_bitmask & active_bit ) {
            // create a pin
            pindef.name = &(pin_names_in[n][0]);
            pindef.data_offset = TO_INSTANCE_SIZE((uint32_t)((char *)next_pin - (char *)data));
            result = bl_instance_add_pin(meta, &pindef);
            CHECK_RETURN(result);
            next_pin++;
        }
        active_bit <<= 1;
    }
    // hardware output pins are driven by data flowing into the driver
    pindef.pin_dir = BL_DIR_IN;
    data->output_pins = (bl_pin_bit_t *)next_pin;
    active_bit = 1;
    for ( uint n = 0 ; n < GPIO_MAX_HW_PINS ; n++ ) {
        if ( output_bitmask & active_bit ) {
            // create a pin
            pindef.name = &(pin_names_out[n][0]);
            pindef.data_offset = TO_INSTANCE_SIZE((uint32_t)((char *)next_pin - (char *)data));
            result = bl_instance_add_pin(meta, &pindef);
            CHECK_RETURN(result);
            next_pin++;
        }
        active_bit <<= 1;
    }
    data->out_ena_pins = (bl_pin_bit_t *)next_pin;
    active_bit = 1;
    for ( uint n = 0 ; n < GPIO_MAX_HW_PINS ; n++ ) {
        if ( bidir_bitmask & active_bit ) {
            // create a pin
            pindef.name = &(pin_names_oe[n][0]);
            pindef.data_offset = TO_INSTANCE_SIZE((uint32_t)((char *)next_pin - (char *)data));
            result = bl_instance_add_pin(meta, &pindef);
            CHECK_RETURN(result);
            next_pin++;
        }
        active_bit <<= 1;
    }
    // finally, create the functions; nothing custom here
    result = bl_instance_add_functions(meta, comp_def);
    CHECK_RETURN(result);
    return meta;
}
#pragma GCC reset_options


// realtime code - one copy in FLASH
static void bl_gpio_read_function(void *ptr, uint32_t period_ns)
{
    (void)period_ns;  // not used
    bl_rp2040_gpio_instance_t *p = (bl_rp2040_gpio_instance_t *)ptr;
    uint32_t in_data, in_mask;
    bl_pin_bit_t *pin;

    // read the hardware
    in_data = gpio_get_all();
    // get config
    in_mask = p->input_bitmask;
    // point at first emblocs pin
    pin = p->input_pins;
    while ( in_mask != 0 ) {
        if ( in_mask & 1 ) {
            // a blocs pin exists, set its value
            **pin = in_data & 1;
            pin++;
        }
        in_mask >>= 1;
        in_data >>= 1;
    }
}

static void bl_gpio_write_function(void *ptr, uint32_t period_ns)
{
    (void)period_ns;  // not used
    bl_rp2040_gpio_instance_t *p = (bl_rp2040_gpio_instance_t *)ptr;
    uint32_t bitmask, active_bit;
    bl_pin_bit_t *pin;

    // manage outputs
    bitmask = p->output_bitmask;
    active_bit = 1;
    pin = p->output_pins;
    while ( bitmask != 0 ) {
        if ( bitmask & active_bit ) {
            // a blocs pin exists
            if ( **(pin++) ) {    // test pin and update ptr for next one
                 gpio_set_mask(active_bit);
            } else {
                 gpio_clr_mask(active_bit);
            }
            bitmask &= ~active_bit;
        }
        active_bit <<= 1;
    }
    // manage output enables
    bitmask = p->out_ena_bitmask;
    active_bit = 1;
    pin = p->out_ena_pins;
    while ( bitmask != 0 ) {
        if ( bitmask & active_bit ) {
            // a blocs pin exists
            if ( **(pin++) ) {    // test pin and update ptr for next one
                gpio_set_dir_out_masked(active_bit);
            } else {
                gpio_set_dir_in_masked(active_bit);
            }
            bitmask &= ~active_bit;
        }
        active_bit <<= 1;
    }
}

