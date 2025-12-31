/***************************************************************
 *
 * emblocs_comp.h - header for EMBLOCS components
 *
 * Embedded Block-Oriented Control System
 *
 *
 *
 **************************************************************/

#ifndef EMBLOCS_COMP_H
#define EMBLOCS_COMP_H

#include "emblocs_common.h"

#ifndef _countof
#define _countof(array) (sizeof(array)/sizeof(array[0]))
#endif

/***********************************************
 * error handling macros
 *
 * ERROR_RETURN(errno) sets bl_errno to 'errno'
 * and then either halts or returns 0 from the
 * containing function.
 *
 * CHECK_RETURN(checkval) assumes that 'checkval'
 * was returned from a function that uses these
 * macros.
 * If 'checkval' is false or NULL, it returns 0
 * from the containing function.
 *
 * CHECK_NULL(ptr) verifies a pointer.
 * If 'ptr' is NULL, it returns 0 from the
 * containing function.
 *
 * These macros are intended for use by component-
 * specific setup functions.
 *
 */
#ifdef BL_ERROR_HALT
#define ERROR_RETURN(errno) do { bl_errno = (errno); while (1); } while (0)
#define CHECK_RETURN(checkval) do {} while (0)  /* previous function would not return */
#else
#define ERROR_RETURN(errno) do { bl_errno = (errno); return 0; } while (0)
#define CHECK_RETURN(checkval) do { if ( 0 == (checkval) ) { return 0; } } while (0)
#endif

#ifdef BL_NULL_POINTER_CHECKS
#define CHECK_NULL(ptr) do { if ( NULL == (ptr) ) { ERROR_RETURN(BL_ERR_NULL_PTR); } } while (0)
#else
#define CHECK_NULL(ptr)
#endif

/**************************************************************
 * Each block has internal data which is in the RT memory pool.
 * The block data size is specified in bytes, and the size
 * is stored in a bitfield.
 */
#ifndef BL_BLOCK_DATA_SIZE_BITS
#define BL_BLOCK_DATA_SIZE_BITS  10
#endif

#define BL_BLOCK_DATA_MAX_SIZE (1<<(BL_BLOCK_DATA_SIZE_BITS))
#define BL_BLOCK_DATA_SIZE_MASK ((BL_BLOCK_DATA_MAX_SIZE)-1)

/* masks 'size' so it can go into a bit field without a conversion warning */
#define TO_BLOCK_SIZE(size) ((size) & BL_BLOCK_DATA_SIZE_MASK)

/* A field in the component definition determines whether the
 * component needs personality data */
typedef enum {
    BL_NO_PERSONALITY = 0,
    BL_NEEDS_PERSONALITY = 1
} bl_personality_t;

#define BL_PERSONALITY_FLAG_BITS (BITS2STORE(BL_NEEDS_PERSONALITY))

/* pin count (number of pins in a block)
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

/**************************************************************
 * The following data structures are used by components to    *
 * describe themselves and allow blocks (component instances) *
 * to be created.  Most of them typically live in flash.      *
 **************************************************************/

/**************************************************************
 * Data structure that defines a component.  These typically
 * exist in flash, but in theory could be built on-the-fly in
 * RAM.  Blocks are created using the data in a component
 * definition plus an optional personality that can customize
 * the basic component.
 * If 'setup' is NULL, then bl_block_new() will call
 * 'bl_default_setup()' to create block using only the data
 * in the component definition.
 * Otherwise, bl_block_new() will call setup(), which
 * should parse 'personality' as needed and create the block
 * by calling the helper functions defined later.
 */

typedef struct bl_comp_def_s {
    char const *name;
    struct bl_block_meta_s  * (*setup) (char const *block_name, struct bl_comp_def_s const *comp_def, void const *personality);
    uint32_t data_size          : BL_BLOCK_DATA_SIZE_BITS;
    uint32_t needs_pers         : BL_PERSONALITY_FLAG_BITS;
    uint32_t num_pin_defs       : BL_PIN_COUNT_BITS;
    uint32_t num_function_defs  : BL_FUNCTION_COUNT_BITS;
    struct bl_pin_def_s const *pin_defs;
    struct bl_function_def_s const *function_defs;
} bl_comp_def_t;

/* Verify that bitfields fit in one uint32_t */
_Static_assert((BL_BLOCK_DATA_SIZE_BITS+BL_PERSONALITY_FLAG_BITS+\
                BL_PIN_COUNT_BITS+BL_FUNCTION_COUNT_BITS) <= 32, "comp_def bitfields too big");

