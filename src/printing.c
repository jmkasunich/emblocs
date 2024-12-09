/***************************************************************
 * 
 * printing.c - lightweight console printing functions
 * 
 * These functions are optimized to use minimum RAM; things are
 * sent to the console as early as possible instead of building
 * the complete string in a buffer.
 *
 * *************************************************************/

#include "printing.h"
#include "platform.h"
#include <stdarg.h>
#include <assert.h>


// print a character
void print_char(char c)
{
    cons_tx_wait(c);
}

// print a string, no truncation or padding
void print_string(const char *string)
{
    if ( string == NULL ) return;
    while ( *string != '\0' ) {
        print_char(*string);
        string++;
    }
}


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

// private helper function for decimal numbers
static void print_dec(uint32_t n, int width, char sign)
{
    char buffer[12], *cp;
    int digit;

    if ( width < 0 ) width = 0;
    // point to end of buffer & terminate
    cp = &buffer[11];
    *cp = '\0';
    // final digit must be printed even if n = 0
    do {
        digit = n % 10;
        n = n / 10;
        *(--cp) = (char)('0' + digit);
        width--;
        // loop till no more digits
    } while ( n > 0 );
    if ( sign != '\0' ) {
        *(--cp) = sign;
        width--;
    }
    // add padding if needed
    pad(width);
    // print the buffer
    print_string(cp);
}

// print a signed decimal integer
void print_int_dec(int32_t n, int width, char sign)
{
    if ( n < 0 ) {
        // handle negative
        print_dec(-n, width, '-');
    } else {
        if ( ( sign == ' ') || ( sign == '+') ) {
            print_dec(n, width, sign);
        } else {
            print_dec(n, width, '\0');
        }
    }
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

// print an unsigned decimal integer
void print_uint_dec(uint32_t n, int width)
{
    print_dec(n, width, '\0');
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



// translation tables for hex printing
static char const itox[] = {
    '0', '1', '2', '3', '4', '5', '6', '7',
    '8', '9', 'a', 'b', 'c', 'd', 'e', 'f'
};

static char const itoX[] = {
    '0', '1', '2', '3', '4', '5', '6', '7',
    '8', '9', 'A', 'B', 'C', 'D', 'E', 'F'
};

// print a hex integer
void print_int_hex(int32_t n, int width, int digits, int uc)
{
    print_uint_hex((uint32_t) n, width, digits, uc);
}

void print_uint_hex(uint32_t n, int width, int digits, int uc)
{
    char buffer[12], *cp;
    char const *xlate;
    int digit;

    if ( width < 0 ) width = 0;
    if ( ( digits <= 0 ) || ( digits > 8 ) ) digits = 8;
    width -= digits;
    // send padding if needed
    pad(width);
    // select translation table
    xlate = uc ? itoX : itox;
    // point to end of buffer and terminate it
    cp = &buffer[11];
    *cp = '\0';
    // build the number
    while ( digits > 0 ) {
        digit = n & 0x0000000F;
        *(--cp) = xlate[digit];
        digits--;
        n >>= 4;
    }
    print_string(cp);
}

// print a pointer
void print_ptr(void const * ptr, int width)
{
    print_uint_hex((uint32_t)(ptr), width, 8, 1);
}

// print a binary integer
//   both versions work the same; the int version avoids a warning
//   displays low 'digits', left padded with space to 'width'
void print_int_bin(int32_t n, int width, int digits, int group)
{
    print_uint_bin((uint32_t) n, width, digits, group);
}

void print_uint_bin(uint32_t n, int width, int digits, int group)
{
    uint32_t mask;
    int next_sep = 0;

    if ( width < 0 ) width = 0;
    if ( ( digits <= 0 ) || ( digits > 32 ) ) digits = 32;
    if ( ( group <= 0 ) || ( group >= digits ) ) group = 0;
    width -= digits;
     if ( group > 0 ) {
        int num_sep = (digits-1) / group;
        width -= num_sep;
        next_sep = num_sep * group;        
    }
    // send padding if needed
    pad(width);
    // output the number
    mask = 1 << ( digits - 1 );
    while ( digits > 0 ) {
        // send group separator if needed
        if ( digits == next_sep ) {
            print_char('.');
            next_sep -= group;
        }
        if ( n & mask ) {
            print_char('1');
        } else {
            print_char('0');
        }
        mask >>= 1;
        digits--;
    }
}


static float p10(int pow)
{
    float result;
    int32_t iresult, ifactor;

    if ( pow < 0 ) {
        result = 1.0f / p10(-pow);
        return result;
    }
    if ( pow > 38 ) {
        pow = 38;
    }
    result = 1.0f;
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

#include <math.h>

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
    print_uint_dec(int_part, 0);
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
            print_int_dec((int32_t)va_arg(ap, int32_t), width, sign);
            break;
        case 'u':
            print_uint_dec((uint32_t)va_arg(ap, uint32_t), width);
            break;
        case 'x':
            print_uint_hex((uint32_t)va_arg(ap, uint32_t), width, prec, 0);
            break;
        case 'X':
            print_uint_hex((uint32_t)va_arg(ap, uint32_t), width, prec, 1);
            break;
        case 's':
            print_string_width((char *)va_arg(ap, char *), width, prec);
            break;
        case 'c':
            print_char((char)va_arg(ap, int));
            break;
        case 'p':
            print_ptr((void *)va_arg(ap, void *), width);
            break;
        case 'b':
            print_uint_bin((uint32_t)va_arg(ap, uint32_t), width, prec, 0);
            break;
        case 'B':
            print_uint_bin((uint32_t)va_arg(ap, uint32_t), width, prec, 8);
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
        print_uint_hex((uint32_t)row, 8, 8, 1);
        print_string(" :");
        addr = row;
        for ( n = 0 ; n < 16 ; n++ ) {
            if ( ( addr >= start ) && ( addr <= end ) ) {
                print_uint_hex(*(addr++), 3, 2, 0);
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





