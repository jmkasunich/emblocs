#include "emblocs_priv.h"
#include <string.h>         // strcmp
#include "printing.h"
#include "linked_list.h"

#define halt()  do {} while (1)

typedef enum {
    KW_INSTANCE     = 0x0001,
    KW_PIN          = 0x0002,
    KW_FUNCTION     = 0x0003,
    KW_SIGNAL       = 0x0004,
    KW_THREAD       = 0x0005,
    KW_BIT          = 0x0006,
    KW_FLOAT        = 0x0007,
    KW_S32          = 0x0008,
    KW_U32          = 0x0009,
    KW_FP           = 0x000A,
    KW_NOFP         = 0x000B,
    KW_NET          = 0x000C,
    KW_SETSIG       = 0x000D,
    KW_SETPIN       = 0x000E,
    KW_SHOW         = 0x000F,
    KW_LINK         = 0x0010,
    KW_UNLINK       = 0x0011
} keyword_id_t;

#define KEYWORD_ID_MASK 0x001F

typedef enum {
    TT_NULL             = 0x0000,
    TT_COMMAND          = 0x0080,
    TT_SIGNAL_TYPE      = 0x1100,
    TT_FUNCT_TYPE       = 0x1200,
    TT_OBJECT_TYPE      = 0x1400,
    TT_NAME             = 0x2000,
    TT_INSTANCE_NAME    = 0x2100,
    TT_SIGNAL_NAME      = 0x2200,
    TT_THREAD_NAME      = 0x2400,
    TT_VALUE            = 0x4000,
    TT_VALUE_BIT        = 0x4100,
    TT_VALUE_FLOAT      = 0x4200,
    TT_VALUE_S32        = 0x4400,
    TT_VALUE_U32        = 0x4800,
    TT_UNKNOWN          = 0x8000
} token_type_enum_t;

#define TOKEN_TYPE_MASK 0xFF80

typedef struct keyword_s {
    char const *name;
    uint32_t id;
} keyword_t;

static keyword_t keywords[] = {
    { "instance",   KW_INSTANCE | TT_COMMAND | TT_OBJECT_TYPE },
    { "pin",        KW_PIN      | TT_OBJECT_TYPE },
    { "function",   KW_FUNCTION | TT_OBJECT_TYPE },
    { "signal",     KW_SIGNAL   | TT_COMMAND | TT_OBJECT_TYPE },
    { "thread",     KW_THREAD   | TT_COMMAND | TT_OBJECT_TYPE },
    { "bit",        KW_BIT      | TT_SIGNAL_TYPE },
    { "float",      KW_FLOAT    | TT_SIGNAL_TYPE },
    { "s32",        KW_S32      | TT_SIGNAL_TYPE },
    { "u32",        KW_U32      | TT_SIGNAL_TYPE },
    { "fp",         KW_FP       | TT_FUNCT_TYPE },
    { "nofp",       KW_NOFP     | TT_FUNCT_TYPE },
    { "net",        KW_NET      | TT_COMMAND | TT_OBJECT_TYPE },
    { "setsig",     KW_SETSIG   | TT_COMMAND },
    { "setpin",     KW_SETPIN   | TT_COMMAND },
    { "show",       KW_SHOW     | TT_COMMAND },
    { "link",       KW_LINK     | TT_COMMAND },
    { "unlink",     KW_UNLINK   | TT_COMMAND }
};

static bl_retval_t parse_token(char const * const token);
static uint32_t classify_token(char const * const token);
static bool is_name(char const * token);
static bool parse_value_bit  (char const * token, bl_sig_data_t *dest);
static bool parse_value_float(char const * token, bl_sig_data_t *dest);
static bool parse_value_s32  (char const * token, bl_sig_data_t *dest);
static bool parse_value_u32  (char const * token, bl_sig_data_t *dest);
static bool parse_u32_with_decimal_pt(char const **token, uint32_t *dest, int32_t *shift_digits);


/**************************************************************
 * These functions support parsing an array of tokens to build
 * or modify a system.
 */