/**************************************************************
 * Data structure that defines a pin.  These can exist in flash
 * or RAM.  For a component with a fixed pin list, an array
 * of these structures in flash can be pointed at by the
 * component definition.  For components with personality, the
 * init() function can set the fields of one (or more) of these
 * structs in RAM (probably a local variable on stack), then
 * pass it to bl_pin_new() to create the pin.
 * The data offset is in bytes from the beginning of the block
 * data, so the standard offsetof() can be used to set it.
 */

typedef struct bl_pin_def_s {
    char const *name;
    uint32_t data_type    : BL_TYPE_BITS;
    uint32_t pin_dir      : BL_DIR_BITS;
    uint32_t data_offset  : BL_BLOCK_DATA_SIZE_BITS;
} bl_pin_def_t;

/* Verify that bitfields fit in one uint32_t */
_Static_assert((BL_BLOCK_DATA_SIZE_BITS+BL_TYPE_BITS+BL_DIR_BITS) <= 32, "pin_def bitfields too big");

/**************************************************************
 * A realtime function to be called from a thread.
 * The function is passed a pointer to the block data
 * and the calling period in nano-seconds.
 */
typedef void (bl_rt_function_t)(void *block_data, uint32_t period_ns);

/**************************************************************
 * Data structure that defines a realtime function.
 * For components that have realtime functions, an array of
 * these structures in flash is pointed to by the component
 * definition.
 */
typedef struct bl_function_def_s {
    char const *name;
    uint32_t nofp         : BL_NOFP_BITS;
    bl_rt_function_t *fp;
} bl_function_def_t;

/* Verify that bitfields fit in one uint32_t */
_Static_assert((BL_NOFP_BITS) <= 32, "function_def bitfields too big");

/**************************************************************
 * Helper functions for bl_block_new()
 * The following functions are called from bl_default_setup()
 * or from a component-specific setup() function to perform
 * various steps in the process of creating a new block
 */

 /**************************************************************
 * Helper function to create a block (instance of a component)
 * using only the component definition.
 */
struct bl_block_meta_s *bl_default_setup(char const *name, bl_comp_def_t const *comp_def);

/**************************************************************
 * Helper function to create a new block and reserve RAM
 * for its data.
 * If 'data_size' is zero, the size of the block data will
 * be based on the component definition; this happens when
 * called from bl_default_setup().  If 'data_size' is non-zero,
 * it overrides the size in the component definition.  This
 * allows a component-specific setup function to modify the
 * size based on the block personality.
 */
struct bl_block_meta_s *bl_block_create(char const *name, bl_comp_def_t const *comp_def, uint32_t data_size);

/**************************************************************
 * Helper function to get the address of the block data
 * for a particular block
 */  
void *bl_block_data_addr(struct bl_block_meta_s *blk);

/**************************************************************
 * Helper functions for new block:
 */

/* Adds a pin as defined by 'def' to block 'blk'
 * allocates a new bl_pin_meta_t struct in meta RAM 
 * allocates a dummy signal in RT ram
 * fills in all fields in the meta struct
 * links the pin to the dummy signal
 * adds the meta struct to 'blk' pin list
 */
bool bl_block_add_pin(struct bl_block_meta_s *blk, bl_pin_def_t const *def);

/* Adds all pins defined by 'def' to block 'blk'.
 * This function calls bl_block_add_pin() for each pin
 * definition in 'def'.  It is called by bl_default_setup()
 * and can be called from component-specific setup functions.
 */
bool bl_block_add_pins(struct bl_block_meta_s *blk, bl_comp_def_t const *def);

/* Adds a function as defined by 'def' to block 'blk'
 * allocates a new bl_function_meta_t struct in meta RAM
 * allocates a bl_function_rtdata_t struct in RT ram
 * fills in all fields in both structures
 * links the meta struct to the rtdata struct
 * adds the meta struct to 'blk' function list
 */
bool bl_block_add_function(struct bl_block_meta_s *blk, bl_function_def_t const *def);

/* Adds all functions defined by 'def' to block 'blk'.
 * This function calls bl_block_add_function() for each
 * function definition in 'def'.  It is called by
 * bl_default_setup() and can be called from component-
 * specific setup functions.
 */
bool bl_block_add_functions(struct bl_block_meta_s *blk, bl_comp_def_t const *def);

#endif // EMBLOCS_COMP_H
