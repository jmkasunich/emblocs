/***************************************************************
 *
 * emblocs_core.h - header for EMBLOCS core
 *
 * Embedded Block-Oriented Control System
 *
 *
 *
 **************************************************************/

#ifndef EMBLOCS_CORE_H
#define EMBLOCS_CORE_H

#include "emblocs_config.h"

#include <stdint.h>    // int32_t, uint32_t
#include <stdbool.h>   // bool, true, false
#include <stddef.h>    // offsetof(), NULL

/* some basic assumptions */
_Static_assert(sizeof(int) == 4, "ints must be 32 bits");
_Static_assert(sizeof(void *) == 4, "pointers must be 32 bits");

/* the four pin/signal data types */
typedef float       bl_float_t;
typedef bool        bl_bit_t;
typedef int32_t     bl_s32_t;
typedef uint32_t    bl_u32_t;

/* "generic" data; implemented as a union of the four types */
typedef union bl_sig_data_u {
    bl_bit_t        b;
    bl_float_t      f;
    bl_s32_t        s;
    bl_u32_t        u;
} bl_sig_data_t;

/* pins are pointers to their respective data types */
typedef bl_bit_t    *bl_pin_bit_t;
typedef bl_float_t  *bl_pin_float_t;
typedef bl_s32_t    *bl_pin_s32_t;
typedef bl_u32_t    *bl_pin_u32_t;

/* "generic" pin is a pointer to generic data */
typedef bl_sig_data_t *bl_pin_t;

/* return values for API functions */
typedef enum {
    BL_SUCCESS = 0,
    BL_ERR_GENERAL = -1,
    BL_ERR_TYPE_MISMATCH = -2,
    BL_ERR_NOT_FOUND = -3,
    BL_ERR_NOMEM = -4
} bl_retval_t;

/* macro to calculate the size of bitfield needed to store 'n' */
#define BITS2STORE(n) (32-(__builtin_clz((n))))

/**************************************************************
 * Data types for pins and signals. 
 */

 typedef enum {
	BL_TYPE_FLOAT    = 0,
	BL_TYPE_BIT      = 1,
	BL_TYPE_S32      = 2,
	BL_TYPE_U32      = 3
} bl_type_t;

/* type is sometimes stored in a bitfield; declare its size */
#define BL_TYPE_BITS   (BITS2STORE(BL_TYPE_U32))

/**************************************************************
 * Data directions for pins.
 */

typedef enum {
	BL_DIR_IN        = 1,
	BL_DIR_OUT       = 2,
	BL_DIR_IO        = 3,
} bl_dir_t;

/* dir is sometimes stored in a bitfield; declare its size */
#define BL_DIR_BITS   (BITS2STORE(BL_DIR_IO))

/**************************************************************
 * Floating point info for threads and functions.  Threads
 * defined as "no_fp" can contain only functions which are
 * also defined as "no_fp".
 */

typedef enum {
	BL_HAS_FP        = 0,
	BL_NO_FP         = 1
} bl_nofp_t;

/* nofp is sometimes stored in a bitfield; declare its size */
#define BL_NOFP_BITS   (BITS2STORE(BL_NO_FP))

/**************************************************************
 * Structures that store object metadata.
 * API functions pass and return pointers to these structures,
 * but the internal data is private and not declared here.
 */
struct bl_instance_meta_s;
struct bl_pin_meta_s;
struct bl_function_def_s;
struct bl_signal_meta_s;
struct bl_thread_meta_s;
struct bl_thread_data_s;

/**************************************************************
 * Each instance of a component has "instance data" which is
 * in the RT memory pool.  The instance data size is specified
 * in bytes, and the size is stored in a bitfield.
 */

#ifndef BL_INSTANCE_DATA_SIZE_BITS
#define BL_INSTANCE_DATA_SIZE_BITS  10
#endif

#define BL_INSTANCE_DATA_MAX_SIZE (1<<(BL_INSTANCE_DATA_SIZE_BITS))
#define BL_INSTANCE_DATA_SIZE_MASK ((BL_INSTANCE_DATA_MAX_SIZE)-1)

/* masks 'size' so it can go into a bit field without a conversion warning */
#define TO_INSTANCE_SIZE(size) ((size) & BL_INSTANCE_DATA_SIZE_MASK)


/* pin count (number of pins in a component instance)
 * is stored in bitfields, need to specify the size
 */
#ifndef BL_PIN_COUNT_BITS
#define BL_PIN_COUNT_BITS 8
#endif

#define BL_PIN_COUNT_MAX (1<<(BL_PIN_COUNT_BITS))

/* the number of functions provided by a component
 * is stored in bitfields, need to specify the size
 */
#ifndef BL_FUNCTION_COUNT_BITS
#define BL_FUNCTION_COUNT_BITS 3
#endif

#define BL_FUNCTION_COUNT_MAX (1<<(BL_FUNCTION_COUNT_BITS))

#endif // EMBLOCS_CORE_H
