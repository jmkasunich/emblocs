#include "emblocs_priv.h"
#include <string.h>         // strcmp
#include "printing.h"
#include "linked_list.h"

#define abs(x)  ( (x) > 0 ? (x) : -(x) )
#define halt()  do {} while (1)

typedef enum {
    CMD_INSTANCE         = 1,
    CMD_SIGNAL           = 2,
    CMD_THREAD           = 3,
    CMD_LINK             = 4,
    CMD_UNLINK           = 5,
    CMD_SET              = 6,
    CMD_SHOW             = 7,
    CMD_LIST             = 8
} command_enum_t;

#define CMD_BITS (4)

typedef enum {
    OBJ_INSTANCE         = 1,
    OBJ_SIGNAL           = 2,
    OBJ_THREAD           = 3,
    OBJ_ALL              = 4
} objtype_enum_t;

#define OBJTYPE_BITS (3)


typedef struct keyword_s {
    char const *name;
    uint32_t is_cmd         : 1;
    uint32_t is_obj_type    : 1;
    uint32_t is_data_type   : 1;
    uint32_t is_thread_type : 1;
    uint32_t cmd            : CMD_BITS;
    uint32_t objtype        : OBJTYPE_BITS;
    uint32_t datatype       : BL_TYPE_BITS;
    uint32_t threadtype     : BL_NOFP_BITS;
} keyword_t;

static keyword_t const keywords[] = {
    { "instance",   1, 1, 0, 0, CMD_INSTANCE, OBJ_INSTANCE, 0, 0 },
    { "signal",     1, 1, 0, 0, CMD_SIGNAL, OBJ_SIGNAL, 0, 0 },
    { "thread",     1, 1, 0, 0, CMD_THREAD, OBJ_THREAD, 0, 0 },
    { "link",       1, 0, 0, 0, CMD_LINK, 0, 0, 0 },
    { "unlink",     1, 0, 0, 0, CMD_UNLINK, 0, 0, 0 },
    { "set",        1, 0, 0, 0, CMD_SET, 0, 0, 0 },
    { "show",       1, 0, 0, 0, CMD_SHOW, 0, 0, 0 },
    { "list",       1, 0, 0, 0, CMD_LIST, 0, 0, 0 },
    { "bit",        0, 0, 1, 0, 0, 0, BL_TYPE_BIT, 0 },
    { "float",      0, 0, 1, 0, 0, 0, BL_TYPE_FLOAT, 0 },
    { "s32",        0, 0, 1, 0, 0, 0, BL_TYPE_S32, 0 },
    { "u32",        0, 0, 1, 0, 0, 0, BL_TYPE_U32, 0 },
    { "nofp",       0, 0, 0, 1, 0, 0, 0, BL_NO_FP },
    { "fp",         0, 0, 0, 1, 0, 0, 0, BL_HAS_FP },
    { "all",        0, 1, 0, 0, 0, OBJ_ALL, 0, 0 }
};

#define MAX_TOKEN_LEN (100)

// this macro declares a function associated with state 'foo'
#define ST_FUNC(foo)    static bool st_ ## foo(char const *token)
// this macro returns the name of the function for state 'foo'
#define ST_NAME(foo)    st_ ## foo

// prototypes for all of the state-handling functions
// this is also a list of all the valid states
ST_FUNC(IDLE);
ST_FUNC(INST_START);
ST_FUNC(INST_1);
ST_FUNC(INST_2);
ST_FUNC(INST_DONE);
ST_FUNC(SIGNAL_START);
ST_FUNC(SIGNAL_1);
ST_FUNC(SIGNAL_2);
ST_FUNC(SIGNAL_3);
ST_FUNC(SIGNAL_DONE);
ST_FUNC(THREAD_START);
ST_FUNC(THREAD_1);
ST_FUNC(THREAD_2);
ST_FUNC(THREAD_3);
ST_FUNC(THREAD_4);
ST_FUNC(THREAD_DONE);
ST_FUNC(LINK_START);
ST_FUNC(LINK_1);
ST_FUNC(LINK_2);
ST_FUNC(LINK_3);
ST_FUNC(LINK_DONE);
ST_FUNC(UNLINK_START);
ST_FUNC(UNLINK_1);
ST_FUNC(UNLINK_DONE);
ST_FUNC(SET_START);
ST_FUNC(SET_1);
ST_FUNC(SET_2);
ST_FUNC(SET_DONE);
ST_FUNC(SHOW_START);
ST_FUNC(LIST_START);

