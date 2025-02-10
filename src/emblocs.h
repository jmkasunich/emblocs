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

#define INIT_BY_NET

/* some basic assumptions */
_Static_assert(sizeof(int) == 4, "ints must be 32 bits");
_Static_assert(sizeof(void *) == 4, "pointers must be 32 bits");

#ifndef _countof
#define _countof(array) (sizeof(array)/sizeof(array[0]))
#endif

typedef enum {
    BL_SUCCESS = 0,
    BL_TYPE_MISMATCH = -1,
    BL_INST_NOT_FOUND = -2,
    BL_PIN_NOT_FOUND = -3,
    BL_SIG_NOT_FOUND = -4
} bl_retval_t;

/*************************************************************
 * Realtime data and object metadata are stored in separate
 * memory pools, the RT pool and the META pool.  Each pool is
 * an array of uint32_t, and in the metadata, pool addresses 
 * are stored as array indexes in bitfields.  As an example,
 * if a pool is 4K bytes, indexes range from 0 to 1023, and
 * they can be stored in a 10 bit field.
 * 
 * If a pool size is intended to be a power of two, simply 
 * define the number of index bits, and the pool size will
 * be computed at compile time.  If the pool size is not a
 * power of two, define both the number of index bits and
 * the pool size in bytes.
 */

/* default index sizes if not defined elsewhere */
#ifndef BL_RT_INDEX_BITS
#define BL_RT_INDEX_BITS  9
#endif

#ifndef BL_META_INDEX_BITS
#define BL_META_INDEX_BITS  9
#endif

/* default to power of two sizes if not defined elsewhere */
#ifndef BL_RT_POOL_SIZE
#define BL_RT_POOL_SIZE (4<<(BL_RT_INDEX_BITS))
#endif

#ifndef BL_META_POOL_SIZE
#define BL_META_POOL_SIZE  (4<<(BL_META_INDEX_BITS))
#endif

/* These asserts verify that the specified number of bits can 
   be used to address the specified pool size. */
_Static_assert((4<<(BL_RT_INDEX_BITS)) >= (BL_RT_POOL_SIZE), "not enough RT index bits");
_Static_assert((4<<(BL_META_INDEX_BITS)) >= (BL_META_POOL_SIZE), "not enough meta index bits");

/* A couple of other constants based on pool size */
#define BL_RT_INDEX_MASK ((1<<(BL_RT_INDEX_BITS))-1)
#define BL_META_INDEX_MASK ((1<<(BL_META_INDEX_BITS))-1)


/*************************************************************
 * Each instance of a component has "instance data" which is
 * in the RT memory pool.  The instance data size is specified
 * in bytes, and the size is stored in a bitfield.
 */

#ifndef BL_INST_DATA_SIZE_BITS
#define BL_INST_DATA_SIZE_BITS  10
#endif

#define BL_INST_DATA_MAX_SIZE (1<<(BL_INST_DATA_SIZE_BITS))
#define BL_INST_DATA_SIZE_MASK ((BL_INST_DATA_MAX_SIZE)-1)

/* pin counts are stored in bitfields, need to specify the size */
#ifndef BL_PIN_COUNT_BITS
#define BL_PIN_COUNT_BITS 8
#endif

/*************************************************************
 * Data types for pins and signals.  Stored in bitfields, so
 * we need to specify the bitfield length as well as the enum.
 */

typedef enum {
	BL_TYPE_FLOAT    = 0,
	BL_TYPE_BIT      = 1,
	BL_TYPE_S32      = 2,
	BL_TYPE_U32      = 3
} bl_type_t;

#define BL_TYPE_BITS 2


/*************************************************************
 * Data directions for pins.  Stored in bitfields, so we need
 * to specify the bitfield length as well as the enum.
 */

typedef enum {
	BL_DIR_IN        = 1,
	BL_DIR_OUT       = 2,
	BL_DIR_IO        = 3,
} bl_dir_t;

#define BL_DIR_BITS  2


/*************************************************************
 * Data structure that describes a component instance.
 * These structures live in the metadata pool, but point to
 * instance data in the realtime pool.
 * 'data_index' and 'data_size' refer to the realtime instance
 * data; size is in bytes, while index is a uint32_t offset from
 * the base of the RT pool.  'pin_list' is a list of pins that
 * belong to this specific instance; the full pin name must be
 * created by concatenating the instance name and pin name.
 * This structure is incomplete; it will eventually have function
 * data in it as well.
 */

typedef struct bl_inst_meta_s {
    struct bl_inst_meta_s *next;
    struct bl_comp_def_s const *comp_def;
    uint32_t data_index  : BL_RT_INDEX_BITS;
    uint32_t data_size   : BL_INST_DATA_SIZE_BITS;
    char const *name;
    struct bl_pin_meta_s *pin_list;
} bl_inst_meta_t;

