/***************************************************************
 * 
 * printing.h - lightweight console printing functions
 * 
 * this will eventually contains a lightweight printf() but for
 * now it is mostly individual functions for printing specific items
 * 
 * These functions are optimized to use minimum RAM; things are
 * sent to the console as early as possible instead of building
 * the complete string in a buffer.
 *
 * *************************************************************/

#ifndef PRINTING_H
#define PRINTING_H

#include <stdint.h>

// print a character
void print_char(char c);

// print a string, no truncation or padding
void print_string(const char *string);

// print a string with padding and/or truncation
//   pads to at least 'width' using spaces
//   truncates at maxlen unless maxlen = 0
void print_string_width(const char *string, int width, int maxlen);

// print a signed decimal integer
//   sign of '+' or ' ' is prefixed to positive numbers, any other
//   value means no prefix, '-' is always prefixed to negative 
void print_int_dec(int32_t n, char sign);

// print an unsigned decimal integer
void print_uint_dec(uint32_t n);

// print a hex integer
//   both versions work the same; the int version avoids a warning
//   displays low 'digits', with '-' separator after every 'group' digits
//   if uc is non-zero, uses upper case letters
void print_int_hex(int32_t n, int digits, int uc, int group);
void print_uint_hex(uint32_t n, int digits, int uc, int group);

// print a pointer
//   displays 8 hex digits
void print_ptr(void const * ptr);

// print a binary integer
//   both versions work the same; the int version avoids a warning
//   displays low 'digits'
//   if 'group' is non-zero, print a '-' between each 'group' bits
void print_int_bin(int32_t n, int digits, int group);
void print_uint_bin(uint32_t n, int digits, int group);

// print a floating point number in scientific notation
//   prints 'precision' digits after the decimal point
void print_double(double v, int precision);
void print_double_sci(double v, int precision);

// formatted printing
//   this is trimmed down printf, supports only the following:
//     %c, %s, %d, %x, %X, %p, %P
//     (eventually %f, %e, %g, but not yet)
//     adds %b (binary) which is not part of normal printf
//   does NOT return the number of characters or any error code
#define printf printf_
void printf_(char const *fmt, ...);

// memory dump
// prints 16 bytes per line, hex and ASCII
void print_memory(void const *mem, uint32_t len);



// these are newer, buffer based versions

// writes 'string' to 'buf', truncating if needed to fit in 'size'
// returns number of characters written, not including terminating '\0'
int snprint_string(char *buf, int size, const char *string);

// writes 'value' to 'buf' in decimal
// 'size' must be at least 12 characters (sign + 10 digits plus terminator)
// negative numbers always start with '-'; if 'sign' is '+' or ' ', positive
// numbers start with 'sign', otherwise positive numbers have no prefix.  
// returns number of characters written, not including terminating '\0'
int snprint_int_dec(char *buf, int size, int32_t value, char sign);

// writes 'value' to 'buf' in decimal
// 'size' must be at least 11 characters (10 digits plus terminator)
// returns number of characters written, not including terminating '\0'
int snprint_uint_dec(char *buf, int size, uint32_t value);

// writes least significant 'digits' of 'value' to 'buf' in hex
// 'size' must be at least big enough to hold digits and group separators
// a size of 17 characters is always big enough
// 'digits' can be 1-8, other values become 8; always shows the
// requested number of digits, leading zeros are always displayed
// if 'uc' is non-zero, uses uppercase for a-f
// if 'group' is non-zero, inserts a '-' between each 'group' digits
// returns number of characters written, not including terminating '\0'
// the int version is exactly the same, but avoids a type conversion warning
int snprint_uint_hex(char *buf, int size, uint32_t value, int digits, int uc, int group);
int snprint_int_hex(char *buf, int size, int32_t value, int digits, int uc, int group);

// writes least significant 'digits' of 'value' to 'buf' in binary
// 'size' must be at least big enough to hold digits and group separators
// a size of 65 characters is always big enough
// 'digits' can be 1-32, other values become 32; always shows the
// requested number of digits, leading zeros are always displayed
// if 'group' is non-zero, inserts a '-' between each 'group' digits
// returns number of characters written, not including terminating '\0'
// the int version is exactly the same, but avoids a type conversion warning
int snprint_uint_bin(char *buf, int size, uint32_t value, int digits, int group);
int snprint_int_bin(char *buf, int size, int32_t value, int digits, int group);

// writes 'ptr' to 'buf' in hex
// 'size' must be at least 9 characters
// returns number of characters written, not including terminating '\0'
int snprint_ptr(char *buf, int size, void *ptr);



#endif // PRINTING_H