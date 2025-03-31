#include "emblocs_priv.h"
#include <string.h>         // strcmp
#include "printing.h"
#include "linked_list.h"

#define abs(x)  ( (x) > 0 ? (x) : -(x) )
#define halt()  do {} while (1)

typedef enum {
    KW_CMD_INSTANCE         = 1,
    KW_CMD_SIGNAL           = 2,
    KW_CMD_THREAD           = 3,
    KW_CMD_LINK             = 4,
    KW_CMD_UNLINK           = 5,
    KW_CMD_SET              = 6,
    KW_CMD_SHOW             = 7,
    KW_CMD_LIST             = 8
} keyword_command_enum_t;

#define KEYWORD_CMD_BITS (4)

typedef enum {
    KW_OBJ_INSTANCE         = 1,
    KW_OBJ_SIGNAL           = 2,
    KW_OBJ_THREAD           = 3,
    KW_OBJ_ALL              = 4
} keyword_objtype_enum_t;

#define KEYWORD_OBJTYPE_BITS (3)


typedef struct keyword_s {
    char const *name;
    uint32_t is_cmd         : 1;
    uint32_t is_obj_type    : 1;
    uint32_t is_data_type   : 1;
    uint32_t is_thread_type : 1;
    uint32_t cmd            : KEYWORD_CMD_BITS;
    uint32_t objtype        : KEYWORD_OBJTYPE_BITS;
    uint32_t datatype       : BL_TYPE_BITS;
    uint32_t threadtype     : BL_NOFP_BITS;
} keyword_t;

static keyword_t const keywords[] = {
    { "instance",   1, 1, 0, 0, KW_CMD_INSTANCE, KW_OBJ_INSTANCE, 0, 0 },
    { "signal",     1, 1, 0, 0, KW_CMD_SIGNAL, KW_OBJ_SIGNAL, 0, 0 },
    { "thread",     1, 1, 0, 0, KW_CMD_THREAD, KW_OBJ_THREAD, 0, 0 },
    { "link",       1, 0, 0, 0, KW_CMD_LINK, 0, 0, 0 },
    { "unlink",     1, 0, 0, 0, KW_CMD_UNLINK, 0, 0, 0 },
    { "set",        1, 0, 0, 0, KW_CMD_SET, 0, 0, 0 },
    { "show",       1, 0, 0, 0, KW_CMD_SHOW, 0, 0, 0 },
    { "list",       1, 0, 0, 0, KW_CMD_LIST, 0, 0, 0 },
    { "bit",        0, 0, 1, 0, 0, 0, BL_TYPE_BIT, 0 },
    { "float",      0, 0, 1, 0, 0, 0, BL_TYPE_FLOAT, 0 },
    { "s32",        0, 0, 1, 0, 0, 0, BL_TYPE_S32, 0 },
    { "u32",        0, 0, 1, 0, 0, 0, BL_TYPE_U32, 0 },
    { "nofp",       0, 0, 0, 1, 0, 0, 0, BL_NO_FP },
    { "fp",         0, 0, 0, 1, 0, 0, 0, BL_HAS_FP },
    { "all",        0, 1, 0, 0, 0, KW_OBJ_ALL, 0, 0 }
};

#define MAX_TOKEN_LEN (100)

typedef enum {
    IDLE            = 0x00,
    INST_START      = 0x10,
    INST_1          = 0x11,
    INST_2          = 0x12,
    INST_DONE       = 0x1F,
    SIGNAL_START    = 0x20,
    SIGNAL_1        = 0x21,
    SIGNAL_2        = 0x22,
    SIGNAL_3        = 0x23,
    SIGNAL_DONE     = 0x2F,
    THREAD_START    = 0x30,
    THREAD_1        = 0x31,
    THREAD_2        = 0x32,
    THREAD_3        = 0x33,
    THREAD_4        = 0x34,
    THREAD_DONE     = 0x3F,
    LINK_START      = 0x40,
    LINK_1          = 0x41,
    LINK_2          = 0x42,
    LINK_3          = 0x43,
    LINK_DONE       = 0x4F,
    UNLINK_START    = 0x50,
    UNLINK_1        = 0x51,
    UNLINK_DONE     = 0x5F,
    SET_START       = 0x60,
    SET_1           = 0x61,
    SET_2           = 0x62,
    SET_3           = 0x63,
    SET_DONE        = 0x64,
    SHOW_START      = 0x70,
    LIST_START      = 0x80
} parser_state_t;

