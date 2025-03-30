#include "emblocs_priv.h"
#include <string.h>         // strcmp
#include "printing.h"

#define halt()  do {} while (1)


/**************************************************************
 * These functions support building a system from arrays of
 * structs and/or strings in flash.
 */

bool bl_init_instances(bl_instance_def_t const instances[])
{
    bl_instance_def_t const *idp;  // instance definition pointer
    bl_instance_meta_t *inst;
    int errors = 0;

    idp = instances;
    while ( idp->name != NULL ) {
        inst = bl_instance_new(idp->name, idp->comp_def, idp->personality);
        #ifndef BL_ERROR_HALT
        if ( inst == NULL) {
            errors++;
        }
        #endif
        idp++;
    }
    #ifndef BL_ERROR_HALT
    if ( errors > 0  ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(2, "error(s) during ", "init_instances()\n");
        #endif
        return false;
    }
    #endif
    return true;
}

static int is_sig_type_str(char const *str, bl_type_t *result)
{
    if ( strcmp(str, "BIT") == 0 ) {
        *result = BL_TYPE_BIT;
        return 1;
    }
    if ( strcmp(str, "FLOAT") == 0 ) {
        *result = BL_TYPE_FLOAT;
        return 1;
    }
    if ( strcmp(str, "S32") == 0 ) {
        *result = BL_TYPE_S32;
        return 1;
    }
    if ( strcmp(str, "U32") == 0 ) {
        *result = BL_TYPE_U32;
        return 1;
    }
    return 0;
}

bool bl_init_nets(char const *const nets[])
{
    bool retval __attribute__ ((unused));
    bl_type_t net_type;
    bl_signal_meta_t *sig;
    bl_instance_meta_t *inst;
    bl_pin_meta_t *pin;
    enum {
        START,
        GET_SIG,
        GOT_SIG,
        GET_PIN
    } state;
    int errors = 0;

    state = START;
    while ( *nets != NULL ) {
        switch (state) {
        case START:
            if ( is_sig_type_str(*nets, &net_type) ) {
                state = GET_SIG;
            } else {
                #ifdef BL_ERROR_VERBOSE
                print_strings(3, "expected net type, not '", *nets, "'\n");
                #endif
                errors++;
                #ifdef BL_ERROR_HALT
                halt();
                #endif
            }
            break;
        case GET_SIG:
            sig = bl_signal_new(*nets, net_type);
            #ifndef BL_ERROR_HALT
            if ( sig == NULL ) {
                errors++;
                state = START;
                break;
            }
            #endif
            state = GOT_SIG;
            break;
        case GOT_SIG:
            if ( is_sig_type_str(*nets, &net_type) ) {
                // done with previous net, start a new one
                state = GET_SIG;
            } else {
                inst = bl_instance_find(*nets);
                #ifndef BL_ERROR_HALT
                if ( inst == NULL ) {
                    errors++;
                    state = START;
                    break;
                }
                #endif
                state = GET_PIN;
            }
            break;
        case GET_PIN:
            pin = bl_pin_find_in_instance(*nets, inst);
            #ifndef BL_ERROR_HALT
            if ( pin == NULL ) {
                errors++;
                state = GOT_SIG;
                break;
            }
            #endif
            retval = bl_pin_linkto_signal(pin, sig);
            #ifndef BL_ERROR_HALT
            if ( ! retval ) {
                errors++;
            }
            #endif
            state = GOT_SIG;
            break;
        default:
            halt();
        }
        nets++;
    }
    #ifndef BL_ERROR_HALT
    if ( errors > 0 ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(2, "error(s) during ", "init_nets()\n");
        #endif
        return false;
    }
    #endif
    return true;
}

bool bl_init_setsigs(bl_setsig_def_t const setsigs[])
{
    bl_setsig_def_t const *sdp;
    bool retval  __attribute__ ((unused));
    #ifndef BL_ERROR_HALT
    int errors = 0;
    #endif

    sdp = setsigs;
    while ( sdp->name != NULL ) {
        retval = bl_signal_set(bl_signal_find(sdp->name), &sdp->value);
        #ifndef BL_ERROR_HALT
        if ( ! retval ) {
            errors++;
        }
        #endif
        sdp++;
    }
    #ifndef BL_ERROR_HALT
    if ( errors > 0 ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(2, "error(s) during ", "init_setsigs()\n");
        #endif
        return false;
    }
    #endif
    return true;
}

