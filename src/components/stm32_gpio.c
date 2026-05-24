// Generated once by the EMBLOCS block compiler.
// Edit freely - this file will not be overwritten.
// Source: stm32_gpio.bloc

#include "emblocs_comp.h"

#define BL_BLOCK_NAME stm32_gpio

// set default parameter values if not supplied
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

#if ((INPUTS!=0))
void BL_MANGLE(read)(void *instance_data, uint32_t periodns) {
    BL_MANGLE(t) *self = (BL_MANGLE(t) *)instance_data;
    (void)periodns;  // delete this line if periodns is used

    uint32_t idr = self->base_addr.IDR;
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
    uint32_t oer = self->base_addr.OER;
    for ( int n = 0 ; n < 16 ; n++ ) {
        if ( pPIN00_OE_[n] != NULL ) {
            if ( PIN00_OE_(n) ) {
                oer |= 1 << n;
            } else {
                oer &= ~(1 << n);
            }
        }
    }
    self->base_addr.OER = oer;
    #endif  // (ENABLES!=0)
    self->base_addr.BSRR = bsrr;
}
#endif // (OUTPUTS!=0)
