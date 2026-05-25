// Generated once by the EMBLOCS block compiler.
// Edit freely - this file will not be overwritten.
// Source: stm32_gpio.bloc

#include "emblocs_comp.h"

#define BL_BLOCK_NAME stm32_gpio

// set default parameter values if not supplied
#ifndef PORT_NUM
#define PORT_NUM (0)
#endif
#ifndef INPUTS
#define INPUTS (255)
#endif
#ifndef OUTPUTS
#define OUTPUTS (65280)
#endif
#ifndef ENABLES
#define ENABLES (65280)
#endif

#include "stm32_gpio.h"

// EMBLOCS:  DO NOT REMOVE OR EDIT ABOVE THIS LINE

// used to convert PORT_NUM parameter to GPIOA...GPIOG
#define _GPIO_FROM_NUM_0   GPIOA
#define _GPIO_FROM_NUM_1   GPIOB
#define _GPIO_FROM_NUM_2   GPIOC
#define _GPIO_FROM_NUM_3   GPIOD
#define _GPIO_FROM_NUM_4   GPIOE
#define _GPIO_FROM_NUM_5   GPIOF
#define _GPIO_FROM_NUM_6   GPIOG

#define _GPIO_FROM_NUM(n)  _GPIO_FROM_NUM_##n
#define GPIO_FROM_NUM(n)   _GPIO_FROM_NUM(n)


void BL_MANGLE(init)(void *instance_data, uint32_t periodns) {
    BL_MANGLE(t) *self = (BL_MANGLE(t) *)instance_data;
    (void)periodns;  // delete this line if periodns is used

    self->base_addr = GPIO_FROM_NUM(PORT_NUM);
    // configure the hardware
    uint32_t moder = self->base_addr->MODER;  // get existing modes
    for ( int n = 0 ; n < 16 ; n++ ) {
        #if (INPUTS!=0)
            if ( pPIN00_IN_[n] != NULL ) {
                // hardware pin is GPIO input
                moder &= ~ (0x00000003 << (n*2));  // mask out mode bits
                uint32_t mode = 0;  // input mode
                moder |= mode << (n*2);  // merge new mode bits
            }
        #endif // (INPUTS!=0)
        #if (OUTPUTS!=0)
            if ( pPIN00_OUT_[n] != NULL ) {
                // hardware pin is GPIO output
                moder &= ~ (0x00000003 << (n*2));  // mask out mode bits
                uint32_t mode = 0;  // default mode - input
                #if (ENABLES!=0)
                    if ( pPIN00_OE_[n] == NULL ) {
                        // hardware pin is always output
                        mode = 0x01;  // output mode
                    } else {
                        // hardware pin has enable
                        if ( PIN00_OE_(n) ) {
                            // and is enabled now
                            mode = 0x01;  // output mode
                        }
                    }
                #else // (ENABLES==0)
                    // hardware pin is always output
                    mode = 0x01;  // output mode
                #endif // (ENABLES==0)
                moder |= mode << (n*2);  // merge new mode bits
            }
        #endif // (OUTPUTS!=0)
    }
    // set pin modes for entire port
    self->base_addr->MODER = moder;
}

#if ((INPUTS!=0))
void BL_MANGLE(read)(void *instance_data, uint32_t periodns) {
    BL_MANGLE(t) *self = (BL_MANGLE(t) *)instance_data;
    (void)periodns;  // delete this line if periodns is used

    uint32_t idr = self->base_addr->IDR;
    for ( int n = 0 ; n < 16 ; n++ ) {
        if ( pPIN00_IN_[n] != NULL ) {
            PIN00_IN_(n) = ( idr >> n ) & 1;
        }
    }
}
#endif // (INPUTS !=0)

#if ((OUTPUTS!=0))
void BL_MANGLE(write)(void *instance_data, uint32_t periodns) {
    BL_MANGLE(t) *self = (BL_MANGLE(t) *)instance_data;
    (void)periodns;  // delete this line if periodns is used

    uint32_t bsrr = 0;
    for ( int n = 0 ; n < 16 ; n++ ) {
        if ( pPIN00_OUT_[n] != NULL ) {
            if ( PIN00_OUT_(n) ) {
                bsrr |= 0x00000001 << n;
            } else {
                bsrr |= 0x00010000 << n;
            }
        }
    }
    #if (ENABLES!=0)
        uint32_t moder = self->base_addr->MODER;
        for ( int n = 0 ; n < 16 ; n++ ) {
            if ( pPIN00_OE_[n] != NULL ) {
                moder &= ~ (0x00000003 << (n*2));  // mask out mode bits
                uint32_t mode = 0;  // input mode
                if ( PIN00_OE_(n) ) {
                    mode = 0x01;  // output mode
                }
                moder |= mode << (n*2);  // merge new mode bits
            }
        }
        self->base_addr->MODER = moder;
    #endif  // (ENABLES!=0)
    self->base_addr->BSRR = bsrr;
}
#endif // (OUTPUTS!=0)
