/***************************************************************
 * 
 * printing.c - lightweight console printing functions
 * 
 * see printing.h for API details
 * 
 * *************************************************************/

#include "printing.h"
#include "platform.h"
#include <stdarg.h>
#include <assert.h>
#include <math.h>


int snprint_string(char *buf, int size, const char *string)
{
    char c;
    int n = 0;

    if ( string == NULL ) return 0;
    // make sure there will be room for the terminating '\0'
    size--;
    // copy characters to buffer
    while ( ( n < size ) && ( (c = string[n]) != '\0' ) ) {
        buf[n++] = c;
    }
    // terminate the string
    buf[n] = '\0';
    return n;
}

int snprint_int_dec(char *buf, int size, int32_t value, char sign)
{
    assert(size >= 12);
    if ( value < 0 ) {
        *(buf++) = '-';
        return snprint_uint_dec(buf, size-1, -value) + 1;
    } else {
        if ( ( sign == ' ' ) || ( sign == '+' ) ) {
            *(buf++) = sign;
            return snprint_uint_dec(buf, size-1, value) + 1;
        } else {
            return snprint_uint_dec(buf, size, value);
        }
    }
}

int snprint_uint_dec(char *buf, int size, uint32_t value)
{
    int digit, len;
    char *start, *end, tmp;

    assert(size >= 11);
    // calculate digits in reverse order, then reverse them
    // init start and end pointers
    start = end = buf;
    // final digit must be printed even if value = 0
    do {
        digit = value % 10;
        value = value / 10;
        *(end++) = (char)('0' + digit);
        // loop till no more digits
    } while ( value > 0 );
    len = end - start;
    // terminate the string and point at last non-terminator character
    *(end--) = '\0';
    // reverse the string
    while ( end > start ) {
        tmp = *end;
        *(end--) = *start;
        *(start++) = tmp;
    }
    return len;
}

// private common code for binary, hex, and pointer printing
static int snprint_uint_bin_hex(char *buf, int size, uint32_t value, int base, int digits, int group, int uc)
{
    char *cp, alpha;
    int digit, dividers, group_cnt;
    int mask, shift, maxdigits;

    if ( base == 2 ) {
        mask = 0x01;
        shift = 1;
        maxdigits = 32;
    } else if ( base == 16 ) {
        mask = 0x0F;
        shift = 4;
        maxdigits = 8;
    } else {
        assert(1);
        return 0;  // make compiler happy
    }
    if ( ( digits < 1 ) || ( digits > maxdigits ) ) digits = maxdigits;
    if ( ( group < 1 ) || ( group > maxdigits ) ) group = maxdigits;
    if ( group < digits ) {
        dividers = (digits - 1) / group;
    } else {
        dividers = 0;
    }
    alpha = uc ? 'A' : 'a';
    assert(size > (digits + dividers + 1));
    // start at the end and work backwards
    cp = buf + digits + dividers;
    *(cp--) = '\0';
    group_cnt = group;
    // build the number
    while ( digits > 0 ) {
        if ( group_cnt <= 0 ) {
            *(cp--) = '-';
            group_cnt = group;
        }
        group_cnt--;
        digit = value & mask;
        *(cp--) = (char)(( digit > 9 ) ? ( alpha + digit - 10 ) : ( '0' + digit ) );
        digits--;
        value >>= shift;
    }
    return digits + dividers;
}

int snprint_uint_hex(char *buf, int size, uint32_t value, int digits, int uc, int group)
{
    return snprint_uint_bin_hex(buf, size, value, 16, digits, group, uc);
}

int snprint_uint_bin(char *buf, int size, uint32_t value, int digits, int group)
{
    return snprint_uint_bin_hex(buf, size, value, 2, digits, group, 0);
}

int snprint_ptr(char *buf, int size, void *ptr)
{
    return snprint_uint_bin_hex(buf, size, (uint32_t)ptr, 16, 8, 0, 1);
}

/* private typedefs and functions for dealing with floating point */
typedef union {
    float f;
    struct {
        unsigned int mantissa:23;
        unsigned int exponent:8;
        unsigned int negative:1;
    } ieee;
} ieee_float_t;
#define IEEE754_FLOAT_BIAS        0x7f /* Added to exponent.  */

