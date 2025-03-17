// EMBLOCS component - GPIO driver
//

#include "emblocs_comp.h"
#include "platform.h"
#include "tmp_gpio.h"
#include "platform_g431.h"
#include "printing.h"

// instance data structure - one copy per instance in RAM
typedef struct bl_gpio_instance_s {
    GPIO_TypeDef *base_addr;
    bl_pin_bit_t *output_pins;
    bl_pin_bit_t *out_ena_pins;
    uint16_t output_bitmask;
    uint16_t out_ena_bitmask;
    bl_pin_bit_t *input_pins;
    uint16_t input_bitmask;
} bl_gpio_instance_t;

// we can have up to 3 blocs pins (in, out, output enable) per hardware pin
// and 16 hardware pins per port
#define GPIO_MAX_PINS (3*16)
#define GPIO_MAX_INSTANCE_SIZE (sizeof(bl_gpio_instance_t)+GPIO_MAX_PINS*sizeof(bl_pin_t))

_Static_assert((GPIO_MAX_PINS < BL_PIN_COUNT_MAX), "too many pins");
_Static_assert((GPIO_MAX_INSTANCE_SIZE < BL_INSTANCE_DATA_MAX_SIZE), "instance structure too large");

// pin name strings
// (pin definitions are created dynamically, but the strings must exist in flash)
char const pin_names_in[16][6] = {
    "00_in", "01_in", "02_in", "03_in",
    "04_in", "05_in", "06_in", "07_in",
    "08_in", "09_in", "10_in", "11_in",
    "12_in", "13_in", "14_in", "15_in"
};

char const pin_names_out[16][7] = {
    "00_out", "01_out", "02_out", "03_out",
    "04_out", "05_out", "06_out", "07_out",
    "08_out", "09_out", "10_out", "11_out",
    "12_out", "13_out", "14_out", "15_out"
};

char const pin_names_oe[16][6] = {
    "00_oe", "01_oe", "02_oe", "03_oe",
    "04_oe", "05_oe", "06_oe", "07_oe",
    "08_oe", "09_oe", "10_oe", "11_oe",
    "12_oe", "13_oe", "14_oe", "15_oe"
};


static void bl_gpio_read_function(void *ptr, uint32_t period_ns);
static void bl_gpio_write_function(void *ptr, uint32_t period_ns);

// array of function definitions - one copy in FLASH
static bl_function_def_t const bl_gpio_functions[] = {
    { "read", BL_NO_FP, &bl_gpio_read_function },
    { "write", BL_NO_FP, &bl_gpio_write_function }
};


/* component-specific setup function */
struct bl_instance_meta_s *gpio_setup(char const *instance_name, struct bl_comp_def_s const *comp_def, void const *personality);


// component definition - one copy in FLASH
bl_comp_def_t const bl_gpio_def = { 
    "gpio",
    gpio_setup,
    sizeof(bl_gpio_instance_t),
    0,
    _countof(bl_gpio_functions),
    NULL,
    bl_gpio_functions
};

static void write_bitfield(volatile uint32_t *dest, uint32_t value, int field_width, int field_num)
{
    uint32_t mask, tmp;

    mask = ~(0xFFFFFFFF << field_width);
    tmp = (*dest) & (~(mask << (field_num * field_width)));
    *dest = tmp | ((value & mask) << (field_num * field_width));
}


/* component-specific setup function */
struct bl_instance_meta_s *gpio_setup(char const *instance_name, struct bl_comp_def_s const *comp_def, void const *personality)
{
    gpio_port_config_t *p = (gpio_port_config_t *)personality;
    int pins_in, pins_out, pins_oe, pins_total;
    uint16_t input_bitmask, output_bitmask, out_ena_bitmask, active_bit;
    GPIO_TypeDef *base_addr;
    gpio_pin_config_t *pin;
    uint32_t hw_mode;
    struct bl_instance_meta_s *meta;
    bl_gpio_instance_t *data;
    bl_pin_t *next_pin;
    bl_pin_def_t pindef;

