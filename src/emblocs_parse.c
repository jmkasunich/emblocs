#include "emblocs_priv.h"
#include <string.h>         // strcmp
#include "printing.h"
#include "linked_list.h"

#define abs(x)  ( (x) > 0 ? (x) : -(x) )
#define halt()  do {} while (1)

static bool str_to_bool(char const * str, bool *dest);
static bool str_to_s32(char const *str, int32_t *dest);
static bool str_to_u32(char const *str, uint32_t *dest);
static bool str_to_float(char const *str, float *dest);

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
    return str_to_bool(token, &dest->b);
}

static bool parse_value_float(char const * token, bl_sig_data_t *dest)
{
    return str_to_float(token, &dest->f);
}

static bool parse_value_s32 (char const * token, bl_sig_data_t *dest)
{
    return str_to_s32(token, &dest->s);
}

static bool parse_value_u32(char const * token, bl_sig_data_t *dest)
{
    return str_to_u32(token, &dest->u);
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

