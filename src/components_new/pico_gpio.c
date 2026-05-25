// Generated once by the EMBLOCS block compiler.
// Edit freely - this file will not be overwritten.
// Source: pico_gpio.bloc

#include "emblocs_comp.h"

#define BL_BLOCK_NAME pico_gpio

// set default parameter values if not supplied
#ifndef INPUTS
#define INPUTS (33554432)
#endif
#ifndef OUTPUTS
#define OUTPUTS (33554432)
#endif
#ifndef ENABLES
#define ENABLES (33554432)
#endif

#include "pico_gpio.h"

// EMBLOCS:  DO NOT REMOVE OR EDIT ABOVE THIS LINE

#include "pico/stdlib.h"
#include "hardware/structs/sio.h"

void BL_MANGLE(init)(void *instance_data, uint32_t periodns) {
    BL_MANGLE(t) *self = (BL_MANGLE(t) *)instance_data;
    (void)periodns;

    for (int n = 0; n < 30; n++) {
#if (INPUTS!=0)
        if (pPIN00_IN_[n] != NULL) {
            gpio_init(n);
            gpio_set_dir(n, GPIO_IN);
        }
#endif
#if (OUTPUTS!=0)
        if (pPIN00_OUT_[n] != NULL) {
            gpio_init(n);
#if (ENABLES!=0)
            if (pPIN00_OE_[n] == NULL) {
                // no output enable pin - always an output
                gpio_set_dir(n, GPIO_OUT);
            } else {
                // has output enable - start as input, write() will manage direction
                gpio_set_dir(n, GPIO_IN);
            }
#else
            // no ENABLES - always an output
            gpio_set_dir(n, GPIO_OUT);
#endif
        }
#endif
    }
}

#if (INPUTS!=0)
void BL_MANGLE(read)(void *instance_data, uint32_t periodns) {
    BL_MANGLE(t) *self = (BL_MANGLE(t) *)instance_data;
    (void)periodns;

    uint32_t gpio_in = sio_hw->gpio_in;
    for (int n = 0; n < 30; n++) {
        if (pPIN00_IN_[n] != NULL) {
            PIN00_IN_(n) = (gpio_in >> n) & 1;
        }
    }
}
#endif

#if (OUTPUTS!=0)
void BL_MANGLE(write)(void *instance_data, uint32_t periodns) {
    BL_MANGLE(t) *self = (BL_MANGLE(t) *)instance_data;
    (void)periodns;

    uint32_t set_mask = 0;
    uint32_t clr_mask = 0;
    for (int n = 0; n < 30; n++) {
        if (pPIN00_OUT_[n] != NULL) {
            if (PIN00_OUT_(n)) {
                set_mask |= 1u << n;
            } else {
                clr_mask |= 1u << n;
            }
        }
    }
    sio_hw->gpio_set = set_mask;
    sio_hw->gpio_clr = clr_mask;

#if (ENABLES!=0)
    uint32_t oe_set = 0;
    uint32_t oe_clr = 0;
    for (int n = 0; n < 30; n++) {
        if (pPIN00_OE_[n] != NULL) {
            if (PIN00_OE_(n)) {
                oe_set |= 1u << n;
            } else {
                oe_clr |= 1u << n;
            }
        }
    }
    sio_hw->gpio_oe_set = oe_set;
    sio_hw->gpio_oe_clr = oe_clr;
#endif
}
#endif