static bool parse_token(char const *token);

static bool is_string(char const * token);
static keyword_t const *is_keyword(char const *token);
static bool is_name(char const * token);
static bool is_new_name(char const *token);
static bool process_done_state(char const *token, bool (*state_if_not_command)(char const *token));

static void print_token(char const * token);
static void print_expect_error(char const *expect, char const *token);

static bool str_to_bool(char const * str, bool *dest);
static bool str_to_s32(char const *str, int32_t *dest);
static bool str_to_u32(char const *str, uint32_t *dest);
static bool str_to_float(char const *str, float *dest);

/* we need to initialize 'state' but  
   don't care about the other fields */
#pragma GCC diagnostic ignored "-Wmissing-field-initializers"

/* internal parser data */
static struct parser_data {
    bool (*state)(char const *token);
    char const *new_name;
    bl_comp_def_t *comp_def;
    void *personality;
    bl_signal_meta_t *signal_meta;
    bl_instance_meta_t *instance_meta;
    bl_thread_meta_t *thread_meta;
    bl_pin_meta_t *pin_meta;
    bl_function_meta_t *funct_meta;
    bl_nofp_t thread_type;
    bl_sig_data_t *set_target;
    bl_type_t set_type;
} pd = {ST_NAME(IDLE)};

#pragma GCC diagnostic pop

/**************************************************************
 * These functions support parsing an array of tokens to build
 * or modify a system.
 */


bool bl_parse_array(char const * const tokens[], uint32_t count)
{
    uint32_t errors = 0;
    for ( uint32_t n = 0 ; n < count ; n++ ) {
        if ( ! parse_token(tokens[n]) ) {
            errors++;
        }
    }
    return ( errors == 0 );
}

static bool parse_token(char const *token)
{
    print_string("state: ");
    print_uint_hex((uint32_t )pd.state, 8, 0, 0);
    print_string(", token: ");
    print_token(token);
    print_string("\n");
    // call the state-specific token processing function
    return pd.state(token);
}

ST_FUNC(IDLE)
{
    keyword_t const *kw;

    kw = is_keyword(token);
    if ( ( kw == NULL ) || ( ! kw->is_cmd ) ) {
        print_expect_error("command", token);
        return false;
    }
    switch ( kw->cmd ) {
        case CMD_INSTANCE:
            pd.state = ST_NAME(INST_START);
            return true;
        case CMD_SIGNAL:
            pd.state = ST_NAME(SIGNAL_START);
            return true;
        case CMD_THREAD:
            pd.state = ST_NAME(THREAD_START);
            return true;
        case CMD_LINK:
            pd.state = ST_NAME(LINK_START);
            return true;
        case CMD_UNLINK:
            pd.state = ST_NAME(UNLINK_START);
            return true;
        case CMD_SET:
            pd.state = ST_NAME(SET_START);
            return true;
        case CMD_SHOW:
            pd.state = ST_NAME(SHOW_START);
            return true;
        case CMD_LIST:
            pd.state = ST_NAME(LIST_START);
            return true;
        default:
            print_strings(2, "ERROR: ", "bad switch\n");
            pd.state = ST_NAME(IDLE);
            return false;
    }
}

ST_FUNC(INST_START)
{
    if ( is_name(token) && is_new_name(token) ) {
        pd.new_name = token;
        pd.state = ST_NAME(INST_1);
        return true;
    }
    print_expect_error("new instance name", token);
    pd.state = ST_NAME(IDLE);
    return false;
}

ST_FUNC(INST_1)
{
    pd.comp_def = (bl_comp_def_t *)token;
    pd.state = ST_NAME(INST_2);
    return true;
}

ST_FUNC(INST_2)
{
    pd.personality = (void *)token;
    pd.instance_meta = bl_instance_new(pd.new_name, pd.comp_def, pd.personality);
    if ( pd.instance_meta != NULL ) {
        pd.state = ST_NAME(INST_DONE);
        return true;
    }
    print_strings(5, "ERROR: ", "could not create ", "instance '", pd.new_name, "'\n" );
    pd.state = ST_NAME(IDLE);
    return false;
}

ST_FUNC(INST_DONE)
{
    return process_done_state(token, ST_NAME(INST_START));
}

