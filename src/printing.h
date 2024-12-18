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
//   always displays the whole number even if width is smaller
//   sign of '+' or ' ' is prefixed to positive numbers, any other
//   value means no prefix, '-' is always prefixed to negative 
void print_int_dec(int32_t n, int width, char sign);

// print an unsigned decimal integer
//   always displays the whole number even if width is smaller
void print_uint_dec(uint32_t n, int width);

// print a hex integer
//   both versions work the same; the int version avoids a warning
//   displays low 'digits', left padded with space to 'width'
//   if uc is non-zero, uses upper case letters
void print_int_hex(int32_t n, int width, int digits, int uc);
void print_uint_hex(uint32_t n, int width, int digits, int uc);

// print a pointer
//   displays 8 hex digits, left padded with space to 'width'
void print_ptr(void const * ptr, int width);

// print a binary integer
//   both versions work the same; the int version avoids a warning
//   displays low 'digits', left padded with space to 'width'
//   if 'group' is non-zero, print a . between each 'group' bits
void print_int_bin(int32_t n, int width, int digits, int group);
void print_uint_bin(uint32_t n, int width, int digits, int group);

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

#endif // PRINTING_H