typedef union {
    double d;
    struct {
        unsigned int mantissa1:32;
        unsigned int mantissa0:20;
        unsigned int exponent:11;
        unsigned int negative:1;
    } ieee;
} ieee_double_t;
#define IEEE754_DOUBLE_BIAS        0x3ff /* Added to exponent.  */

/* private function to return 10^pow for integer 'pow' */
static double p10(int pow)
{
    double result;
    int32_t iresult, ifactor;

    if ( pow < 0 ) {
        result = 1.0 / p10(-pow);
        return result;
    }
    assert(pow < 308);
    result = 1.0;
    while ( pow >= 8 ) {
        result *= 1e8f;
        pow -= 8;
    }
    ifactor = 10;
    iresult = 1;
    while ( pow > 0 ) {
        if ( pow & 1 ) {
            iresult = iresult * ifactor;
        }
        ifactor = ifactor * ifactor;
        pow >>= 1;
    }
    result = result * (float)iresult;
    return result;
}

/* private function to deal with floating point special cases
 *   (nan, infinity, zero, negative)
 * returns number of chars written into buffer
 * if 0, *value is positive and non-zero
 * if 1, *value was negative and non-zero, is now positive , '-' is in buffer
 * if > 1, value was zero, nan, or inf and the appropriate string is in the buffer
 * 'precision' and 'use_sci' describe the string to be output for zero
 * caller must ensure that the buffer can hold the specified representation
 * of zero, either '0.<precision>' or '0.<precision>e+00', as well as '-nan'
 * or '-inf'; this function does not know the buffer size
 */
int snprint_double_handle_special_cases(char *buf, double *value, int precision, int use_sci)
{
    int len = 0;
    int fpclass;

    if ( signbit(*value) ) {
        *value = -(*value);
        *(buf++) = '-';
        len++;
    }
    fpclass = fpclassify(*value);
    if ( fpclass == FP_NAN ) {
        len += snprint_string(buf, 4, "nan");
    } else if ( fpclass == FP_INFINITE ) {
        len += snprint_string(buf, 4, "inf");
    } else if ( fpclass == FP_ZERO ) {
        *(buf++) = '0';
        len++;
        if ( precision > 0 ) {
            *(buf++) = '.';
            len++;
            while ( precision-- > 0 ) {
                *(buf++) = '0';
                len++;
            }
        }
        if ( use_sci ) {
            len += snprint_string(buf, 5, "e+00");
        }
    }
    return len;
}

int snprint_double(char *buf, int size, double value, int precision)
{
    int len;
    uint32_t int_part;
    double frac_part;
    char digit;

    if ( precision > 16 ) {
        precision = 16;
    } else if ( precision < 0 ) {
        precision = 0;
    }
    /* check buffer size - worst case is '-' plus 10-digit integer
       plus '.' plus 'precision' trailing digits plus terminator */
    assert(size > (precision + 13));
    len = snprint_double_handle_special_cases(buf, &value, precision, 0);
    if ( len > 1 ) return len;
    if ( value > 4294967295.0 ) {
        // too large for regular printing
        return len + snprint_double_sci(buf+len, size-len, value, precision);
    }
    if ( value < 1e-6 ) {
        // too small for regular printing
        return snprint_double_sci(buf+len, size-len, value, precision);
    }
    // perform rounding to specified precision
    value = value + 0.5 * p10(-precision);
    // split into integer and fractional parts
    int_part = (uint32_t)value;
    frac_part = value - int_part;
    len += snprint_uint_dec(buf+len, size-len, int_part);
    if ( precision > 0 ) {
        *(buf+len) = '.';
        len++;
        do {
            frac_part = frac_part * 10.0;
            digit = (char)frac_part;
            frac_part -= digit;
            *(buf+len) = '.';
            len++;
        } while ( --precision > 0 );
    }
    // terminate the string
    *(buf+len) = '\0';
    return len;
}









void print_char(char c)
{
    cons_tx_wait(c);
}

void print_string(const char *string)
{
    if ( string == NULL ) return;
    while ( *string != '\0' ) {
        print_char(*string);
        string++;
    }
}

void print_int_dec(int32_t value, char sign)
{
    char buffer[16];
    snprint_int_dec(buffer, 16, value, sign);
    print_string(buffer);
}

void print_uint_dec(uint32_t value)
{
    char buffer[16];
    snprint_uint_dec(buffer, 16, value);
    print_string(buffer);
}