ST_FUNC(SIGNAL_START)
{
    if ( is_name(token) ) {
        pd.signal_meta = bl_signal_find(token);
        if ( pd.signal_meta ) {
            pd.state = ST_NAME(SIGNAL_2);
            return true;
        }
        if ( is_new_name(token) ) {
            pd.new_name = token;
            pd.state = ST_NAME(SIGNAL_1);
            return true;
        }
    }
    print_expect_error("new or existing signal name", token);
    pd.state = ST_NAME(IDLE);
    return false;
}

ST_FUNC(SIGNAL_1)
{
    keyword_t const *kw;

    if ( is_name(token) ) {
        pd.instance_meta = bl_instance_find(token);
        if ( pd.instance_meta ) {
            pd.state = ST_NAME(SIGNAL_3);
            return true;
        }
    } else {
        kw = is_keyword(token);
        if ( ( kw ) && ( kw->is_data_type ) ) {
            pd.signal_meta = bl_signal_new(pd.new_name, kw->datatype );
            if ( pd.signal_meta ) {
                pd.state = ST_NAME(SIGNAL_DONE);
                return true;
            }
            print_strings(5, "ERROR: ", "could not create ", "signal '", pd.new_name, "'\n" );
            pd.state = ST_NAME(IDLE);
            return false;
        }
    }
    print_expect_error("instance name or data type", token);
    pd.state = ST_NAME(IDLE);
    return false;
}

ST_FUNC(SIGNAL_2)
{
    if ( is_name(token) ) {
        pd.instance_meta = bl_instance_find(token);
        if ( pd.instance_meta ) {
            pd.state = ST_NAME(SIGNAL_3);
            return true;
        }
    }
    print_expect_error("instance name", token);
    pd.state = ST_NAME(IDLE);
    return false;
}

ST_FUNC(SIGNAL_3)
{
    if ( is_name(token) ) {
        pd.pin_meta = bl_pin_find_in_instance(token, pd.instance_meta);
        if ( pd.pin_meta ) {
            if ( ! pd.signal_meta ) {
                pd.signal_meta = bl_signal_new(pd.new_name, pd.pin_meta->data_type);
                if ( ! pd.signal_meta ) {
                    print_strings(5, "ERROR: ", "could not create ", "signal '", pd.new_name, "'\n" );
                    pd.state = ST_NAME(IDLE);
                    return false;
                }
            }
            if ( bl_pin_linkto_signal(pd.pin_meta, pd.signal_meta) ) {
                pd.state = ST_NAME(SIGNAL_DONE);
                return true;
            }
            print_strings(9, "ERROR: ", "could not link ", "pin '", pd.instance_meta->name, ".", pd.pin_meta->name, "' to signal '", pd.signal_meta->name, "'\n" );
            pd.state = ST_NAME(IDLE);
            return false;
        }
    }
    print_expect_error("pin name", token);
    pd.state = ST_NAME(IDLE);
    return false;
}

ST_FUNC(SIGNAL_DONE)
{
    // check innermost loop - another instance/pin pair
    if ( is_name(token) ) {
        pd.instance_meta = bl_instance_find(token);
        if ( pd.instance_meta ) {
            pd.state = ST_NAME(SIGNAL_3);
            return true;
        }
    }
    return process_done_state(token, ST_NAME(SIGNAL_START));
}

ST_FUNC(THREAD_START)
{
    if ( is_name(token) ) {
        pd.thread_meta = bl_thread_find(token);
        if ( pd.thread_meta ) {
            pd.state = ST_NAME(THREAD_3);
            return true;
        }
        if ( is_new_name(token) ) {
            pd.new_name = token;
            pd.state = ST_NAME(THREAD_1);
            return true;
        }
    }
    print_expect_error("new or existing thread name", token);
    pd.state = ST_NAME(IDLE);
    return false;
}

ST_FUNC(THREAD_1)
{
    keyword_t const *kw;

    kw = is_keyword(token);
    if ( ( kw ) && ( kw->is_thread_type ) ) {
        pd.thread_type = kw->threadtype;
        pd.state = ST_NAME(THREAD_2);
        return true;
    }
    print_expect_error("thread type", token);
    pd.state = ST_NAME(IDLE);
    return false;
}