bl_retval_t bl_parse_array(char const * const tokens[], uint32_t count)
{
    for ( uint32_t n = 0 ; n < count ; n++ ) {
        parse_token(tokens[n]);
    }
    return BL_ERR_GENERAL;
}

static bl_retval_t parse_token(char const *token)
{
    uint32_t id;

    id = classify_token(token);
    printf("%04x %16.4b '%s'\n", id, id, token);
    return 0;
}

static uint32_t classify_token(char const * const token)
{
    uint32_t retval;
    bl_sig_data_t value;

    if ( token == NULL ) {
        return TT_NULL;
    }
    // is it a keyword?
    for ( uint32_t n = 0 ; n < _countof(keywords) ; n++ ) {
        if ( strcmp(token, keywords[n].name) == 0 ) {
            return keywords[n].id;
        }
    }
    if ( is_name(token) ) {
        retval = TT_NAME;
        if ( ll_find((void **)(&(instance_root)), (void *)(token), bl_instance_meta_compare_name_key) ) {
            retval |= TT_INSTANCE_NAME;
        }
        if ( ll_find((void **)(&(signal_root)), (void *)(token), bl_sig_meta_compare_name_key) ) {
            retval |= TT_SIGNAL_NAME;
        }
        if ( ll_find((void **)(&(thread_root)), (void *)(token), bl_thread_meta_compare_name_key) ) {
            retval |= TT_THREAD_NAME;
        }
        return retval;
    }
    retval = 0;
    printf("Parsing '%s'\n", token);
    if ( parse_value_bit(token, &value) ) {
        retval |= TT_VALUE_BIT;
        printf("  bit   :%d\n", value.b);
    }
    if ( parse_value_float(token, &value) ) {
        retval |= TT_VALUE_FLOAT;
        printf("  float :%f\n", value.f);
    }
    if ( parse_value_s32(token, &value) ) {
        retval |= TT_VALUE_S32;
        printf("  s32   :%10d = %08x\n", value.s, value.s);
    }
    if ( parse_value_u32(token, &value) ) {
        retval |= TT_VALUE_U32;
        printf("  u32   :%10u = %08x\n", value.u, value.u);
    }
    if ( retval != 0 ) {
        return retval;
    }
    return TT_UNKNOWN;
}

static bool is_name(char const * token)
{
    char c;

    if ( token == NULL ) {
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

static bool parse_value_bit  (char const * token, bl_sig_data_t *dest)
{
    if ( token == NULL ) {
        return false;
    }
    if ( ( token[0] < '0' ) || ( token[0] > '1' ) ) {
        return false;
    }
    if ( token[1] != '\0' ) {
        return false;
    }
    if ( dest != NULL ) {
        dest->b = token[0] - '0';
    }
    return true;
}

static bool parse_value_float(char const * token, bl_sig_data_t *dest)
{
    bool is_neg;
    char c;
    uint32_t uval;
    int32_t shift;
    bl_sig_data_t exp_dest;

    is_neg = 0;
    c = *token;
    if ( c == '-' ) {
        is_neg = 1;
        token++;
    } else if ( c == '+' ) {
        token++;
    }
    if ( ! parse_u32_with_decimal_pt( &token, &uval, &shift) ) {
        return false;
    }
    c = *token++;
    if ( ( c == 'e' ) || ( c == 'E' ) ) {
        if ( ! parse_value_s32 (token, &exp_dest) ) {
            return false;
        }
        shift = shift + exp_dest.s;
    }
    // shift here
}

static bool parse_value_s32  (char const * token, bl_sig_data_t *dest)
{
    bool is_neg;
    char c;

    is_neg = 0;
    c = *token;
    if ( c == '-' ) {
        is_neg = 1;
        token++;
    } else if ( c == '+' ) {
        token++;
    }
    if ( ! parse_value_u32(token, dest) ) {
        return false;
    }
    if ( is_neg ) {
        if ( dest->u <= 2147483648 ) {
            dest->s = -dest->u;
            return true;
        }
    } else {
        if ( dest->u <= 2147483647 ) {
            dest->s = dest->u;
            return true;
        }
    }
    return false;
}

static bool parse_value_u32(char const * token, bl_sig_data_t *dest)
{
    char c;
    uint32_t result;
    uint32_t limit;

    result = 0;
    c = *(token++);
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
            // adding this digit would overflow; too many digits in token
            return false;
        }
        // add this digit
        result *= 10;
        result += c - '0';
        // next digit
        c = *(token++);
    } while ( c != '\0' );
    if ( dest != NULL ) {
        dest->u = result;
    }
    return true;
}


