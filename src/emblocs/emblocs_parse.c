#include "emblocs_priv.h"
#include <string.h>         // strcmp
#include <stdarg.h>
#include "printing.h"
#include "linked_list.h"
#include "str_to_xx.h"

/* These enums and the subsequent table define
 * the keywords (aka reserved words) for the
 * emblocs language.
 */

typedef enum {
    CMD_INSTANCE = 1,
    CMD_SIGNAL,
    CMD_THREAD,
    CMD_LINK,
#ifdef BL_ENABLE_UNLINK
    CMD_UNLINK,
#endif
    CMD_SET,
    CMD_SHOW,
} command_enum_t;

#define CMD_BITS (4)  // bits needed to store a command_enum_t

typedef enum {
    OBJ_INSTANCE = 1,
    OBJ_SIGNAL,
    OBJ_THREAD,
    OBJ_ALL
} objtype_enum_t;

#define OBJTYPE_BITS (3)  // bits needed to store a objtype_enum_t

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
#ifdef BL_ENABLE_UNLINK
    { "unlink",     1, 0, 0, 0, CMD_UNLINK, 0, 0, 0 },
#endif
    { "set",        1, 0, 0, 0, CMD_SET, 0, 0, 0 },
    { "show",       1, 0, 0, 0, CMD_SHOW, 0, 0, 0 },
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
#define ST_FUNC(foo)    static bool st_ ## foo(char const * const token)
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
#ifdef BL_ENABLE_UNLINK
ST_FUNC(UNLINK_START);
ST_FUNC(UNLINK_1);
ST_FUNC(UNLINK_DONE);
#endif
ST_FUNC(SET_START);
ST_FUNC(SET_1);
ST_FUNC(SET_2);
ST_FUNC(SET_DONE);
ST_FUNC(SHOW_START);

/* Error handling macros:
 * Each of these macros can be invoked by the
 * token parsing state machine.  They set the
 * state machine back to the 'IDLE' state and
 * return false.  If BL_PRINT_ERRORS is defined
 * they also print an error message; each
 * macro provides a different message format.
 */
#ifdef BL_PRINT_ERRORS
static void error_internal(void);
#define ERROR_INTERNAL()                do { error_internal(); return false; } while (0)
static void error_expect(char const *expect, char const *token);
#define ERROR_EXPECT(expect, token)     do { error_expect(expect, token); return false; } while (0)
static void error_api(int num_strings, ...);
#define ERROR_API(num, ...)             do { error_api(num, __VA_ARGS__); return false; } while (0)
#else
#define ERROR_INTERNAL()                do { pd.state = ST_NAME(IDLE); return false; } while (0)
#define ERROR_EXPECT(expect, token)     do { pd.state = ST_NAME(IDLE); return false; } while (0)
#define ERROR_API(num, ...)             do { pd.state = ST_NAME(IDLE); return false; } while (0)
#endif

static bool process_done_state(char const *token, bool (*state_if_not_command)(char const *token));

static bool is_string(char const * token);
static keyword_t const *is_keyword(char const *token);
static bool is_name(char const * token);
static bool is_new_name(char const *token);

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

    CHECK_NULL(tokens);
    for ( uint32_t n = 0 ; n < count ; n++ ) {
        printf("%s\n", tokens[n]);
        if ( ! bl_parse_token(tokens[n]) ) {
            errors++;
        }
    }
    return ( errors == 0 );
}

bool bl_parse_token(char const * const token)
{
    // call the state-specific token processing function
    return pd.state(token);
}

ST_FUNC(IDLE)
{
    keyword_t const *kw;

    kw = is_keyword(token);
    if ( ( kw == NULL ) || ( ! kw->is_cmd ) ) {
        ERROR_EXPECT("command", token);
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
#ifdef BL_ENABLE_UNLINK
        case CMD_UNLINK:
            pd.state = ST_NAME(UNLINK_START);
            return true;
#endif
        case CMD_SET:
            pd.state = ST_NAME(SET_START);
            return true;
        case CMD_SHOW:
            pd.state = ST_NAME(SHOW_START);
            return true;
        default:
            ERROR_INTERNAL();
    }
}

ST_FUNC(INST_START)
{
    if ( is_name(token) && is_new_name(token) ) {
        pd.new_name = token;
        pd.state = ST_NAME(INST_1);
        return true;
    }
    ERROR_EXPECT("new instance name", token);
}

