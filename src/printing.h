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

#define PRINTING_TEST

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
#define PRINT_INT_DEC_MAXLEN    (12)

/***************************************************************
 * writes 'value' to 'buf' in decimal
 * 'size' must be at least 11 (10 digits plus terminator)
 * returns number of characters written, not including terminating '\0'
 */
int snprint_uint_dec(char *buf, int size, uint32_t value);
#define PRINT_UINT_DEC_MAXLEN    (11)

/***************************************************************
 * writes least significant 'digits' of 'value' to 'buf' in hex
 * 'size' must be big enough to hold digits and group separators;
 * 16 bytes is always big enough (8 digits, 7 separators, terminator)
 * 'digits' can be 1-8, other values become 8; always shows the
 * requested number of digits (leading zeros are always displayed)
 * if 'group' is non-zero, inserts a '-' between each 'group' digits
 * if 'uc' is non-zero, uses uppercase for a-f
 * returns number of characters written, not including terminating '\0'
 */
int snprint_uint_hex(char *buf, int size, uint32_t value, int digits, int group, int uc);
#define PRINT_UINT_HEX_MAXLEN    (16)

/***************************************************************
 * writes least significant 'digits' of 'value' to 'buf' in binary
 * 'size' must be big enough to hold digits and group separators;
 * 64 bytes is always big enough, (32 bits, 31 separators, terminator)
 * or 33 if 'group' = 0 (32 bits plus terminator)
 * 'digits' can be 1-32, other values become 32; always shows the
 * requested number of digits (leading zeros are always displayed)
 * if 'group' is non-zero, inserts a '-' between each 'group' digits
 * returns number of characters written, not including terminating '\0'
 */
int snprint_uint_bin(char *buf, int size, uint32_t value, int digits, int group);
#define PRINT_UINT_BIN_MAXLEN    (64)

/***************************************************************
 * writes 'ptr' to 'buf' in hex
 * 'size' must be at least 9 characters (8 digits + terminator)
 * returns number of characters written, not including terminating '\0'
 */
int snprint_ptr(char *buf, int size, void *ptr);
#define PRINT_PTR_MAXLEN    (9)

/***************************************************************
 * writes 'value' to 'buf' as a floating point number
 * 'size' must be big enough to hold the converted number
 * 28 bytes is always big enough (sign + 10 digits + '.' +
 * 'precision' fractional digits + terminator)
 * 'precision' digits are printed after the decimal point;
 * 'precision' can be 0-15, other values become 15
 * values larger than 2^32 or smaller than 1e-6 are printed
 * in scientific notation using snprint_double_sci()
 * negative numbers always start with '-'; if 'sign' is '+' or
 * ' ', positive numbers start with 'sign', otherwise positive
 * numbers have no prefix.  
 * returns number of characters written, not including terminating '\0'
 */
int snprint_double(char *buf, int size, double value, int precision, char sign);
#define PRINT_DOUBLE_MAXLEN    (28)

/***************************************************************
 * writes 'value' to 'buf' in scientific notation
 * 'size' must be big enough to hold the converted number
 * 24 bytes is always big enough (sign + 1 digit + '.' +
 * 'precision' fractional digits + 'e' + sign + 3 digit 
 * exponent + terminator)
 * 'precision' digits are printed after the decimal point;
 * 'precision' can be 0-15, other values become 15
 * negative numbers always start with '-'; if 'sign' is '+' or
 * ' ', positive numbers start with 'sign', otherwise positive
 * numbers have no prefix.  
 * returns number of characters written, not including terminating '\0'
 */
int snprint_double_sci(char *buf, int size, double value, int precision, char sign);
#define PRINT_DOUBLE_SCI_MAXLEN    (24)


/***************************************************************
 * sends 'c' to the console
 * all of the console printing functions in this header
 * eventually use print_char() to send their output
 */
#ifdef PRINTING_TEST 
extern void (* print_char)(char c);
#else
void print_char(char c);
#endif


/***************************************************************
 * sends 'string' to the console
 * no truncation or padding
 */
void print_string(const char *string);

/***************************************************************
 * print a string with padding and/or truncation
 *   truncates at maxlen unless maxlen = 0
 *   pads to at least 'width' using spaces
 *   if 'align' is 'R', prints padding, then string
 *   if 'align' is 'L', prints string, then padding
 */
void print_string_width(const char *string, int width, int maxlen, char align);

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
void print_double(double value, int precision, char sign);

/***************************************************************
 * sends 'value' to the console in scientific notation
 * 'precision' digits are printed after the decimal point;
 * 'precision' can be 0-15, other values become 15
 */
void print_double_sci(double value, int precision, char sign);


/***************************************************************
 * fprmatted printing
 *   this is a scaled down printf(), suppports only:
 *     %c, %s, %d, %u, %x, %X, %b, %p, %f, %e
 *   it does not support '*' for width or precision
 *   it parses but ignores the '#' alternate format flag
 *   it parses but ingores the "'" separator flag
 *   it neither parses nor supports the 'length' field
 *   toe followng formats vary from the standard:
 *     %x, %X  Ignores all flags.  Always prints leading zeros.
 *             Always prints 'width' digits; 'width' defaults 
 *             to 8 if not specified.  Prints in groups of  
 *             'precision' digits if 'precision' is specified.
 *     %b      Ignores all flags.  Always prints leading zeros.
 *             Always prints 'width' bits; 'width' defaults to
 *             32 if not specified.  Prints in groups of  
 *             'precision' bits if 'precision' is specified.
 *     %f      Uses scientific notation for numbers bigger than
 *             2^32 or smaller than approximately 1e-6
 * it does NOT return the number of characters or any error code
 */
#define printf printf_
void printf_(char const *fmt, ...);

// memory dump
// prints 16 bytes per line, hex and ASCII
void print_memory(void const *mem, uint32_t len);

#endif // PRINTING_H