#ifdef USE_ONE_U32_FUNCT
static bool parse_u32_with_decimal_pt_generic(char const **token, uint32_t *dest, int32_t *shift_digits)
{
    char const *cp;
    char c;
    bool dp_found, reached_max;
    int shift;
    uint32_t result;
    uint32_t limit;

    result = 0;
    shift = 0;
    dp_found = 0;
    reached_max = 0;
    cp = *token;
    c = *(cp++);
    do {
        if ( ( c < '0' ) || ( c > '9' ) ) {
            if ( ( c != '.' ) || ( shift_digits == NULL ) ) {
                return false;
            } else {
                if ( dp_found ) {
                    return false;
                } else {
                    dp_found = 1;
                    c = *(cp++);
                    continue;
                }
            }
        }
        // largest number that can be multiplied by 10 and not overflow
        limit = 429496729;
        if ( c > '5' ) {
            // can't let the subsequent add overflow either
            limit--;
        }
        if ( result > limit ) {
            // adding this digit would overflow
            if ( shift_digits == NULL ) {
                return false;
            } else {
                if ( ! reached_max ) {
                    // first overflow digit, round it
                    if ( c >= '5' ) {
                        result++;
                    }
                    reached_max = 1;
                }
                if ( ! dp_found ) {
                    shift++;
                }
            }
        } else {
            // add this digit
            result *= 10;
            result += c - '0';
            if ( dp_found ) {
                shift--;
            }
        }
        // next digit
        c = *(cp++);
    } while ( ( c != '\0' ) && ( c != 'e' ) && ( c != 'E' ) );
    if ( ( shift_digits == NULL ) && ( c != '\0' ) ) {
        return false;
    }
    // update pointer to last character used
    *token = --cp;
    // save results
    if ( dest != NULL ) {
        *dest = result;
    }
    if ( shift_digits != NULL ) {
        *shift_digits = shift;
    }
    return true;
}
#endif

static bool parse_u32_with_decimal_pt(char const **token, uint32_t *dest, int32_t *shift_digits)
{
    char const *cp;
    char c;
    bool dp_found = 0;
    bool reached_max = 0;
    int32_t shift = 0;
    uint32_t result = 0;
    uint32_t limit;

    cp = *token;
    c = *(cp++);
    do {
        if ( ( c < '0' ) || ( c > '9' ) ) {
            if ( ( c == '.' ) && ( ! dp_found ) ) {
                dp_found = 1;
                c = *(cp++);
                continue;
            }
            return false;
        }
        // largest number that can be multiplied by 10 and not overflow
        limit = 429496729;
        if ( c > '5' ) {
            // can't let the subsequent add overflow either
            limit--;
        }
        if ( result > limit ) {
            // adding this digit would overflow
            if ( ! reached_max ) {
                // first overflow digit, round it
                if ( c >= '5' ) {
                    result++;
                }
                reached_max = 1;
            }
            if ( ! dp_found ) {
                shift++;
            }
        } else {
            // add this digit
            result *= 10;
            result += c - '0';
            if ( dp_found ) {
                shift--;
            }
        }
        // next digit
        c = *(cp++);
    } while ( ( c != '\0' ) && ( c != 'e' ) && ( c != 'E' ) );
    // update pointer to last character used
    *token = --cp;
    // save results
    if ( dest != NULL ) {
        *dest = result;
    }
    if ( shift_digits != NULL ) {
        *shift_digits = shift;
    }
    return true;
}