void print_uint_hex(uint32_t n, int digits, int group, int uc)
{
    char buffer[20];
    snprint_uint_bin_hex(buffer, 20, n, 16, digits, group, uc);
    print_string(buffer);
}

void print_uint_bin(uint32_t n, int digits, int group)
{
    char buffer[68];
    snprint_uint_bin_hex(buffer, 68, n, 2, digits, group, 0);
    print_string(buffer);
}

// print a pointer
void print_ptr(void const * ptr)
{
    print_uint_hex((uint32_t)ptr, 8, 0, 1);
}









void print_double(double v, int precision)
{
    int c;
    uint32_t int_part;
    double frac_part;
    char digit;

    if ( signbit(v) ) {
        v = -v;
        print_char('-');
    }
    if ( precision > 16 ) {
        precision = 16;
    } else if ( precision < 0 ) {
        precision = 0;
    }
    c = fpclassify(v);
    if ( c == FP_NAN ) {
        print_string("nan");
        return;
    }
    if ( c == FP_INFINITE ) {
        print_string("inf");
        return;
    }
    if ( c == FP_ZERO ) {
        print_char('0');
        if ( precision > 0 ) {
            print_char('.');
            while ( precision-- > 0 ) {
                print_char('0');
            }
        }
        return;
    }
    if ( v > 4294967295.0 ) {
        // too large for regular printing
        print_double_sci(v, precision);
        return;
    }
    if ( v < 1e-6 ) {
        // too small for regular printing
        print_double_sci(v, precision);
        return;
    }
    // perform rounding to specified precision
    v = v + 0.5 * p10(-precision);
    // split into integer and fractional parts
    int_part = (uint32_t)v;
    frac_part = v - int_part;
    print_uint_dec(int_part);
    if ( precision > 0 ) {
        print_char('.');
        do {
            frac_part = frac_part * 10.0;
            digit = (char)frac_part;
            frac_part -= digit;
            print_char('0' + digit);
        } while ( --precision > 0 );
    }
}


void print_double_sci(double v, int precision)
{
    int c, exponent;
    char digit;

    if ( signbit(v) ) {
        v = -v;
        print_char('-');
    }
    if ( precision > 16 ) {
        precision = 16;
    } else if ( precision < 0 ) {
        precision = 0;
    }
    c = fpclassify(v);
    if ( c == FP_NAN ) {
        print_string("nan");
        return;
    }
    if ( c == FP_INFINITE ) {
        print_string("inf");
        return;
    }
    if ( c == FP_ZERO ) {
        print_char('0');
        if ( precision > 0 ) {
            print_char('.');
            while ( precision-- > 0 ) {
                print_char('0');
            }
            print_string("e+00");
        }
        return;
    }
    exponent = 0;
    if ( v < 1.0 ) {
        // small number, make it bigger
        while ( v < 1e-8 ) {
            v *= 1e8;
            exponent -= 8;
        }
        while ( v < 1e-3 ) {
            v *= 1e3;
            exponent -= 3;
        }
        while ( v < 1.0 ) {
            v *= 10.0;
            exponent -= 1;
        }
    } else {
        // large number, make it smaller
        while ( v >= 1e8 ) {
            v *= 1e-8;
            exponent += 8;
        }
        while ( v >= 1e3 ) {
            v *= 1e-3;
            exponent += 3;
        }
        while ( v >= 1e1 ) {
            v *= 1e-1;
            exponent += 1;
        }
    }
    // perform rounding to specified precision
    v = v + 0.5 * p10(-precision);
    // there is a small chance that rounding pushed it over 10.0
    if ( v >= 10.0 ) {
        v *= 0.1;
        exponent += 1;
    }
    // print the first digit
    digit = (char)v;
    print_char('0' + digit);
    if ( precision > 0 ) {
        print_char('.');
        do {
            v = v - digit;
            v = v * 10.0;
            digit = (char)v;
            print_char('0' + digit);
        } while ( --precision > 0 );
    }
    print_char('e');
    if ( exponent < 0 ) {
        print_char('-');
        exponent = -exponent;
    } else {
        print_char('+');
    }
    digit = (char)(exponent/10);
    print_char('0' + digit);
    digit = (char)(exponent%10);
    print_char('0' + digit);
}






