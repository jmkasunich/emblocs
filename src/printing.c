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

// print an unsigned decimal integer
void print_uint_dec(uint32_t n, int width)
{
    print_dec(n, width, '\0');
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