#define STATE_CMD_MASK      (0xF0)
#define STATE_STEP_MASK     (0x0F)

static bool parse_token(char const *token);

static bool parse_instance_cmd(char const *token);
static bool parse_signal_cmd(char const *token);
static bool parse_thread_cmd(char const *token);
static bool parse_link_cmd(char const *token);
static bool parse_unlink_cmd(char const *token);
static bool parse_set_cmd(char const *token);
static bool parse_show_cmd(char const *token);
static bool parse_list_cmd(char const *token);

static bool is_string(char const * token);
static keyword_t *is_keyword(char const *token);
static bool is_name(char const * token);
static bool is_new_name(char const *token);
static bool process_done_state(char const *token, parser_state_t state_if_not_command);

static void print_token(char const * token);
static void print_expect_error(char const *expect, char const *token);

static bool str_to_bool(char const * str, bool *dest);
static bool str_to_s32(char const *str, int32_t *dest);
static bool str_to_u32(char const *str, uint32_t *dest);
static bool str_to_float(char const *str, float *dest);


/* internal parser data */
static parser_state_t state = IDLE;
static char const *new_name;
static bl_comp_def_t *comp_def;
static void *personality;
static bl_signal_meta_t *signal_meta;
static bl_instance_meta_t *instance_meta;
static bl_thread_meta_t *thread_meta;
static bl_pin_meta_t *pin_meta;
static bl_function_meta_t *funct_meta;
static bl_nofp_t thread_type;
static uint32_t thread_period;

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
    bool retval = false;
    keyword_t *kw;

    print_string("state: ");
    print_uint_hex(state, 2, 0, 0);
    print_string(", token: ");
    print_token(token);
    print_string("\n");
    switch ( state & STATE_CMD_MASK ) {
        case IDLE:
            kw = is_keyword(token);
            if ( ( kw == NULL ) || ( ! kw->is_cmd ) ) {
                print_expect_error("command", token);
                return false;
            }
            switch ( kw->cmd ) {
                case KW_CMD_INSTANCE:
                    state = INST_START;
                    retval = true;
                    break;
                case KW_CMD_SIGNAL:
                    state = SIGNAL_START;
                    retval = true;
                    break;
                case KW_CMD_THREAD:
                    state = THREAD_START;
                    retval = true;
                    break;
                case KW_CMD_LINK:
                    state = LINK_START;
                    retval = true;
                    break;
                case KW_CMD_UNLINK:
                    state = UNLINK_START;
                    retval = true;
                    break;
                case KW_CMD_SET:
                    state = SET_START;
                    retval = true;
                    break;
                case KW_CMD_SHOW:
                    state = SHOW_START;
                    retval = true;
                    break;
                case KW_CMD_LIST:
                    state = LIST_START;
                    retval = true;
                    break;
                default:
                    print_strings(2, "ERROR: ", "bad switch\n");
                    retval = false;
                    break;
            }
            break;
        case INST_START:
            retval = parse_instance_cmd(token);
            break;
        case SIGNAL_START:
            retval = parse_signal_cmd(token);
            break;
        case THREAD_START:
            retval = parse_thread_cmd(token);
            break;
        case LINK_START:
            retval = parse_link_cmd(token);
            break;
        case UNLINK_START:
            retval = parse_unlink_cmd(token);
            break;
        case SET_START:
            retval = parse_set_cmd(token);
            break;
        case SHOW_START:
            retval = parse_show_cmd(token);
            break;
        case LIST_START:
            retval = parse_list_cmd(token);
            break;
        default:
            retval = false;
            break;
    }
    return retval;
}