/* Verify that bitfields fit in one uint32_t */
_Static_assert((BL_RT_INDEX_BITS+BL_INST_DATA_SIZE_BITS) <= 32, "instance bitfields too big");


/*************************************************************
 * Data structure that describes a pin.  Each instance has a
 * list of pins.  These structures live in the metadata pool,
 * but point to data in the realtime pool.
 */

typedef struct bl_pin_meta_s {
    struct bl_pin_meta_s *next;
    uint32_t ptr_index    : BL_RT_INDEX_BITS;
    uint32_t dummy_index  : BL_RT_INDEX_BITS;
    uint32_t data_type    : BL_TYPE_BITS;
    uint32_t pin_dir      : BL_DIR_BITS;
    char const *name;
} bl_pin_meta_t;

/* Verify that bitfields fit in one uint32_t */
_Static_assert((BL_RT_INDEX_BITS*2+BL_TYPE_BITS+BL_DIR_BITS) <= 32, "pin bitfields too big");


/*************************************************************
 * Data structure that describes a signal.  There is one list
 * of signals which lives in the metadata pool, but point to
 * data in the realtime pool.
 */

typedef struct bl_sig_meta_s {
    struct bl_sig_meta_s *next;
    uint32_t data_index   : BL_RT_INDEX_BITS;
    uint32_t data_type    : BL_TYPE_BITS;
    char const *sig_name;
} bl_sig_meta_t;

/* Verify that bitfields fit in one uint32_t */
_Static_assert((BL_RT_INDEX_BITS+BL_TYPE_BITS) <= 32, "sig bitfields too big");


/****************************************************************
 * the four pin/signal types
 */

typedef float bl_float_t;
typedef bool bl_bit_t;
typedef int32_t bl_s32_t;
typedef uint32_t bl_u32_t;

/* pins are pointers to their respective data types */

typedef bl_bit_t *bl_pin_bit_t;
typedef bl_float_t *bl_pin_float_t;
typedef bl_s32_t *bl_pin_s32_t;
typedef bl_u32_t *bl_pin_u32_t;

/* "generic" data and pins; implemented as a union of the four types */
typedef union bl_sig_data_u {
    bl_bit_t b;
    bl_float_t f;
    bl_s32_t s;
    bl_u32_t u;
} bl_sig_data_t;

typedef union bl_pin_u {
    bl_pin_bit_t b;
    bl_pin_float_t f;
    bl_pin_s32_t s;
    bl_pin_u32_t u;
} bl_pin_t;



/**********************************************************************************
 * Structures used to define component characteristics at compile time.
 *
 */


/*************************************************************
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
 * 
 */

typedef struct bl_comp_def_s {
    char const * const name;
    bl_inst_meta_t * (*setup) (char const *inst_name, struct bl_comp_def_s const *comp_def, void const *personality);
    uint32_t data_size   : BL_INST_DATA_SIZE_BITS;
    uint32_t pin_count   : BL_PIN_COUNT_BITS;

//    uint8_t const funct_count;
    struct bl_pin_def_s const *pin_defs;
//    struct bl_funct_def_s const *funct_defs;
} bl_comp_def_t;


/* Verify that bitfields fit in one uint32_t */
_Static_assert((BL_INST_DATA_SIZE_BITS+BL_PIN_COUNT_BITS) <= 32, "comp_def bitfields too big");


/*************************************************************
 * Data structure that defines a pin.  These can exist in flash
 * or RAM.  For a component with a fixed pin list, an array
 * of these structures in flash can be pointed at by the
 * component definition.  For components with personality, the
 * init() function can set the fields of one (or more) of these
 * structs in RAM (probably local variable on stack) and then
 * pass it/them to bl_pin_new() to drive the allocation of the
 * actual bl_pin_meta_t structures in RAM.
 * The data offset is in bytes from the beginning of the instance
 * data, so the standard offsetof() can be used to set it.
 */

typedef struct bl_pin_def_s {
    char const *name;
    uint32_t data_type    : BL_TYPE_BITS;
    uint32_t pin_dir      : BL_DIR_BITS;
    uint32_t data_offset  : BL_INST_DATA_SIZE_BITS;
} bl_pin_def_t;

/* Verify that bitfields fit in one uint32_t */
_Static_assert((BL_INST_DATA_SIZE_BITS+BL_TYPE_BITS+BL_DIR_BITS) <= 32, "pin_def bitfields too big");


#if 0

typedef struct bl_funct_def_s {
    char const * const name;
    void (*fp) (void *);
} bl_funct_def_t;


#endif

/**********************************************************************************
 * Top-level functions used to build a system
 *
 */


/*************************************************************
 * Creates an instance of a component, using a component 
 * definition (typically in flash) and an optional personality.
 */
