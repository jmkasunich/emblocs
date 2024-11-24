/***************************************************************
 * 
 * emblocs.h - headers for EMBLOCS
 * 
 * Embedded Block-Oriented Control System
 * 
 * 
 * 
 * *************************************************************/

#ifndef EMBLOCS_H
#define EMBLOCS_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

typedef enum {
	BL_PINTYPE_FLOAT    = 0x00,
	BL_PINTYPE_BIT      = 0x01,
	BL_PINTYPE_SINT     = 0x02,
	BL_PINTYPE_UINT     = 0x03
} bl_pintype_t;

#define BL_PINTYPE_MASK (0x03)

typedef enum {
	BL_PINDIR_IN        = 0x04,
	BL_PINDIR_OUT       = 0x08,
	BL_PINDIR_IO        = 0x0C,
} bl_pindir_t;

#define BL_PINDIR_MASK (0x0C)

typedef float bl_float_t;
typedef bool bl_bit_t;
typedef int32_t bl_s32_t;
typedef uint32_t bl_u32_t;

typedef union {
	bl_float_t f;
	bl_bit_t b;
	bl_s32_t s;
	bl_u32_t u;
} bl_data_t;

typedef struct {
	bl_pintype_t type;
	bl_pindir_t dir;
	const char *name;
} bl_pindef_t;






// component definition


// component instance


// pin definition


// pin instance w/metadata


// pin instance (functional only)


// signal 


/***********************************************************/

// functions




#endif // EMBLOCS_H