#if 0

// private helpers for printf
static inline int _is_digit(char ch)
{
  return (ch >= '0') && (ch <= '9');
}

static unsigned int _atoi(char const ** str)
{
  unsigned int i = 0U;
  while (_is_digit(**str)) {
    i = i * 10U + (unsigned int)(*((*str)++) - '0');
  }
  return i;
}


// formatted printing
void printf_(char const *fmt, ...)
{
    va_list ap;
    int width, prec;
    char sign;

    va_start(ap, fmt);
    while ( *fmt != '\0' ) {
        if ( *fmt != '%' ) {
            // print it verbatim
            print_char(*(fmt++));
            continue;
        }
        // look at next char
        fmt++;
        if ( ( *fmt == '+' ) || ( *fmt == ' ') ) {
            sign = *(fmt++);
        } else {
            sign = '\0';
        }
        width = 0;
        if ( _is_digit(*fmt) ) {
            width = _atoi(&fmt);
        }
        prec = -1;
        if ( *fmt == '.' ) {
            fmt++;
            if ( _is_digit(*fmt) ) {
                prec = _atoi(&fmt);
            }
        }
        switch (*fmt) {
        case 'd':
            print_int_dec((int32_t)va_arg(ap, int32_t), sign);
            break;
        case 'u':
            print_uint_dec((uint32_t)va_arg(ap, uint32_t));
            break;
        case 'x':
            print_uint_hex((uint32_t)va_arg(ap, uint32_t), prec, 0, 0);
            break;
        case 'X':
            print_uint_hex((uint32_t)va_arg(ap, uint32_t), prec, 1, 0);
            break;
        case 's':
            print_string_width((char *)va_arg(ap, char *), width, prec);
            break;
        case 'c':
            print_char((char)va_arg(ap, int));
            break;
        case 'p':
            print_ptr((void *)va_arg(ap, void *));
            break;
        case 'b':
            print_uint_bin((uint32_t)va_arg(ap, uint32_t), prec, 0);
            break;
        case 'B':
            print_uint_bin((uint32_t)va_arg(ap, uint32_t), prec, 8);
            break;
        default:
            print_char(*fmt);
            break;
        }
        fmt++;
    }
    va_end(ap);
}   






void print_memory(void const *mem, uint32_t len)
{
    uint8_t const *start, *end, *row, *addr;
    int n;
    char c;

    start = (uint8_t const *)mem;
    end = start + len;
    row = (void *)((uint32_t)(start) & 0xFFFFFFF0);
    while ( row <= end ) {
        print_char('\n');
        print_uint_hex((uint32_t)row, 8, 1, 0);
        print_string(" :");
        addr = row;
        for ( n = 0 ; n < 16 ; n++ ) {
            if ( ( addr >= start ) && ( addr <= end ) ) {
                print_char(' ');
                print_uint_hex(*(addr++), 2, 0, 0);
            } else {
                print_string("   ");
                addr++;
            }
        }
        print_string(" - ");
        addr = row;
        for ( n = 0 ; n < 16 ; n++ ) {
            if ( ( addr >= start ) && ( addr <= end ) ) {
                c = *(addr++);
                if ( ( c > 0x20 ) && ( c < 0x80 ) ) {
                    print_char(c);
                } else {
                    print_char('.');
                }
            } else {
                print_char(' ');
                addr++;
            }
        }
        row += 16;
    }
    print_char('\n');
}



// private helper function for padding with spaces
static void pad(int spaces)
{
    while ( spaces > 0 ) {
        print_char(' ');
        spaces--;
    }
}

// print a string with padding and/or truncation
void print_string_width(char const *string, int width, int maxlen)
{
    if ( string == NULL ) return;
    if ( maxlen <= 0 ) maxlen = 0x7FFFFFFF;
    if ( width < 0 ) width = 0;
    if ( width > maxlen ) width = maxlen;
    if ( width > 0 ) {
        // need to see how long the string is
        char const* cp = string;
        while ( ( *cp != '\0' ) && ( width > 0 ) ) {
            cp++;
            width--;
        }
        // print the leading spaces
        pad(width);
    }
    while ( ( *string != '\0' ) && ( maxlen > 0 ) ) {
        print_char(*string);
        string++;
        maxlen--;
    }
}

#endif // 0

