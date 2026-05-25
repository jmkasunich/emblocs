// Generated once by the EMBLOCS block compiler.
// Edit freely - this file will not be overwritten.
// Source: not.bloc

#include "emblocs_comp.h"

#define BL_BLOCK_NAME not

#include "not.h"

// EMBLOCS:  DO NOT REMOVE OR EDIT ABOVE THIS LINE

void BL_MANGLE(update)(void *instance_data, uint32_t periodns) {
    BL_MANGLE(t) *self = (BL_MANGLE(t) *)instance_data;
    (void)periodns;  // delete this line if periodns is used

    OUT_ = ! IN_;
}