    // configure the hardware and find out how many blocs pins we need
    pins_in = pins_out = pins_oe = 0;
    input_bitmask = output_bitmask = out_ena_bitmask = 0;
    // point at the hardware
    base_addr = p->base_address;
    // loop through config info
    active_bit = 1;
    for ( int n = 0 ; n < 16 ; n++ ) {
        pin = &(p->pins[n]);
        hw_mode = 0;
        switch(pin->pin_mode) {
        case BGPIO_MD_BIO:
            pins_out++;
            output_bitmask |= active_bit;
            pins_oe++;
            out_ena_bitmask |= active_bit;
            [[fallthrough]];
        case BGPIO_MD_BIN:
            pins_in++;
            input_bitmask |= active_bit;
            [[fallthrough]];
        case BGPIO_MD_IN:
            hw_mode = 0;
            break;
        case BGPIO_MD_BOUT:
            pins_out++;
            output_bitmask |= active_bit;
            [[fallthrough]];
        case BGPIO_MD_OUT:
            hw_mode = 1;
            break;
        case BGPIO_MD_ALT:
            hw_mode = 2;
            break;
        case BGPIO_MD_ANA:
            hw_mode = 3;
            break;
        default:
            break;
        }
        write_bitfield(&(base_addr->MODER), hw_mode, 2, n);
        write_bitfield(&(base_addr->OTYPER), pin->output_type, 1, n);
        write_bitfield(&(base_addr->OSPEEDR), pin->output_spd, 2, n);
        write_bitfield(&(base_addr->PUPDR), pin->pu_pd, 2, n);
        if ( n < 8 ) {
            write_bitfield(&(base_addr->AFR[0]), pin->alt_funct, 4, n);
        } else {
            write_bitfield(&(base_addr->AFR[1]), pin->alt_funct, 4, n-8);
        }
        active_bit <<= 1;
    }
    // now the emblocs setup - create an instance of the proper size to include all pins
    pins_total = pins_in + pins_out + pins_oe;
    meta = bl_instance_create(instance_name, comp_def, comp_def->data_size+pins_total*sizeof(bl_pin_t));
    data = bl_instance_data_addr(meta);
    // fill in instance data fields
    data->base_addr = p->base_address;
    data->input_bitmask = input_bitmask;
    data->output_bitmask = output_bitmask;
    data->out_ena_bitmask = out_ena_bitmask;
    // prepare for pin creation
    // dynamic pins follow the main instance data structure
    next_pin = (bl_pin_t *)((char *)data + sizeof(bl_gpio_instance_t));
    pindef.data_type = BL_TYPE_BIT;
    // hardware input pins result in data flow out of the driver
    pindef.pin_dir = BL_DIR_OUT;
    data->input_pins = (bl_pin_bit_t *)next_pin;
    active_bit = 1;
    for ( int n = 0 ; n < 16 ; n++ ) {
        if ( input_bitmask & active_bit ) {
            // create a pin
            pindef.name = &(pin_names_in[n][0]);
            pindef.data_offset = TO_INSTANCE_SIZE((uint32_t)((char *)next_pin - (char *)data));
            bl_instance_add_pin(meta, &pindef);
            next_pin++;
        }
        active_bit <<= 1;
    }
    // hardware output pins are driven by data flowing into the driver
    pindef.pin_dir = BL_DIR_IN;
    data->output_pins = (bl_pin_bit_t *)next_pin;
    active_bit = 1;
    for ( int n = 0 ; n < 16 ; n++ ) {
        if ( output_bitmask & active_bit ) {
            // create a pin
            pindef.name = &(pin_names_out[n][0]);
            pindef.data_offset = TO_INSTANCE_SIZE((uint32_t)((char *)next_pin - (char *)data));
            bl_instance_add_pin(meta, &pindef);
            next_pin++;
        }
        active_bit <<= 1;
    }
    data->out_ena_pins = (bl_pin_bit_t *)next_pin;
    active_bit = 1;
    for ( int n = 0 ; n < 16 ; n++ ) {
        if ( out_ena_bitmask & active_bit ) {
            // create a pin
            pindef.name = &(pin_names_oe[n][0]);
            pindef.data_offset = TO_INSTANCE_SIZE((uint32_t)((char *)next_pin - (char *)data));
            bl_instance_add_pin(meta, &pindef);
            next_pin++;
        }
        active_bit <<= 1;
    }
    return meta;
}


// realtime code - one copy in FLASH
static void bl_gpio_read_function(void *ptr, uint32_t period_ns)
{
    (void)period_ns;  // not used
    bl_gpio_instance_t *p = (bl_gpio_instance_t *)ptr;
    uint32_t shifter;
    bl_pin_bit_t *pin;

    // read the hardware into low half of shifter
    shifter = p->base_addr->IDR;
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

static void bl_gpio_write_function(void *ptr, uint32_t period_ns)
{
    (void)period_ns;  // not used
    bl_gpio_instance_t *p = (bl_gpio_instance_t *)ptr;
    uint32_t bitmask, active_bit, bsrr, mode;
    bl_pin_bit_t *pin;

    // manage outputs
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
    p->base_addr->BSRR = bsrr;
    // manage output enables
    bitmask = p->out_ena_bitmask;
    active_bit = 1;
    mode = p->base_addr->MODER;
    pin = p->out_ena_pins;
    while ( bitmask != 0 ) {
        if ( bitmask & 0x0001 ) {
            // a blocs pin exists
            if ( **(pin++) ) {    // test pin and update ptr for next one
                // set the pin mode to output
                mode |= active_bit;
            } else {
                // set the pin mode to input
                mode &= ~active_bit;
            }
        }
        bitmask >>= 1;
        active_bit <<= 2;
    }
    p->base_addr->MODER = mode;
}