ST_FUNC(THREAD_2)
{
    uint32_t thread_period;

    if ( str_to_u32(token, &thread_period) ) {
        pd.thread_meta = bl_thread_new(pd.new_name, thread_period, pd.thread_type);
        if ( pd.thread_meta ) {
            pd.state = ST_NAME(THREAD_DONE);
            return true;
        }
        print_strings(5, "ERROR: ", "could not create ", "thread '", pd.new_name, "'\n" );
        pd.state = ST_NAME(IDLE);
        return false;
    }
    print_expect_error("thread period", token);
    pd.state = ST_NAME(IDLE);
    return false;
}

ST_FUNC(THREAD_3)
{
    if ( is_name(token) ) {
        pd.instance_meta = bl_instance_find(token);
        if ( pd.instance_meta ) {
            pd.state = ST_NAME(THREAD_4);
            return true;
        }
    }
    print_expect_error("instance name", token);
    pd.state = ST_NAME(IDLE);
    return false;
}

ST_FUNC(THREAD_4)
{
    if ( is_name(token) ) {
        pd.funct_meta = bl_function_find_in_instance(token, pd.instance_meta);
        if ( pd.funct_meta ) {
            if ( bl_function_linkto_thread(pd.funct_meta, pd.thread_meta) ) {
                pd.state = ST_NAME(THREAD_DONE);
                return true;
            }
            print_strings(9, "ERROR: ", "could not link ", "function '", pd.instance_meta->name, ".", pd.funct_meta->name, "' to thread '", pd.thread_meta->name, "'\n" );
            pd.state = ST_NAME(IDLE);
            return false;
        }
    }
    print_expect_error("function name", token);
    pd.state = ST_NAME(IDLE);
    return false;
}

ST_FUNC(THREAD_DONE)
{
    // check innermost loop - another instance/function pair
    if ( is_name(token) ) {
        pd.instance_meta = bl_instance_find(token);
        if ( pd.instance_meta ) {
            pd.state = ST_NAME(THREAD_4);
            return true;
        }
    }
    return process_done_state(token, ST_NAME(THREAD_START));
}

ST_FUNC(LINK_START)
{
    if ( is_name(token) ) {
        pd.instance_meta = bl_instance_find(token);
        if ( pd.instance_meta ) {
            pd.state = ST_NAME(LINK_1);
            return true;
        }
    }
    print_expect_error("instance name", token);
    pd.state = ST_NAME(IDLE);
    return false;
}

ST_FUNC(LINK_1)
{
    // dummy code, avoids warning spam
    return (token == NULL);

}

ST_FUNC(LINK_2)
{
    // dummy code, avoids warning spam
    return (token == NULL);

}

ST_FUNC(LINK_3)
{
    // dummy code, avoids warning spam
    return (token == NULL);

}

ST_FUNC(LINK_DONE)
{
    return process_done_state(token, ST_NAME(LINK_START));
}

ST_FUNC(UNLINK_START)
{
    if ( is_name(token) ) {
        pd.instance_meta = bl_instance_find(token);
        if ( pd.instance_meta ) {
            pd.state = ST_NAME(UNLINK_1);
            return true;
        }
    }
    print_expect_error("instance name", token);
    pd.state = ST_NAME(IDLE);
    return false;
}

ST_FUNC(UNLINK_1)
{
    // dummy code, avoids warning spam
    return (token == NULL);

}

ST_FUNC(UNLINK_DONE)
{
    return process_done_state(token, ST_NAME(UNLINK_START));
}

ST_FUNC(SET_START)
{
    if ( is_name(token) ) {
        pd.signal_meta = bl_signal_find(token);
        if ( pd.signal_meta ) {
            pd.set_type = pd.signal_meta->data_type;
            pd.set_target = TO_RT_ADDR(pd.signal_meta->data_index);
            pd.state = ST_NAME(SET_2);
            return true;
        }
        pd.instance_meta = bl_instance_find(token);
        if ( pd.instance_meta ) {
            pd.state = ST_NAME(SET_1);
            return true;
        }
    }
    print_expect_error("signal or instance name", token);
    pd.state = ST_NAME(IDLE);
    return false;
}

#pragma GCC optimize ("no-strict-aliasing")
ST_FUNC(SET_1)
{
    if ( is_name(token) ) {
        pd.pin_meta = bl_pin_find_in_instance(token, pd.instance_meta);
        if ( pd.pin_meta ) {
            pd.set_type = pd.pin_meta->data_type;
            pd.set_target = *(bl_sig_data_t **)TO_RT_ADDR(pd.pin_meta->ptr_index);
            pd.state = ST_NAME(SET_2);
            return true;
        }
    }
    print_expect_error("pin name", token);
    pd.state = ST_NAME(IDLE);
    return false;
}
#pragma GCC reset_options

