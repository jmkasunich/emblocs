// Generated once by the EMBLOCS block compiler.
// Edit freely - this file will not be overwritten.
// Source: limit1.bloc

#include "emblocs_comp.h"

#define BL_BLOCK_NAME limit1

#include "limit1.h"

// EMBLOCS:  DO NOT REMOVE OR EDIT ABOVE THIS LINE

void BL_MANGLE(update)(void *instance_data, uint32_t periodns) {
    BL_MANGLE(t) *self = (BL_MANGLE(t) *)instance_data;
    (void)periodns;  // delete this line if periodns is used

    float val = IN_;
    if ( val < MIN_) {
        val = MIN_;
    }
    if ( val > MAX_ ) {
        val = MAX_;
    }
    OUT_ = val;
}