bl_inst_meta_t *bl_instance_new(char const *name, bl_comp_def_t const *comp_def, void const *personality);


/*************************************************************
 * Creates a signal of the specified name and type
 */
bl_sig_meta_t *bl_signal_new(char const *name, bl_type_t type);

/*************************************************************
 * Links the specified instance/pin to the specified signal
 */
bl_retval_t bl_link_pin_to_signal_by_names(char const *inst_name, char const *pin_name, char const *sig_name );
bl_retval_t bl_link_pin_to_signal(bl_pin_meta_t *pin, bl_sig_meta_t *sig );


/*************************************************************
 * Disconnects the specified instance/pin from any signal
 */
bl_retval_t bl_unlink_pin_by_name(char const *inst_name, char const *pin_name);
void bl_unlink_pin(bl_pin_meta_t *pin);



/*************************************************************
 * Helper function for bl_instance_new(); creates an instance
 * of a component using only the component definition.
 */
bl_inst_meta_t *bl_default_setup(char const *name, bl_comp_def_t const *comp_def);


/*************************************************************
 * Helper functions for bl_instance_new()
 * The following functions are called from bl_default_setup()
 * or from a component-specific setup() function to perform
 * various steps in the process of creating a new component
 * instance
 */



/*************************************************************
 * Helper function to create a new instance and reserve RAM
 * for its instance data.  
 * If 'data_size' is zero, the size of the instance data will
 * be based on the component definition; this happens when
 * called from bl_default_setup().  If 'data_size' is non-zero,
 * it overrides the size in the component definition.  This
 * allows a component-specific setup function to modify the
 * size based on the instance personality.
 */
bl_inst_meta_t *bl_inst_create(char const *name, bl_comp_def_t const *comp_def, uint32_t data_size);


/*************************************************************
 * helper function for new instance:
 * adds a pin as defined by 'def' to instance 'inst'
 * allocates a new bl_pin_meta_t struct in meta RAM 
 * allocates a dummy signal in RT ram
 * fills in all fields in the meta struct
 * links the pin to the dummy signal
 * adds the meta struct to 'inst' pin list
 */
bl_pin_meta_t *bl_inst_add_pin(bl_inst_meta_t *inst, bl_pin_def_t const *def);

/**********************************************************************************
 * More helper functions
 *
 */

bl_inst_meta_t *bl_find_instance_by_name(char const *name);
bl_pin_meta_t *bl_find_pin_in_instance_by_name(char const *name, bl_inst_meta_t *inst);
bl_sig_meta_t *bl_find_signal_by_name(char const *name);
bl_sig_meta_t *bl_find_signal_by_index(uint32_t index);
void bl_find_pins_linked_to_signal(bl_sig_meta_t *sig, void (*callback)(bl_inst_meta_t *inst, bl_pin_meta_t *pin));



/**********************************************************************************
 * Introspection functions
 *
 */

void bl_show_memory_status(void);
void bl_show_instance(bl_inst_meta_t *inst);
void bl_show_all_instances(void);
void bl_show_pin(bl_pin_meta_t *pin);
void bl_show_all_pins_of_instance(bl_inst_meta_t *inst);
void bl_show_pin_value(bl_pin_meta_t *pin);
void bl_show_pin_linkage(bl_pin_meta_t *pin);
void bl_show_signal(bl_sig_meta_t *sig);
void bl_show_signal_value(bl_sig_meta_t *sig);
void bl_show_signal_linkage(bl_sig_meta_t *sig);
void bl_show_sig_data_t_value(bl_sig_data_t *data, bl_type_t type);
void bl_show_all_signals(void);


/* arrays that the application must supply to define the system */

typedef struct inst_def_s {
    char *name;
    bl_comp_def_t *comp_def;
    void *personality;
} bl_inst_def_t;

/* array listing all instances to be created */
extern bl_inst_def_t const bl_instances[];

#ifdef INIT_BY_NET
/* nets array consists of a series of strings defining nets
 * each net starts with the one of the type strings "FLOAT",
 * "BIT", "S32" or "U32", then the net name, followed by an
 * instance name and a pin name.  The pin name is followed 
 * by either another instance and pin name, or by a type 
 * string to start a new signal, or by NULL to end the list.
 */

extern char const * const bl_nets[];

#else  // not INIT_BY_NET

/* arrays listing all signals to be created */
extern char const * const bl_signals_float[];
extern char const * const bl_signals_bit[];
extern char const * const bl_signals_s32[];
extern char const * const bl_signals_u32[];

typedef struct link_def_s {
    char *inst_name;
    char *pin_name;
    char *sig_name;
} bl_link_def_t;

extern bl_link_def_t const bl_links[];

#endif

/* function that reads the above and builds the system */
void emblocs_init(void);



#endif // EMBLOCS_H
