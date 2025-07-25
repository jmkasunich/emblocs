/***************************************************************
 * 
 * printing.c - lightweight console printing functions
 * 
 * see printing.h for API details
 * 
 * *************************************************************/

#include "printing.h"
#ifdef PICO_BUILD
#include <stdio.h>
#else
#include "platform.h"
#endif
#include <stdarg.h>
#include <assert.h>
#include <math.h>

//#define HANDLE_DENORM
#define NEW_FRAC_PART





uint snprint_string(char *buf, uint size, const char *string)
{
    char c;
    uint n = 0;

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
static uint snprint_uint_dec_helper(char *buf, uint size, uint32_t value, uint digits)
{
    uint32_t digit, len;
    char *start, *end, tmp;

    // largest possible uint32_t fits in 10 digits
    assert(size > 10);
    if ( digits > 10 ) digits = 10;
    // calculate digits in reverse order, then reverse them
    // init start and end pointers
    start = end = buf;
    // final digit must be printed even if value = 0
    do {
        digit = value % 10u;
        value = value / 10;
        *(end++) = (char)('0' + digit);
        digits--;
        // loop till no more digits
    } while ( value > 0 );
    // pad if needed
    while ( digits-- > 0 ) {
        *(end++) = '0';
    }
    len = (uint32_t)(end - start);
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

uint snprint_int_dec(char *buf, uint size, int32_t value, char sign)
{
    uint len = 0;

    assert(size >= PRINT_INT_DEC_MAXLEN);
    if ( value < 0 ) {
        buf[len++] = '-';
        value = -value;
    } else if ( ( sign == ' ' ) || ( sign == '+' ) ) {
        buf[len++] = sign;
    }
    len += snprint_uint_dec_helper(buf+len, size-len, (uint32_t)value, 0);
    return len;
}

uint snprint_uint_dec(char *buf, uint size, uint32_t value)
{
    assert(size >= PRINT_UINT_DEC_MAXLEN);
    return snprint_uint_dec_helper(buf, size, value, 0);
}

// private common code for binary, hex, and pointer printing
static uint snprint_uint_bin_hex(char *buf, uint size, uint32_t value, uint base, uint digits, uint group, uint uc)
{
    char *cp, alpha;
    uint digit, dividers, group_cnt;
    uint mask, shift, maxdigits;

    if ( base == 2 ) {
        mask = 0x01;
        shift = 1;
        maxdigits = 32;
    } else if ( base == 16 ) {
        mask = 0x0F;
        shift = 4;
        maxdigits = 8;
    } else {
        assert(0);
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
    for ( uint32_t n = digits ; n > 0 ; n-- ) {
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

uint snprint_uint_hex(char *buf, uint size, uint32_t value, uint digits, uint group, uint uc)
{
    return snprint_uint_bin_hex(buf, size, value, 16u, digits, group, uc);
}

uint snprint_uint_bin(char *buf, uint size, uint32_t value, uint digits, uint group)
{
    return snprint_uint_bin_hex(buf, size, value, 2u, digits, group, 0);
}

uint snprint_ptr(char *buf, uint size, void *ptr)
{
    return snprint_uint_bin_hex(buf, size, (uint32_t)ptr, 16u, 8u, 0, 1u);
}


/* private lookup table for rounding - I want to add 0.5 * 10^^(-precision),
 * where legal values of 'precision' are 0 to 15.  Single precision is
 * good enough, so just make a 16-entry float lookup table.
 */
static float round_factor[] = {
    0.5e0f,   0.5e-1f,  0.5e-2f,  0.5e-3f,
    0.5e-4f,  0.5e-5f,  0.5e-6f,  0.5e-7f,
    0.5e-8f,  0.5e-9f,  0.5e-10f, 0.5e-11f,
    0.5e-12f, 0.5e-13f, 0.5e-14f, 0.5e-15f
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


typedef union {
    struct {
        uint64_t mantissa : 52;
        unsigned int exponent : 11;
        unsigned int sign : 1;
    } raw;
    double d;
} ieee754_double_union_t;

/* private function to deal with floating point special cases
 *   (nan, infinity, zero, negative)
 * returns number of chars written into buffer
 * if 'sign' is '+' or ' ', positive numbers are prefixed with 'sign'
 * negative numbers are always prefixed with '-'
 * if return value is 0 or 1, *value is positive and non-zero and the appropriate
 * prefix is in the buffer
 * if return value is greater than 1, value was zero, nan, or inf and the 
 * appropriate string is in the buffer
 * 'precision' and 'use_sci' describe the string to be output for zero
 * caller must ensure that the buffer can hold the specified representation
 * of zero, either '0.<precision>' or '0.<precision>e+0', as well as '-nan'
 * or '-inf'; this function does not know the buffer size
 */

static uint snprint_double_handle_special_cases(char *buf, double *value, uint precision, uint use_sci, char sign)
{
    uint len = 0;
    ieee754_double_union_t tmp;

    tmp.d = *value;
    if ( tmp.raw.sign ) {
        // negative
        tmp.raw.sign = 0;
        *value = tmp.d;
        buf[len++] = '-';
    } else {
        if ( ( sign == '+' ) || ( sign == ' ' ) ) {
            buf[len++] = sign;
        }
    }
    if ( tmp.raw.exponent == 0 ) {
#ifdef HANDLE_DENORM
        if ( tmp.raw.mantissa != 0 ) {
            len += snprint_string(buf+len, 7, "denorm");
        } else {
#endif
            buf[len++] = '0';
            if ( precision > 0 ) {
                buf[len++] = '.';
                while ( precision-- > 0 ) {
                    buf[len++] = '0';
                }
            }
            if ( use_sci ) {
                len += snprint_string(buf+len, 5u, "e+0");
            }
#ifdef HANDLE_DENORM
        }
#endif
    } else if ( tmp.raw.exponent == 0x7FF ) {
        if ( tmp.raw.mantissa != 0 ) {
            len += snprint_string(buf+len, 4u, "nan");
        } else {
            len += snprint_string(buf+len, 4u, "inf");
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
static uint snprint_double_helper(char *buf, uint size, double value, uint precision)
{
    uint len;
    uint32_t int_part;
#ifdef NEW_FRAC_PART
    uint digits;
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


uint snprint_double(char *buf, uint size, double value, uint precision, char sign)
{
    uint len;
    ieee754_double_union_t tmp;

    if ( precision > 15 ) {
        precision = 15;
    }
    /* check buffer size - worst case is '-' plus 10-digit integer
       plus '.' plus 'precision' trailing digits plus terminator */
    assert(size > (precision + 13));
    len = snprint_double_handle_special_cases(buf, &value, precision, 0, sign);
    if ( len > 1 ) return len;
    tmp.d = value;
    if ( ( tmp.raw.exponent > 1054 ) || ( tmp.raw.exponent < 1003 ) ) {
        // too large or too small for regular printing
        return len + snprint_double_sci(buf+len, size-len, value, precision, '\0');
    }
    // perform rounding to specified precision
    value = value + (double)round_factor[precision];
    // print it
    return len + snprint_double_helper(buf+len, size-len, value, precision);
}

uint snprint_double_sci(char *buf, uint size, double value, uint precision, char sign)
{
    uint len;
    int exponent;

    if ( precision > 15 ) {
        precision = 15;
    }
    /* check buffer size - worst case is '-' plus 1 digit plus '.' plus
       'precision' trailing digits plus 'e+123' plus terminator */
    assert(size > (precision + 9));
    len = snprint_double_handle_special_cases(buf, &value, precision, 1, sign);
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
    value = value + (double)round_factor[precision];
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


#ifdef PRINTING_TEST 
void (* print_char)(char c) = cons_tx_wait;
#else
void print_char(char c)
{
#ifdef PICO_BUILD
    putchar(c);
#else
    cons_tx_wait(c);
#endif
}
#endif


void print_string(const char *string)
{
    if ( string == NULL ) return;
    while ( *string != '\0' ) {
        print_char(*string);
        string++;
    }
}


void print_strings(uint num_strings, ...)
{
    va_list ap;

    va_start(ap, num_strings);
    for ( uint n = 0 ; n < num_strings ; n++ ) {
        print_string((char *)va_arg(ap, char *));
        }
    va_end(ap);
}


// private helper for printing repeated characters
// prints 'n' copies of 'c'
static void print_padding(uint n, char c)
{
    while ( n > 0 ) {
        print_char(c);
        n--;
    }
}

void print_string_width(char const *string, uint width, uint maxlen, char align)
{
    uint len;

    if ( string == NULL ) return;
    if ( maxlen <= 0 ) maxlen = 0x7FFFFFFF;
    len = 0;
    while ( string[len] != '\0' ) {
        len++;
    }
    if ( len > maxlen ) {
        len = maxlen;
    }
    if ( align == 'R' ) {
        print_padding(width-len, ' ');
    }
    for ( uint n = 0 ; n < len ; n++ ) {
        print_char(string[n]);
    }
    if ( align == 'L' ) {
        print_padding(width-len, ' ');
    }
}

void print_int_dec(int32_t value, char sign)
{
    char buffer[PRINT_INT_DEC_MAXLEN];
    snprint_int_dec(buffer, 16, value, sign);
    print_string(buffer);
}

void print_uint_dec(uint32_t value)
{
    char buffer[PRINT_UINT_DEC_MAXLEN];
    snprint_uint_dec(buffer, 16, value);
    print_string(buffer);
}

void print_uint_hex(uint32_t value, uint digits, uint group, uint uc)
{
    char buffer[PRINT_UINT_HEX_MAXLEN];
    snprint_uint_bin_hex(buffer, 20, value, 16, digits, group, uc);
    print_string(buffer);
}

void print_uint_bin(uint32_t value, uint digits, uint group)
{
    char buffer[PRINT_UINT_BIN_MAXLEN];
    snprint_uint_bin_hex(buffer, 68, value, 2, digits, group, 0);
    print_string(buffer);
}

void print_ptr(void const * ptr)
{
    print_uint_hex((uint32_t)ptr, 8, 0, 1);
}

void print_double(double value, uint precision, char sign)
{
    char buffer[PRINT_DOUBLE_MAXLEN];
    snprint_double(buffer, 32, value, precision, sign);
    print_string(buffer);
}

void print_double_sci(double value, uint precision, char sign)
{
    char buffer[PRINT_DOUBLE_SCI_MAXLEN];
    snprint_double_sci(buffer, 32, value, precision, sign);
    print_string(buffer);
}


// private helper for printf
static uint parse_uint(char const ** str)
{
  uint i = 0U;
  while ( (**str >= '0') && (**str <= '9') ) {
    i = i * 10U + (unsigned int)(*((*str)++) - '0');
  }
  return i;
}


// formatted printing
void printf_(char const *fmt, ...)
{
    va_list ap;
    uint loop, width, prec;
    char align, sign, pad;
    char buf[PRINT_UINT_BIN_MAXLEN];
    uint len;

    va_start(ap, fmt);
    while ( *fmt != '\0' ) {
        if ( *fmt != '%' ) {
            // print it verbatim
            print_char(*(fmt++));
            continue;
        }
        // '%' found
        // loop till all flags parsed
        loop = 1;
        align = 'R';
        sign = '\0';
        pad = ' ';
        do {
            // look at next char
            switch (*(++fmt)) {
            case '-':
                align = 'L';
                break;
            case '+':
                sign = '+';
                break;
            case ' ':
                if ( sign != '+' ) {
                    sign = ' ';
                }
                break;
            case '0':
                pad = '0';
                break;
            case '#':
            case '\'':
                break;
            default:
                loop = 0;
                break;
            }
        } while ( loop );
        width = 0;
        prec = ~0u;
        width = parse_uint(&fmt);
        if ( *fmt == '.' ) {
            fmt++;
            prec = parse_uint(&fmt);
        }
        len = 0;
        switch (*fmt) {
        case 'c':
            print_char((char)va_arg(ap, int));
            break;
        case 's':
            print_string_width((char *)va_arg(ap, char *), width, prec, align);
            break;
        case 'd':
            len = snprint_int_dec(buf, sizeof(buf), (int32_t)va_arg(ap, int32_t), sign);
            break;
        case 'u':
            len = snprint_uint_dec(buf, sizeof(buf), (uint32_t)va_arg(ap, uint32_t));
            break;
        case 'x':
            len = snprint_uint_hex(buf, sizeof(buf), (uint32_t)va_arg(ap, uint32_t), width, prec, 0);
            break;
        case 'X':
            len = snprint_uint_hex(buf, sizeof(buf), (uint32_t)va_arg(ap, uint32_t), width, prec, 1);
            break;
        case 'b':
            len = snprint_uint_bin(buf, sizeof(buf), (uint32_t)va_arg(ap, uint32_t), width, prec);
            break;
        case 'p':
            len = snprint_ptr(buf, sizeof(buf), (void *)va_arg(ap, void *));
            break;
        case 'f':
            if ( prec == ~0u ) prec = 8;
            len = snprint_double(buf, sizeof(buf), (double)va_arg(ap, double), prec, sign);
            break;
        case 'e':
            if ( prec == ~0u ) prec = 8;
            len = snprint_double_sci(buf, sizeof(buf), (double)va_arg(ap, double), prec, sign);
            break;
        default:
            print_char(*fmt);
            break;
        }
        if ( len > 0 ) {
            // there is something in the buffer to be printed
            if ( align == 'L' ) {
                // left align is simple, print buffer then pad with spaces
                print_string(buf);
                print_padding(width-len, ' ');
            } else {
                // right align, a bit more complex
                char *cp = buf;
                if ( pad == '0' ) {
                    // pad with leading zeros, need to print sign (if any) first,
                    // then the zeros, and finally the rest of the string
                    char c = *buf;
                    if ( ( c == '-' ) || ( c == '+' ) || ( c == ' ' ) ) {
                        // print sign, point to rest of string
                        print_char(c);
                        cp++;
                    }
                }
                print_padding(width-len, pad);
                print_string(cp);
            }
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
        print_uint_hex((uint32_t)row, 8, 0, 0);
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


