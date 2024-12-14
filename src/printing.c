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

/* private helper for printing decimal numbers
   prints unsigned number, padding with leading zeros if less than 'digits'
   assumes that caller has validated 'size'
 */
static int snprint_uint_dec_helper(char *buf, int size, uint32_t value, int digits)
{
    int digit, len;
    char *start, *end, tmp;

    if ( digits > 10 ) digits = 10;
    // calculate digits in reverse order, then reverse them
    // init start and end pointers
    start = end = buf;
    // final digit must be printed even if value = 0
    do {
        digit = value % 10;
        value = value / 10;
        *(end++) = (char)('0' + digit);
        digits--;
        // loop till no more digits
    } while ( value > 0 );
    // pad if needed
    while ( digits-- > 0 ) {
        *(end++) = '0';
    }
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

int snprint_int_dec(char *buf, int size, int32_t value, char sign)
{
    int len = 0;

    assert(size >= 12);
    if ( value < 0 ) {
        buf[len++] = '-';
        value = -value;
    } else if ( ( sign == ' ' ) || ( sign == '+' ) ) {
        buf[len++] = sign;
    }
    len += snprint_uint_dec_helper(buf+len, size-len, value, 0);
    return len;
}

int snprint_uint_dec(char *buf, int size, uint32_t value)
{
    assert(size >= 11);
    return snprint_uint_dec_helper(buf, size, value, 0);
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
    for ( int n = digits ; n > 0 ; n-- ) {
        if ( group_cnt <= 0 ) {
            *(cp--) = '-';
            group_cnt = group;
        }
        group_cnt--;
        digit = value & mask;
        *(cp--) = (char)(( digit > 9 ) ? ( alpha + digit - 10 ) : ( '0' + digit ) );
        value >>= shift;
    }
    return digits + dividers;
}

int snprint_uint_hex(char *buf, int size, uint32_t value, int digits, int group, int uc)
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


#define NEW_FRAC_PART


/* private lookup table for rounding - I want to add 0.5 * 10^^(-precision),
 * where legal values of 'precision' are 0 to 16.  Single precision is
 * good enough, so just make a 17-entry float lookup table.
 */
static float round_factor[] = {
    0.5e0f,   0.5e-1f,  0.5e-2f,  0.5e-3f,
    0.5e-4f,  0.5e-5f,  0.5e-6f,  0.5e-7f,
    0.5e-8f,  0.5e-9f,  0.5e-10f, 0.5e-11f,
    0.5e-12f, 0.5e-13f, 0.5e-14f, 0.5e-15f,
    0.5e-16f
};

#ifdef NEW_FRAC_PART
/* private lookup table for printing 'chunks' of the fractional part
 * I need to multiply by 10^^(digits), where 'digits' is 1 to 9
 * C will promote integers as needed and these all fit in 32 bits so
 * just make a 10-entry uint32_t lookup table
 */
static uint32_t pow10[] = {
    1, 10, 100, 1000, 10000, 100000, 1000000, 10000000, 100000000, 1000000000
};
#endif

/* private function to deal with floating point special cases
 *   (nan, infinity, zero, negative)
 * returns number of chars written into buffer
 * if 0, *value is positive and non-zero
 * if 1, *value was negative and non-zero, is now positive , '-' is in buffer
 * if > 1, value was zero, nan, or inf and the appropriate string is in the buffer
 * 'precision' and 'use_sci' describe the string to be output for zero
 * caller must ensure that the buffer can hold the specified representation
 * of zero, either '0.<precision>' or '0.<precision>e+0', as well as '-nan'
 * or '-inf'; this function does not know the buffer size
 */
static int snprint_double_handle_special_cases(char *buf, double *value, int precision, int use_sci)
{
    int len = 0;
    int fpclass;

    if ( signbit(*value) ) {
        *value = -(*value);
        buf[len++] = '-';
    }
    fpclass = fpclassify(*value);
    if ( fpclass == FP_NAN ) {
        len += snprint_string(buf+len, 4, "nan");
    } else if ( fpclass == FP_INFINITE ) {
        len += snprint_string(buf+len, 4, "inf");
    } else if ( fpclass == FP_ZERO ) {
        buf[len++] = '0';
        if ( precision > 0 ) {
            buf[len++] = '.';
            while ( precision-- > 0 ) {
                buf[len++] = '0';
            }
        }
        if ( use_sci ) {
            len += snprint_string(buf+len, 5, "e+0");
        }
    }
    buf[len] = '\0';
    return len;
}

/* private helper function that prints a floating point number
 * assumes that snprint_double_handle_special_cases() has been called
 * assumes that buffer size has been checked
 * assumes that value is greater than zero and less than +4.294967294e+9
 * assumes that appropriate rounding has been done
 */
static int snprint_double_helper(char *buf, int size, double value, int precision)
{
    int len;
    uint32_t int_part;
#ifdef NEW_FRAC_PART
    int digits;
#else
    char digit;
#endif

   // split into integer and fractional parts
    int_part = (uint32_t)value;
    value -= int_part;
    len = snprint_uint_dec_helper(buf, size, int_part, 0);
    if ( precision > 0 ) {
        buf[len++] = '.';
#ifdef NEW_FRAC_PART
        do {
            digits = ( precision > 9 ) ? 9 : precision;
            value *= pow10[digits];
            int_part = (uint32_t)value;
            value -= int_part;
            len += snprint_uint_dec_helper(buf+len, size-len, int_part, digits);
            precision -= digits;
        } while ( precision > 0 );
#else
        do {
            value = value * 10.0;
            digit = (char)value;
            value -= digit;
            buf[len++] = '0' + digit;
        } while ( --precision > 0 );
#endif // NEW_FRAC_PART
    }
    // terminate the string
    buf[len] = '\0';
    return len;
}

int snprint_double(char *buf, int size, double value, int precision)
{
    int len;

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
    if ( value > 4294967294.0 ) {
        // too large for regular printing
        return len + snprint_double_sci(buf+len, size-len, value, precision);
    }
    if ( value < 1e-6 ) {
        // too small for regular printing
        return len + snprint_double_sci(buf+len, size-len, value, precision);
    }
    // perform rounding to specified precision
    value = value + round_factor[precision];
    // print it
    return len + snprint_double_helper(buf+len, size-len, value, precision);
}

int snprint_double_sci(char *buf, int size, double value, int precision)
{
    int len;
    int exponent;

    if ( precision > 16 ) {
        precision = 16;
    } else if ( precision < 0 ) {
        precision = 0;
    }
    /* check buffer size - worst case is '-' plus 1 digit plus '.' plus
       'precision' trailing digits plus 'e+123' plus terminator */
    assert(size > (precision + 9));
    len = snprint_double_handle_special_cases(buf, &value, precision, 1);
    if ( len > 1 ) return len;
    // determine the exponent
    exponent = 0;
    while ( value < 1.0 ) {
        value *= 10.0;
        exponent -= 1;
    }
    while ( value >= 10.0 ) {
        value *= 0.1;
        exponent += 1;
    }
    // perform rounding to specified precision
    value = value + round_factor[precision];
    // there is a small chance that rounding pushed it over 10.0
    if ( value >= 10.0 ) {
        value *= 0.1;
        exponent += 1;
    }
    // print the mantissa
    len += snprint_double_helper(buf+len, size-len, value, precision);
    // and the exponent
    buf[len++] = 'e';
    len += snprint_int_dec(buf+len, size-len, exponent, '+');
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

void print_uint_hex(uint32_t value, int digits, int group, int uc)
{
    char buffer[20];
    snprint_uint_bin_hex(buffer, 20, value, 16, digits, group, uc);
    print_string(buffer);
}

void print_uint_bin(uint32_t value, int digits, int group)
{
    char buffer[68];
    snprint_uint_bin_hex(buffer, 68, value, 2, digits, group, 0);
    print_string(buffer);
}

// print a pointer
void print_ptr(void const * ptr)
{
    print_uint_hex((uint32_t)ptr, 8, 0, 1);
}

void print_double(double value, int precision)
{
    char buffer[32];
    snprint_double(buffer, 32, value, precision);
    print_string(buffer);
}

void print_double_sci(double value, int precision)
{
    char buffer[28];
    snprint_double_sci(buffer, 32, value, precision);
    print_string(buffer);
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