ST_FUNC(INST_1)
{
    if ( is_name(token) ) {
        int n = 0;
        // search comp_defs[] for a match
        while ( (pd.comp_def = bl_comp_defs[n]) != NULL ) {
            if ( strcmp(token, pd.comp_def->name) == 0 ) {
                if ( pd.comp_def->needs_pers == BL_NEEDS_PERSONALITY ) {
                    pd.state = ST_NAME(INST_2);
                    return true;
                }
                pd.instance_meta = bl_instance_new(pd.new_name, pd.comp_def, NULL);
                if ( pd.instance_meta != NULL ) {
                    pd.state = ST_NAME(INST_DONE);
                    return true;
                }
                ERROR_API(4, "creating ", "instance '", pd.new_name, "'" );
            }
            n++;
        }
    }
    ERROR_EXPECT("component definition name", token);
}

ST_FUNC(INST_2)
{
    pd.personality = (void *)token;
    pd.instance_meta = bl_instance_new(pd.new_name, pd.comp_def, pd.personality);
    if ( pd.instance_meta != NULL ) {
        pd.state = ST_NAME(INST_DONE);
        return true;
    }
    ERROR_API(4, "creating ", "instance '", pd.new_name, "'" );
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
    ERROR_EXPECT("new or existing signal name", token);
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
            ERROR_API(4, "creating ", "signal '", pd.new_name, "'" );
        }
    }
    ERROR_EXPECT("instance name or data type", token);
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
    ERROR_EXPECT("instance name", token);
}

ST_FUNC(SIGNAL_3)
{
    if ( is_name(token) ) {
        pd.pin_meta = bl_pin_find_in_instance(token, pd.instance_meta);
        if ( pd.pin_meta ) {
            if ( ! pd.signal_meta ) {
                pd.signal_meta = bl_signal_new(pd.new_name, pd.pin_meta->data_type);
                if ( ! pd.signal_meta ) {
                    ERROR_API(4, "creating ", "signal '", pd.new_name, "'" );
                }
            }
            if ( bl_pin_linkto_signal(pd.pin_meta, pd.signal_meta) ) {
                pd.state = ST_NAME(SIGNAL_DONE);
                return true;
            }
            ERROR_API(8, "linking ", "pin '", pd.instance_meta->name, ".", pd.pin_meta->name, "' to signal '", pd.signal_meta->name, "'" );
        }
    }
    ERROR_EXPECT("pin name", token);
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
    ERROR_EXPECT("new or existing thread name", token);
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
    ERROR_EXPECT("thread type", token);
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
        ERROR_API(4, "creating ", "thread '", pd.new_name, "'" );
    }
    ERROR_EXPECT("thread period", token);
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
    ERROR_EXPECT("instance name", token);
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
            ERROR_API(8, "linking ", "function '", pd.instance_meta->name, ".", pd.funct_meta->name, "' to thread '", pd.thread_meta->name, "'" );
        }
    }
    ERROR_EXPECT("function name", token);
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
    ERROR_EXPECT("instance name", token);
}

ST_FUNC(LINK_1)
{
    if ( is_name(token) ) {
        pd.pin_meta = bl_pin_find_in_instance(token, pd.instance_meta);
        if ( pd.pin_meta ) {
            pd.state = ST_NAME(LINK_2);
            return true;
        }
        pd.funct_meta = bl_function_find_in_instance(token, pd.instance_meta);
        if ( pd.funct_meta ) {
            pd.state = ST_NAME(LINK_3);
            return true;
        }
    }
    ERROR_EXPECT("pin or function name", token);
}

ST_FUNC(LINK_2)
{
    if ( is_name(token) ) {
        pd.signal_meta = bl_signal_find(token);
        if ( pd.signal_meta ) {
            if ( bl_pin_linkto_signal(pd.pin_meta, pd.signal_meta) ) {
                pd.state = ST_NAME(LINK_DONE);
                return true;
            }
            ERROR_API(8, "linking ", "pin '", pd.instance_meta->name, ".", pd.pin_meta->name, "' to signal '", pd.signal_meta->name, "'" );
        }
    }
    ERROR_EXPECT("signal name", token);
}

ST_FUNC(LINK_3)
{
    if ( is_name(token) ) {
        pd.thread_meta = bl_thread_find(token);
        if ( pd.thread_meta ) {
            if ( bl_function_linkto_thread(pd.funct_meta, pd.thread_meta) ) {
                pd.state = ST_NAME(LINK_DONE);
                return true;
            }
            ERROR_API(8, "linking ", "function '", pd.instance_meta->name, ".", pd.funct_meta->name, "' to thread '", pd.thread_meta->name, "'" );
        }
    }
    ERROR_EXPECT("signal name", token);
}

ST_FUNC(LINK_DONE)
{
    return process_done_state(token, ST_NAME(LINK_START));
}

#ifdef BL_ENABLE_UNLINK
ST_FUNC(UNLINK_START)
{
    if ( is_name(token) ) {
        pd.instance_meta = bl_instance_find(token);
        if ( pd.instance_meta ) {
            pd.state = ST_NAME(UNLINK_1);
            return true;
        }
    }
    ERROR_EXPECT("instance name", token);
}

