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

#ifndef GPIO_H
#define GPIO_H PB

#include <stdint.h>
#include "platform_g431.h"

typedef enum {
    BGPIO_MD_IN = 0,        // no blocs pins; GP output control by registers
    BGPIO_MD_OUT = 1,       // no blocs pins; GP input
    BGPIO_MD_ALT = 2,       // no blocs pins; alternate function
    BGPIO_MD_ANA = 3,       // no blocs pins; analog
    BGPIO_MD_BIN = 4,       // exports in pin
    BGPIO_MD_BOUT = 5,      // exports out pin
    BGPIO_MD_BIO = 6,       // exports in, out, and output enable pins
} gpio_pin_mode_t;

#define GPIO_PIN_MODE_BITS (3)

typedef enum {
    BGPIO_OUT_PP = 0,
    BGPIO_OUT_OD = 1
} gpio_output_type_t;

#define GPIO_OUTPUT_TYPE_BITS (1)

typedef enum {
    BGPIO_SPD_SLOW = 0,
    BGPIO_SPD_MED = 1,
    BGPIO_SPD_FAST = 2,
    BGPIO_SPD_VFST = 3
} gpio_output_speed_t;

#define GPIO_OUTPUT_SPEED_BITS (2)

typedef enum {
    BGPIO_PULL_NONE = 0,
    BGPIO_PULL_UP = 1,
    BGPIO_PULL_DOWN = 2
} gpio_pull_t;

#define GPIO_PULL_BITS (2)

typedef enum {
    BGPIO_AF0 = 0,
    BGPIO_AF1 = 1,
    BGPIO_AF2 = 2,
    BGPIO_AF3 = 3,
    BGPIO_AF4 = 4,
    BGPIO_AF5 = 5,
    BGPIO_AF6 = 6,
    BGPIO_AF7 = 7,
    BGPIO_AF8 = 8,
    BGPIO_AF9 = 9,
    BGPIO_AF10 = 10,
    BGPIO_AF11 = 11,
    BGPIO_AF12 = 12,
    BGPIO_AF13 = 13,
    BGPIO_AF14 = 14,
    BGPIO_AF15 = 15
} gpio_alt_funct_t;

#define GPIO_ALT_FUNCT_BITS (4)

typedef struct  {
    uint16_t pin_mode     : GPIO_PIN_MODE_BITS;
    uint16_t output_type  : GPIO_OUTPUT_TYPE_BITS;
    uint16_t output_spd   : GPIO_OUTPUT_SPEED_BITS;
    uint16_t pu_pd        : GPIO_PULL_BITS;
    uint16_t alt_funct    : GPIO_ALT_FUNCT_BITS;
} gpio_pin_config_t;

typedef struct {
    GPIO_TypeDef *base_address;
    gpio_pin_config_t pins[16];
} gpio_port_config_t;


#endif // GPIO_H