static bool parse_instance_cmd(char const *token)
{
    bool retval = false;

    switch ( state ) {
        case INST_START:
            if ( is_name(token) && is_new_name(token) ) {
                new_name = token;
                state = INST_1;
                retval = true;
                break;
            }
            print_expect_error("new instance name", token);
            state = IDLE;
            break;
        case INST_1:
            comp_def = (bl_comp_def_t *)token;
            state = INST_2;
            retval = true;
            break;
        case INST_2:
            personality = (void *)token;
            instance_meta = bl_instance_new(new_name, comp_def, personality);
            if ( instance_meta != NULL ) {
                state = INST_DONE;
                retval = true;
                break;
            }
            print_strings(5, "ERROR: ", "could not create ", "instance '", new_name, "'\n" );
            state = IDLE;
            break;
        case INST_DONE:
            retval = process_done_state(token, INST_START);
            break;
        default:
            print_strings(2, "ERROR: ", "bad switch\n");
            retval = false;
    }
    return retval;
}

static bool parse_signal_cmd(char const *token)
{
    bool retval = false;
    keyword_t *kw;

    switch ( state ) {
        case SIGNAL_START:
            if ( is_name(token) ) {
                signal_meta = bl_signal_find(token);
                if ( signal_meta ) {
                    state = SIGNAL_2;
                    retval = true;
                    break;
                }
                if ( is_new_name(token) ) {
                    new_name = token;
                    state = SIGNAL_1;
                    retval = true;
                    break;
                }
            }
            print_expect_error("new or existing signal name", token);
            state = IDLE;
            break;
        case SIGNAL_1:
            if ( is_name(token) ) {
                instance_meta = bl_instance_find(token);
                if ( instance_meta ) {
                    state = SIGNAL_3;
                    retval = true;
                    break;
                }
            } else {
                kw = is_keyword(token);
                if ( ( kw ) && ( kw->is_data_type ) ) {
                    signal_meta = bl_signal_new(new_name, kw->datatype );
                    if ( signal_meta ) {
                        state = SIGNAL_DONE;
                        retval = true;
                        break;
                    }
                    print_strings(5, "ERROR: ", "could not create ", "signal '", new_name, "'\n" );
                    state = IDLE;
                    break;
                }
            }
            print_expect_error("instance name or data type", token);
            state = IDLE;
            break;
        case SIGNAL_2:
            if ( is_name(token) ) {
                instance_meta = bl_instance_find(token);
                if ( instance_meta ) {
                    state = SIGNAL_3;
                    retval = true;
                    break;
                }
            }
            print_expect_error("instance name", token);
            state = IDLE;
            break;
        case SIGNAL_3:
            if ( is_name(token) ) {
                pin_meta = bl_pin_find_in_instance(token, instance_meta);
                if ( pin_meta ) {
                    if ( ! signal_meta ) {
                        signal_meta = bl_signal_new(new_name, pin_meta->data_type);
                        if ( ! signal_meta ) {
                            print_strings(5, "ERROR: ", "could not create ", "signal '", new_name, "'\n" );
                            state = IDLE;
                            break;
                        }
                    }
                    retval = bl_pin_linkto_signal(pin_meta, signal_meta);
                    if ( retval ) {
                        state = SIGNAL_DONE;
                        retval = true;
                        break;
                    }
                    print_strings(9, "ERROR: ", "could not link ", "pin '", instance_meta->name, ".", pin_meta->name, "' to signal '", signal_meta->name, "'\n" );
                    state = IDLE;
                    break;
                }
            }
            print_expect_error("pin name", token);
            state = IDLE;
            break;
        case SIGNAL_DONE:
            // check innermost loop - another instance/pin pair
            if ( is_name(token) ) {
                instance_meta = bl_instance_find(token);
                if ( instance_meta ) {
                    state = SIGNAL_3;
                    retval = true;
                    break;
                }
            }
            retval = process_done_state(token, SIGNAL_START);
            break;
        default:
            print_strings(2, "ERROR: ", "bad switch\n");
            break;
    }
    return retval;
}