ST_FUNC(UNLINK_1)
{
    if ( is_name(token) ) {
        pd.pin_meta = bl_pin_find_in_instance(token, pd.instance_meta);
        if ( pd.pin_meta ) {
            if ( bl_pin_unlink(pd.pin_meta) ) {
                pd.state = ST_NAME(UNLINK_DONE);
                return true;
            }
            ERROR_API(6, "unlinking ", "pin '", pd.instance_meta->name, ".", pd.pin_meta->name, "'" );
        }
        pd.funct_meta = bl_function_find_in_instance(token, pd.instance_meta);
        if ( pd.funct_meta ) {
            if ( bl_function_unlink(pd.funct_meta) ) {
                pd.state = ST_NAME(UNLINK_DONE);
                return true;
            }
            ERROR_API(6, "unlinking ", "function '", pd.instance_meta->name, ".", pd.funct_meta->name, "'" );
        }
    }
    ERROR_EXPECT("pin or function name", token);
}

ST_FUNC(UNLINK_DONE)
{
    return process_done_state(token, ST_NAME(UNLINK_START));
}
#endif

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
    ERROR_EXPECT("signal or instance name", token);
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
    ERROR_EXPECT("pin name", token);
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
            ERROR_EXPECT("bit value", token);
        case BL_TYPE_FLOAT:
            if ( str_to_float(token, &(pd.set_target->f)) ) {
                pd.state = ST_NAME(SET_DONE);
                return true;
            }
            ERROR_EXPECT("float value", token);
        case BL_TYPE_S32:
            if ( str_to_s32(token, &(pd.set_target->s)) ) {
                pd.state = ST_NAME(SET_DONE);
                return true;
            }
            ERROR_EXPECT("s32 value", token);
        case BL_TYPE_U32:
            if ( str_to_u32(token, &(pd.set_target->u)) ) {
                pd.state = ST_NAME(SET_DONE);
                return true;
            }
            ERROR_EXPECT("u32 value", token);
        default:
            ERROR_INTERNAL();
    }
}

ST_FUNC(SET_DONE)
{
    return process_done_state(token, ST_NAME(SET_START));
}

ST_FUNC(SHOW_START)
{
    keyword_t const *kw;

    kw = is_keyword(token);
    if ( kw ) {
        if ( kw->is_obj_type ) {
            switch ( kw->objtype ) {
                case OBJ_INSTANCE:
                    bl_show_all_instances();
                return true;
                case OBJ_SIGNAL:
                    bl_show_all_signals();
                return true;
                case OBJ_THREAD:
                    bl_show_all_threads();
                return true;
                case OBJ_ALL:
                    bl_show_memory_status();
                    bl_show_all_instances();
                    bl_show_all_signals();
                    bl_show_all_threads();
                return true;
                default:
                    ERROR_INTERNAL();
            }
        }
        if ( kw->is_cmd ) {
            pd.state = ST_NAME(IDLE);
            return bl_parse_token(token);
        }
    }
    if ( is_name(token) ) {
        pd.instance_meta = bl_instance_find(token);
        if ( pd.instance_meta ) {
            bl_show_instance(pd.instance_meta);
            return true;
        }
        pd.signal_meta = bl_signal_find(token);
        if ( pd.signal_meta ) {
            bl_show_signal(pd.signal_meta);
            return true;
        }
        pd.thread_meta = bl_thread_find(token);
        if ( pd.thread_meta ) {
            bl_show_thread(pd.thread_meta);
            return true;
        }
    }
    ERROR_EXPECT("object name, object type, or 'all'", token);
}


static bool process_done_state(char const *token, bool (*state_if_not_command)(char const *token))
{
    keyword_t const *kw;

    if ( (kw = is_keyword(token)) != NULL ) {
        if ( kw->is_cmd ) {
            pd.state = ST_NAME(IDLE);
            return bl_parse_token(token);
        }
        ERROR_EXPECT("command", token);
    }
    pd.state = state_if_not_command;
    return bl_parse_token(token);
}


#ifdef BL_PRINT_ERRORS
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

static void error_internal(void)
{
    print_string("ERROR: internal error\n");
    pd.state = ST_NAME(IDLE);
}

static void error_expect(char const *expect, char const *token)
{
    print_strings(3, "ERROR: expected ", expect, "found " );
    print_token(token);
    print_string("\n");
    pd.state = ST_NAME(IDLE);
}

static void error_api(int num_strings, ...)
{
    va_list ap;

    print_string("ERROR: ");
    va_start(ap, num_strings);
    for ( int n = 0 ; n < num_strings ; n++ ) {
        print_string((char *)va_arg(ap, char *));
        }
    va_end(ap);
    print_strings(3, ": ", bl_errstr(), "\n");
}
#endif


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

#pragma GCC optimize ("no-strict-aliasing")
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
#pragma GCC reset_options
