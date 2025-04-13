/***************************************************************
 *
 * str_to_xx.h - lightweight string conversion functions
 *
 * This module contains functions that convert strings to
 * other types such as integers and floats.  Their API is
 * not the same as the C standard library strtod, etc.
 *
 * They accept a pointer to the string and a pointer to the
 * destination (which can be NULL, see below).
 *
 * If the _entire_ string was successfully converted, they
 * return true and set the destination to the converted value.
 * If the destination was NULL, they simply indicate that the
 * string could be converted to the target type.
 * If the string could not be converted, they return false
 * and do not change the destination.
 *
 * These functions do not strip leading and trailing white-
 * space; I often used them on tokens that never had any
 * whitespace.  Whitespace anywhere in the string causes
 * these functions to return false.
 *
 **************************************************************/
#ifndef STR_TO_XX_H
#define STR_TO_XX_H

#include <stdint.h>    // int32_t, uint32_t
#include <stdbool.h>   // bool, true, false
#include <stddef.h>    // offsetof(), NULL

bool str_to_bool(char const * str, bool *dest);
bool str_to_u32(char const *str, uint32_t *dest);
bool str_to_s32(char const *str, int32_t *dest);
bool str_to_float(char const *str, float *dest);

#endif // STR_TO_XX_H