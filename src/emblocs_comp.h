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

#include "emblocs_core.h"

#ifndef _countof
#define _countof(array) (sizeof(array)/sizeof(array[0]))
#endif

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

/**************************************************************
 * The following data structures are used by components to    *
 * describe themselves and allow component instances to be    *
 * created.  Most of them typically live in FLASH memory.     *
 **************************************************************/

/**************************************************************
 * Data structure that defines a component.  These typically
 * exist in flash, but in theory could be built on-the-fly in
 * RAM.  Component instances are created using the data in a
 * component definition plus an optional personality that can
 * customize the basic component.
 * If 'setup' is NULL, then bl_instance_new() will call
 * 'bl_default_setup()' to create an instance of the component
 * using only the data in the component definition.
 * Otherwise, bl_instance_new() will call setup(), which
 * should parse 'personality' as needed and create the instance
 * by calling the helper functions defined later.
 */

typedef struct bl_comp_def_s {
    char const *name;
    struct bl_instance_meta_s * (*setup) (char const *instance_name, struct bl_comp_def_s const *comp_def, void const *personality);
    uint32_t data_size   : BL_INSTANCE_DATA_SIZE_BITS;
    uint32_t pin_count   : BL_PIN_COUNT_BITS;
    uint32_t function_count : BL_FUNCTION_COUNT_BITS;
    struct bl_pin_def_s const *pin_defs;
    struct bl_function_def_s const *function_defs;
} bl_comp_def_t;

/* Verify that bitfields fit in one uint32_t */
_Static_assert((BL_INSTANCE_DATA_SIZE_BITS+BL_PIN_COUNT_BITS+BL_FUNCTION_COUNT_BITS) <= 32, "comp_def bitfields too big");

/**************************************************************
 * Data structure that defines a pin.  These can exist in flash
 * or RAM.  For a component with a fixed pin list, an array
 * of these structures in flash can be pointed at by the
 * component definition.  For components with personality, the
 * init() function can set the fields of one (or more) of these
 * structs in RAM (probably a local variable on stack), then
 * pass it to bl_pin_new() to create the pin.
 * The data offset is in bytes from the beginning of the instance
 * data, so the standard offsetof() can be used to set it.
 */

typedef struct bl_pin_def_s {
    char const *name;
    uint32_t data_type    : BL_TYPE_BITS;
    uint32_t pin_dir      : BL_DIR_BITS;
    uint32_t data_offset  : BL_INSTANCE_DATA_SIZE_BITS;
} bl_pin_def_t;

/* Verify that bitfields fit in one uint32_t */
_Static_assert((BL_INSTANCE_DATA_SIZE_BITS+BL_TYPE_BITS+BL_DIR_BITS) <= 32, "pin_def bitfields too big");

/**************************************************************
 * A realtime function to be called from a thread.
 * The function is passed a pointer to the instance data
 * and the calling period in nano-seconds.
 */
typedef void (bl_rt_function_t)(void *instance_data, uint32_t period_ns);

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
 * Helper functions for bl_instance_new()
 * The following functions are called from bl_default_setup()
 * or from a component-specific setup() function to perform
 * various steps in the process of creating a new component
 * instance
 */

/**************************************************************
 * Helper function to create a new instance and reserve RAM
 * for its instance data.  
 * If 'data_size' is zero, the size of the instance data will
 * be based on the component definition; this happens when
 * called from bl_default_setup().  If 'data_size' is non-zero,
 * it overrides the size in the component definition.  This
 * allows a component-specific setup function to modify the
 * size based on the instance personality.
 */
struct bl_instance_meta_s *bl_instance_create(char const *name, bl_comp_def_t const *comp_def, uint32_t data_size);

/**************************************************************
 * Helper function to get the address of the instance data
 * for a particular instance
 */  
void *bl_instance_data_addr(struct bl_instance_meta_s *inst);

/**************************************************************
 * Helper functions for new instance:
 */

/* Adds a pin as defined by 'def' to instance 'inst'
 * allocates a new bl_pin_meta_t struct in meta RAM 
 * allocates a dummy signal in RT ram
 * fills in all fields in the meta struct
 * links the pin to the dummy signal
 * adds the meta struct to 'inst' pin list
 */
bool bl_instance_add_pin(struct bl_instance_meta_s *inst, bl_pin_def_t const *def);

/* Adds all pins defined by 'def' to instance 'inst'.
 * This function calls bl_instance_add_pin() for each pin
 * definition in 'def'.  It is called by bl_default_setup()
 * and can be called from component-specific setup functions.
 */
bool bl_instance_add_pins(struct bl_instance_meta_s *inst, bl_comp_def_t const *def);

/* Adds a function as defined by 'def' to instance 'inst'
 * allocates a new bl_function_meta_t struct in meta RAM
 * allocates a bl_function_rtdata_t struct in RT ram
 * fills in all fields in both structures
 * links the meta struct to the rtdata struct
 * adds the meta struct to 'inst' function list
 */
bool bl_instance_add_function(struct bl_instance_meta_s *inst, bl_function_def_t const *def);

/* Adds all functions defined by 'def' to instance 'inst'.
 * This function calls bl_instance_add_function() for each
 * function definition in 'def'.  It is called by
 * bl_default_setup() and can be called from component-
 * specific setup functions.
 */
bool bl_instance_add_functions(struct bl_instance_meta_s *inst, bl_comp_def_t const *def);

#endif // EMBLOCS_COMP_H
