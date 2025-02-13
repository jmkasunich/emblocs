// EMBLOCS component - GPIO driver
//

#include "emblocs.h"
#include "platform.h"

/*********************************************
 * 
 * GPIO management:
 * 
 * For every pin on the MCU, must define how it is used
 *     GPIO Input
 *     GPIO Output
 *     Alternate Function (and which one)
 *     Analog
 * If it is an output (GPIO or Alternate function), must 
 * select speed and push-pull or open-drain
 * If it is GPIO, must decide if it will be mapped to
 * an emblocs pin (and driven by gpio_read or gpio_write
 * functions) or controlled directly
 * 
 * 
 */

typedef enum {
    GPOUT = 0,          // no blocs pins; GP output control by registers
    ALTFUNCT = 1,       // no blocs pins; choose an alternate function
    GPIN = 2,           // no blocs pins; GP input
    ANALOG = 3,         // no blocs pins; analog
    BL_IN = 4,          // exports in pin
    BL_OUT = 5,         // exports out pin
    BL_IO = 6,          // exports in, out, and output enable pins
} gpio_pin_mode_t;

#define GPIO_MODE_MASK (0x007)

typedef enum {
    PUSHPULL = 0,
    OPENDRAIN = 0x08
} gpio_output_type_t;

#define GPIO_OUTPUT_TYPE_MASK (0x008)

typedef enum {
    SPD_SLOW = 0,
    SPD_MED = 0x010,
    SPD_FAST = 0x20,
    SPD_VFAST = 0x30
} gpio_output_speed_t;

#define GPIO_OUTPUT_SPEED_MASK (0x030)

typedef enum {
    NO_PU_PD = 0,
    PULL_UP = 0x40,
    PULL_DOWN = 0x80
} gpio_pu_pd_t;

#define GPIO_PU_PD_MASK (0x0C0)

#define GPIO_ALT_FUNCT_MASK (0xF00)
#define GPIO_ALT_FUNCT_SHIFT (8)



// instance data structure - one copy per instance in RAM
typedef struct bl_gpio_inst_s {
    bl_pin_bit_t bits[16];
	uint32_t tsc;
} bl_gpio_inst_t;

_Static_assert((sizeof(bl_gpio_inst_t) < 32767), "instance structure too large");

// array of pin definitions - one copy in FLASH
static bl_pin_def_t const bl_gpio_pins[] = {
    { "time", BL_TYPE_U32, BL_DIR_OUT, offsetof(bl_gpio_inst_t, bits[0])}
};

static void bl_gpio_read_funct(void *ptr);
static void bl_gpio_write_funct(void *ptr);

/*
// array of function definitions - one copy in FLASH
static bl_funct_def_t const bl_gpio_functs[] = {
    { "read", &bl_gpio_read_funct },
    { "write", &bl_gpio_write_funct }
};
*/

/* component-specific setup function */
bl_inst_meta_t * gpio_setup(char const *inst_name, struct bl_comp_def_s *comp_def, void *personality);



// component definition - one copy in FLASH
bl_comp_def_t const bl_gpio_def = { 
    "gpio",
    gpio_setup,
    sizeof(bl_gpio_inst_t),
    _countof(bl_gpio_pins),
//    ARRAYCOUNT(bl_gpio_functs),
    &(bl_gpio_pins[0])
//    &(bl_gpio_functs[0])
};

// realtime code - one copy in FLASH
static void bl_gpio_read_funct(void *ptr)
{
    bl_gpio_inst_t *p = (bl_gpio_inst_t *)ptr;

    p->tsc = tsc_read();
}

static void bl_gpio_write_funct(void *ptr)
{
    bl_gpio_inst_t *p = (bl_gpio_inst_t *)ptr;

    *(p->bits) = tsc_read() - p->tsc;
}

