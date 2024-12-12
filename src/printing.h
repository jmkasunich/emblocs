/***************************************************************
 * 
 * printing.h - lightweight console printing functions
 * 
 *
 * This module contains two kinds of functions:
 *   snprint_xxxx(buf, size, ...) functions generate their
 *     output in the supplied buffer, and return the number
 *     of characters generated.
 *   print_xxxx(...) functions send their output to the 
 *     console UART and return nothing.  For the most part,
 *     they call their snprint counterparts, then print the
 *     resulting string.
 * 
 * The 'snprint' functions mostly use assert() to check buffer
 * sizes; if assert() is disabled buffer overruns are possible.
 * 
 * When the console printing functions call their 'snprint' 
 * counterparts, they allocate suitable buffers on the stack;
 * they should never assert or overflow.
 *
 **************************************************************/

#ifndef PRINTING_H
#define PRINTING_H

#include <stdint.h>

/***************************************************************
 * writes 'string' to 'buf', truncating if needed to fit in 'size'
 * returns number of characters written, not including terminating '\0'
 */
int snprint_string(char *buf, int size, const char *string);

/***************************************************************
 * writes 'value' to 'buf' in decimal
 * 'size' must be at least 12 (sign + 10 digits plus terminator)
 * negative numbers always start with '-'; if 'sign' is '+' or
 * ' ', positive numbers start with 'sign', otherwise positive
 * numbers have no prefix.  
 * returns number of characters written, not including terminating '\0'
 */
int snprint_int_dec(char *buf, int size, int32_t value, char sign);

/***************************************************************
 * writes 'value' to 'buf' in decimal
 * 'size' must be at least 11 (10 digits plus terminator)
 * returns number of characters written, not including terminating '\0'
 */
int snprint_uint_dec(char *buf, int size, uint32_t value);

/***************************************************************
 * writes least significant 'digits' of 'value' to 'buf' in hex
 * 'size' must be big enough to hold digits and group separators;
 * 17 bytes is always big enough
 * 'digits' can be 1-8, other values become 8; always shows the
 * requested number of digits (leading zeros are always displayed)
 * if 'group' is non-zero, inserts a '-' between each 'group' digits
 * if 'uc' is non-zero, uses uppercase for a-f
 * returns number of characters written, not including terminating '\0'
 */
int snprint_uint_hex(char *buf, int size, uint32_t value, int digits, int group, int uc);

/***************************************************************
 * writes least significant 'digits' of 'value' to 'buf' in binary
 * 'size' must be big enough to hold digits and group separators;
 * 65 bytes is always big enough, or 34 if 'group' = 0
 * 'digits' can be 1-32, other values become 32; always shows the
 * requested number of digits (leading zeros are always displayed)
 * if 'group' is non-zero, inserts a '-' between each 'group' digits
 * returns number of characters written, not including terminating '\0'
 */
int snprint_uint_bin(char *buf, int size, uint32_t value, int digits, int group);

/***************************************************************
 * writes 'ptr' to 'buf' in hex
 * 'size' must be at least 9 characters
 * returns number of characters written, not including terminating '\0'
 */
int snprint_ptr(char *buf, int size, void *ptr);

/***************************************************************
 * writes 'value' to 'buf' as a floating point number
 * 'size' must be big enough to hold the converted number
 * 30 bytes is always big enough
 * 'precision' digits are printed after the decimal point;
 * 'precision' can be 0-15, other values become 15
 * values larger than 2^32 or smaller than 1e-6 are printed
 * in scientific notation using snprint_double_sci()
 * returns number of characters written, not including terminating '\0'
 */
int snprint_double(char *buf, int size, double value, int precision);

/***************************************************************
 * writes 'value' to 'buf' in scientific notation
 * 'size' must be big enough to hold the converted number
 * 25 bytes is always big enough
 * 'precision' digits are printed after the decimal point;
 * 'precision' can be 0-15, other values become 15
 * returns number of characters written, not including terminating '\0'
 */
int snprint_double_sci(char *buf, int size, double value, int precision);




/***************************************************************
 * sends 'c' to the console
 * all of the console printing functions in this header
 * eventually use print_char() to send their output
 */
void print_char(char c);

/***************************************************************
 * sends 'string' to the console
 * no truncation or padding
 */
void print_string(const char *string);

/***************************************************************
 * sends 'value' to the console as a decimal integer
 * negative numbers always start with '-'; if 'sign' is '+' or
 * ' ', positive numbers start with 'sign', otherwise positive
 * numbers have no prefix.
 */
void print_int_dec(int32_t value, char sign);

/***************************************************************
 * sends 'value' to the console as an unsigned decimal integer
 */
void print_uint_dec(uint32_t value);

/***************************************************************
 * sends 'value' to the console as hexadecimal
 * 'digits' can be 1-8, other values become 8; always shows the
 * requested number of digits (leading zeros are always displayed)
 * if 'group' is non-zero, inserts a '-' between each 'group' digits
 * if 'uc' is non-zero, uses uppercase for a-f
 */
void print_uint_hex(uint32_t value, int digits, int group, int uc);

/***************************************************************
 * sends 'value' to the console as binary
 * 'digits' can be 1-32, other values become 32; always shows the
 * requested number of digits (leading zeros are always displayed)
 * if 'group' is non-zero, inserts a '-' between each 'group' digits
 */
void print_uint_bin(uint32_t value, int digits, int group);

/***************************************************************
 * sends 'ptr' to the console as 8 hex digits
 */
void print_ptr(void const * ptr);

/***************************************************************
 * sends 'value' to the console as a floating point number
 * 'precision' digits are printed after the decimal point;
 * 'precision' can be 0-15, other values become 15
 * values larger than 2^32 or smaller than 1e-6 are printed
 * in scientific notation using print_double_sci()
 */
void print_double(double value, int precision);

/***************************************************************
 * sends 'value' to the console in scientific notation
 * 'precision' digits are printed after the decimal point;
 * 'precision' can be 0-15, other values become 15
 */
void print_double_sci(double value, int precision);


// formatted printing
//   this is trimmed down printf, supports only the following:
//     %c, %s, %d, %x, %X, %p, %P
//     (eventually %f, %e, %g, but not yet)
//     adds %b (binary) which is not part of normal printf
//   does NOT return the number of characters or any error code
#define printf printf_
void printf_(char const *fmt, ...);

// print a string with padding and/or truncation
//   pads to at least 'width' using spaces
//   truncates at maxlen unless maxlen = 0
void print_string_width(const char *string, int width, int maxlen);

// memory dump
// prints 16 bytes per line, hex and ASCII
void print_memory(void const *mem, uint32_t len);


void pow_test(void);


#endif // PRINTING_H