ST_FUNC(SET_2)
{
    switch ( pd.set_type ) {
        case BL_TYPE_BIT:
            if ( str_to_bool(token, &(pd.set_target->b)) ) {
                pd.state = ST_NAME(SET_DONE);
                return true;
            }
            print_expect_error("bit value", token);
            return false;
        case BL_TYPE_FLOAT:
            if ( str_to_float(token, &(pd.set_target->f)) ) {
                pd.state = ST_NAME(SET_DONE);
                return true;
            }
            print_expect_error("float value", token);
            return false;
        case BL_TYPE_S32:
            if ( str_to_s32(token, &(pd.set_target->s)) ) {
                pd.state = ST_NAME(SET_DONE);
                return true;
            }
            print_expect_error("s32 value", token);
            return false;
        case BL_TYPE_U32:
            if ( str_to_u32(token, &(pd.set_target->u)) ) {
                pd.state = ST_NAME(SET_DONE);
                return true;
            }
            print_expect_error("u32 value", token);
            return false;
        default:
            print_strings(2, "ERROR: ", "bad switch\n");
            pd.state = ST_NAME(IDLE);
            return false;
    }
}

ST_FUNC(SET_DONE)
{
    return process_done_state(token, ST_NAME(SET_START));
}

ST_FUNC(SHOW_START)
{
    // dummy code, avoids warning spam
    return (token == NULL);
    
}

ST_FUNC(LIST_START)
{
    // dummy code, avoids warning spam
    return (token == NULL);
    
}


/* a string must be 1 to MAX_TOKEN_LEN printable
 * characters terminated by '\0'
 */
static bool is_string(char const * token)
{
    if ( token == NULL ) {
        return false;
    }
    for ( int len = 0 ; len <= MAX_TOKEN_LEN ; len++ ) {
        char c = token[len];
        if ( c == '\0' ) {
            return ( len > 0 );
        }
        if ( c < 0x21 ) {
            // control characters or space
            return false;
        }
        if ( c > 0x7E ) {
            // extended chars, not supported
            return false;
        }
    }
    // too long
    return false;
}

static keyword_t const *is_keyword(char const *token)
{
    if ( token == NULL ) {
        return NULL;
    }
    // is it a keyword?
    for ( uint32_t n = 0 ; n < _countof(keywords) ; n++ ) {
        if ( strcmp(token, keywords[n].name) == 0 ) {
            return &keywords[n];
        }
    }
    return NULL;
}

static bool is_name(char const * token)
{
    char c;

    if ( ! is_string(token) || is_keyword(token) ) {
        return false;
    }
    c = token[0];
    if ( ( c != '_') &&
         ( ( c < 'a' ) || ( c > 'z' ) ) &&
         ( ( c < 'A' ) || ( c > 'Z' ) ) ) {
        return false;
    }
    for ( int n = 0 ; n < BL_MAX_NAME_LEN ; n++ ) {
        c = token[n];
        if ( c == '\0' ) {
            return true;
        }
        if ( ( c != '_') &&
            ( ( c < 'a' ) || ( c > 'z' ) ) &&
            ( ( c < 'A' ) || ( c > 'Z' ) ) &&
            ( ( c < '0' ) || ( c > '9' ) ) ) {
            return false;
        }
    }
    return false;
}

static bool is_new_name(char const *token)
{
    if ( ll_find((void **)(&(instance_root)), (void *)(token), bl_instance_meta_compare_name_key) ) {
        return false;
    }
    if ( ll_find((void **)(&(signal_root)), (void *)(token), bl_sig_meta_compare_name_key) ) {
        return false;
    }
    if ( ll_find((void **)(&(thread_root)), (void *)(token), bl_thread_meta_compare_name_key) ) {
        return false;
    }
    return true;
}

static bool process_done_state(char const *token, bool (*state_if_not_command)(char const *token))
{
    keyword_t const *kw;

    if ( (kw = is_keyword(token)) != NULL ) {
        if ( kw->is_cmd ) {
            pd.state = ST_NAME(IDLE);
            return parse_token(token);
        }
        print_expect_error("command", token);
        pd.state = ST_NAME(IDLE);
        return false;
    }
    pd.state = state_if_not_command;
    return parse_token(token);
}


