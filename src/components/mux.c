// Generated once by the EMBLOCS block compiler.
// Edit freely - this file will not be overwritten.
// Source: mux.bloc

#include "mux.h"

// EMBLOCS:  DO NOT REMOVE OR EDIT ABOVE THIS LINE

void BL_MANGLE(update)(void *instance_data, uint32_t periodns) {
    BL_MANGLE(t) *self = (BL_MANGLE(t) *)instance_data;
    (void)periodns;  // delete this line if periodns is used

    #if (NUM_CHAN==1)
        OUT_ = IN0_(SELECT_);
    #endif
    #if (NUM_CHAN>1)
        int s = SELECT_;
        for ( int n = 0 ; n < NUM_CHAN ; n++ ) {
            CH00_OUT_(n) = CH00_IN0_(s, n);
        }
    #endif
}