static bool parse_thread_cmd(char const *token)
{
    bool retval = false;
    keyword_t *kw;

    switch ( state ) {
        case THREAD_START:
            if ( is_name(token) ) {
                thread_meta = bl_thread_find(token);
                if ( thread_meta ) {
                    state = THREAD_3;
                    retval = true;
                    break;
                }
                if ( is_new_name(token) ) {
                    new_name = token;
                    state = THREAD_1;
                    retval = true;
                    break;
                }
            }
            print_expect_error("new or existing thread name", token);
            state = IDLE;
            break;
        case THREAD_1:
            kw = is_keyword(token);
            if ( ( kw ) && ( kw->is_thread_type ) ) {
                thread_type = kw->threadtype;
                state = THREAD_2;
                retval = true;
                break;
            }
            print_expect_error("thread type", token);
            state = IDLE;
            break;
        case THREAD_2:
            if ( str_to_u32(token, &thread_period) ) {
                thread_meta = bl_thread_new(new_name, thread_period, thread_type);
                if ( thread_meta ) {
                    state = THREAD_DONE;
                    retval = true;
                    break;
                }
                print_strings(5, "ERROR: ", "could not create ", "thread '", new_name, "'\n" );
                state = IDLE;
                break;
            }
            print_expect_error("thread period", token);
            state = IDLE;
            break;
        case THREAD_3:
            if ( is_name(token) ) {
                instance_meta = bl_instance_find(token);
                if ( instance_meta ) {
                    state = THREAD_4;
                    retval = true;
                    break;
                }
            }
            print_expect_error("instance name", token);
            state = IDLE;
            break;
        case THREAD_4:
            if ( is_name(token) ) {
                funct_meta = bl_function_find_in_instance(token, instance_meta);
                if ( funct_meta ) {
                    retval = bl_function_linkto_thread(funct_meta, thread_meta);
                    if ( retval ) {
                        state = THREAD_DONE;
                        retval = true;
                        break;
                    } else {
                        print_strings(9, "ERROR: ", "could not link ", "function '", instance_meta->name, ".", funct_meta->name, "' to thread '", thread_meta->name, "'\n" );
                        state = IDLE;
                        break;
                    }
                }
            }
            print_expect_error("function name", token);
            state = IDLE;
            break;
        case THREAD_DONE:
            // check innermost loop - another instance/function pair
            if ( is_name(token) ) {
                instance_meta = bl_instance_find(token);
                if ( instance_meta ) {
                    state = THREAD_4;
                    retval = true;
                    break;
                }
            }
            retval = process_done_state(token, THREAD_START);
            break;
        default:
            print_strings(2, "ERROR: ", "bad switch\n");
            break;
    }
    return retval;
}

static bool parse_link_cmd(char const *token)
{

    return false;
}

static bool parse_unlink_cmd(char const *token)
{

    return false;
}

static bool parse_set_cmd(char const *token)
{

    return false;
}

static bool parse_show_cmd(char const *token)
{

    return false;
}

static bool parse_list_cmd(char const *token)
{

    return false;
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

static keyword_t *is_keyword(char const *token)
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

static bool process_done_state(char const *token, parser_state_t state_if_not_command)
{
    keyword_t *kw;

    if ( (kw = is_keyword(token)) != NULL ) {
        if ( kw->is_cmd ) {
            state = IDLE;
            return parse_token(token);
        } else {
            print_expect_error("command", token);
            state = IDLE;
            return false;
        }
    } else {
        state = state_if_not_command;
        return parse_token(token);
    }
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

