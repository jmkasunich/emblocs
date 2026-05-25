// Generated once by the EMBLOCS block compiler.
// Edit freely - this file will not be overwritten.
// Source: integrator.bloc

#include "emblocs_comp.h"

#define BL_BLOCK_NAME integrator

// set default parameter values if not supplied
#ifndef HAS_ENABLE
#define HAS_ENABLE (0)
#endif
#ifndef HAS_HOLD
#define HAS_HOLD (0)
#endif

#include "integrator.h"

// EMBLOCS:  DO NOT REMOVE OR EDIT ABOVE THIS LINE

void BL_MANGLE(update)(void *instance_data, uint32_t periodns) {
    BL_MANGLE(t) *self = (BL_MANGLE(t) *)instance_data;

    #if (HAS_ENABLE)
    if ( ! ENABLE_ ) {
        self->accumulator = 0.0;
    } else {
        #endif  // HAS_ENABLE
        #if (HAS_HOLD)
        if ( ! HOLD_ ) {
            #endif // HAS_HOLD
            float dt = periodns * 0.000000001;
            self->accumulator += IN_ * dt;
            OUT_ = self->accumulator;
            #if (HAS_HOLD)
        }
        #endif // (HAS_HOLD)
        #if (HAS_ENABLE)
    }
    #endif // HAS ENABLE
}