bool bl_init_setpins(bl_setpin_def_t const setpins[])
{
    bl_setpin_def_t const *sdp;
    bl_instance_meta_t *inst;
    bl_pin_meta_t *pin;
    bool retval  __attribute__ ((unused));
    #ifndef BL_ERROR_HALT
    int errors = 0;
    #endif

    sdp = setpins;
    while ( sdp->instance_name != NULL ) {
        inst = bl_instance_find(sdp->instance_name);
        #ifndef BL_ERROR_HALT
        if ( inst ==NULL ) {
            errors++;
            goto next;
        }
        #endif
        pin = bl_pin_find_in_instance(sdp->pin_name, inst);
        #ifndef BL_ERROR_HALT
        if ( pin ==NULL ) {
            errors++;
            goto next;
        }
        #endif
        retval = bl_pin_set(pin, &sdp->value);
        #ifndef BL_ERROR_HALT
        if ( ! retval ) {
            errors++;
        }
        #endif
        next:
        sdp++;
    }
    #ifndef BL_ERROR_HALT
    if ( errors > 0 ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(2, "error(s) during ", "init_setsigs()\n");
        #endif
        return false;
    }
    #endif
    return true;
}

static int is_thread_type_str(char const *str, bl_nofp_t *result)
{
    if ( strcmp(str, "HAS_FP") == 0 ) {
        *result = BL_HAS_FP;
        return 1;
    }
    if ( strcmp(str, "NO_FP") == 0 ) {
        *result = BL_NO_FP;
        return 1;
    }
    return 0;
}

static int is_uint32_str(char const *str, uint32_t *result)
{
    uint32_t r = 0;

    do {
        if ( ( *str < '0' ) || ( *str > '9' )  ) {
            return 0;
        }
        r *= 10;
        r += *str - '0';
        str++;
    } while ( *str != '\0' );
    *result = r;
    return 1;
}

bool bl_init_threads(char const * const threads[])
{
    bool retval  __attribute__ ((unused));
    bl_nofp_t thread_type;
    uint32_t period_ns;
    bl_thread_meta_t *thread;
    bl_instance_meta_t *inst;
    bl_function_meta_t *function;
    int errors = 0;

    enum {
        START,
        GET_PERIOD,
        GET_NAME,
        GOT_NAME,
        GET_FUNCT
    } state;

    state = START;
    while ( *threads != NULL ) {
        switch (state) {
        case START:
            if ( is_thread_type_str(*threads, &thread_type) ) {
                state = GET_PERIOD;
            } else {
                #ifdef BL_ERROR_VERBOSE
                print_strings(3, "expected thread type, not '", *threads, "'\n");
                #endif
                errors++;
                #ifdef BL_ERROR_HALT
                halt();
                #endif
            }
            break;
        case GET_PERIOD:
            if ( ! is_uint32_str(*threads, &period_ns) ) {
                #ifdef BL_ERROR_VERBOSE
                print_strings(3, "expected thread period, not '", *threads, "'\n");
                #endif
                errors++;
                #ifdef BL_ERROR_HALT
                halt();
                #endif
                state = START;
                break;
            }
            state = GET_NAME;
            break;
        case GET_NAME:
            thread = bl_thread_new(*threads, period_ns, thread_type);
            #ifndef BL_ERROR_HALT
            if ( thread == NULL ) {
                errors++;
                state = START;
                break;
            }
            #endif
            state = GOT_NAME;
            break;
        case GOT_NAME:
            if ( is_thread_type_str(*threads, &thread_type) ) {
                // done with previous thread, start a new one
                state = GET_PERIOD;
            } else {
                inst = bl_instance_find(*threads);
                #ifndef BL_ERROR_HALT
                if ( inst == NULL ) {
                    errors++;
                    state = START;
                    break;
                }
                #endif
                state = GET_FUNCT;
            }
            break;
        case GET_FUNCT:
            function = bl_function_find_in_instance(*threads, inst);
            #ifndef BL_ERROR_HALT
            if ( function == NULL ) {
                errors++;
                state = GOT_NAME;
                break;
            }
            #endif
            retval = bl_function_linkto_thread(function, thread);
            #ifndef BL_ERROR_HALT
            if ( ! retval ) {
                errors++;
            }
            #endif
            state = GOT_NAME;
            break;
        default:
            halt();
        }
        threads++;
    }
    #ifndef BL_ERROR_HALT
    if ( errors > 0 ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(2, "error(s) during ", "init_threads()\n");
        #endif
        return false;
    }
    #endif
    return true;
}

