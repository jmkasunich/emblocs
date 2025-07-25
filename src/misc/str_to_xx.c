#include "str_to_xx.h"

#define abs(x)  ( (x) > 0 ? (x) : -(x) )

bool str_to_bool(char const * str, bool *dest)
{
    if ( ( str == NULL )  ||
         ( str[0] < '0' ) || ( str[0] > '1' ) ||
         ( str[1] != '\0' ) ) {
        return false;
    }
    if ( dest != NULL ) {
        *dest = (str[0] == '1');
    }
    return true;
}

bool str_to_u32(char const *str, uint32_t *dest)
{
    if ( str == NULL ) {
        return false;
    }
    uint32_t result = 0;
    char c = *(str++);
    do {
        if ( ( c < '0' ) || ( c > '9' ) ) {
            return false;
        }
        // largest number that can be multiplied by 10 and not overflow
        uint32_t limit = 429496729;
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

bool str_to_s32(char const *str, int32_t *dest)
{
    if ( str == NULL ) {
        return false;
    }
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
            result = -(int32_t)utmp;
        }
    } else {
        if ( utmp > 0x7FFFFFFF ) {
            return false;
        } else {
            result = (int32_t)utmp;
        }
    }
    if ( dest != NULL ) {
        *dest = result;
    }
    return true;
}

#pragma GCC optimize ("no-strict-aliasing") // float <-> u32 type punning
bool str_to_float(char const *str, float *dest)
{
    if ( str == NULL ) {
        return false;
    }
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
    uint32_t shift_abs = (uint32_t)abs(shift);
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