static void print_token (char const * token)
{
    if ( is_string(token) ) {
        print_strings(3, "'", token, "'");
    } else if ( token == NULL ) {
        print_string("<NULL>");
    } else {
        print_string("<0x");
        print_uint_hex((uint32_t)token, 8, 0, 0);
        print_string(">");
    }
}

static void print_expect_error(char const *expect, char const *token)
{
    print_strings(4, "ERROR: ", "expected ", expect, ", found ");
    print_token(token);
    print_string("\n");
}


static bool str_to_bool(char const * str, bool *dest)
{
    if ( ( str == NULL )  ||
         ( str[0] < '0' ) || ( str[0] > '1' ) ||
         ( str[1] != '\0' ) ) {
        return false;
    }
    if ( dest != NULL ) {
        *dest = str[0] - '0';
    }
    return true;
}

static bool str_to_u32(char const *str, uint32_t *dest)
{
    uint32_t limit;

    uint32_t result = 0;
    char c = *(str++);
    do {
        if ( ( c < '0' ) || ( c > '9' ) ) {
            return false;
        }
        // largest number that can be multiplied by 10 and not overflow
        limit = 429496729;
        if ( c > '5' ) {
            // can't let the subsequent add overflow either
            limit--;
        }
        if ( result > limit ) {
            // adding this digit would overflow; too many digits in string
            return false;
        }
        // add this digit
        result *= 10;
        result += c - '0';
        // next digit
        c = *(str++);
    } while ( c != '\0' );
    if ( dest != NULL ) {
        *dest = result;
    }
    return true;
}

static bool str_to_s32(char const *str, int32_t *dest)
{
    bool is_neg = 0;
    if ( *str == '-' ) {
        is_neg = 1;
        str++;
    } else if ( *str == '+' ) {
        str++;
    }
    uint32_t utmp;
    if ( ! str_to_u32(str, &utmp) ) {
        return false;
    }
    int32_t result = 0;
    if ( is_neg ) {
        if ( utmp > 0x80000000 ) {
            return false;
        } else {
            result = -utmp;
        }
    } else {
        if ( utmp > 0x7FFFFFFF ) {
            return false;
        } else {
            result = utmp;
        }
    }
    if ( dest != NULL ) {
        *dest = result;
    }
    return true;
}

#pragma GCC optimize ("no-strict-aliasing")
static bool str_to_float(char const *str, float *dest)
{
    bool is_neg = 0;
    char c = *str;
    if ( c == '-' ) {
        is_neg = 1;
        str++;
    } else if ( c == '+' ) {
        str++;
    }
    c = *(str++);
    uint32_t uval = 0;
    int shift = 0;
    bool dp_found = 0;
    do {
        if ( ( c < '0' ) || ( c > '9' ) ) {
            if ( ( c == '.' ) && ( ! dp_found ) ) {
                dp_found = 1;
                c = *(str++);
                continue;
            }
            return false;
        }
        if ( uval > 429496728 ) {
            // adding this digit could overflow
            if ( ! dp_found ) {
                shift++;
            }
        } else {
            // add this digit
            uval *= 10;
            uval += c - '0';
            if ( dp_found ) {
                shift--;
            }
        }
        // next digit
        c = *(str++);
    } while ( ( c != '\0' ) && ( c != 'e' ) && ( c != 'E' ) );
    if ( c != '\0' ) {
        int32_t exponent;
        if ( ! str_to_s32(str, &exponent) ) {
            return false;
        }
        shift += exponent;
    }
    uint32_t shift_abs = abs(shift);
    if ( shift_abs > 60 ) {
        return false;
    }
    // compute the power of 10 for shift
    double tmp = 10;
    double pow = 1;
    while ( shift_abs ) {
        if ( shift_abs & 1 ) {
            pow *= tmp;
        }
        tmp *= tmp;
        shift_abs >>= 1;
    }
    // perform the shift
    double dresult = uval;
    if ( shift < 0 ) {
        dresult /= pow;
    } else {
        dresult *= pow;
    }
    float result = (float)dresult;
    // if double value was too high, float value
    //   becomes +infinity = 0x7F800000
    if ( *(uint32_t *)(&result) == 0x7F800000 ) {
        return false;
    }
    if ( is_neg ) {
        result = -result;
    }
    if ( dest != NULL ) {
        *dest = result;
    }
    return true;
}
#pragma GCC reset_options

