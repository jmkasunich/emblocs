/***************************************************************
 * 
 * emblocs.h - headers for EMBLOCS
 * 
 * Embedded Block-Oriented Control System
 * 
 * 
 * 
 **************************************************************/

#ifndef EMBLOCS_H
#define EMBLOCS_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

/* some basic assumptions */
_Static_assert(sizeof(int) == 4, "ints must be 32 bits");
_Static_assert(sizeof(void *) == 4, "pointers must be 32 bits");

#ifndef _countof
#define _countof(array) (sizeof(array)/sizeof(array[0]))
#endif


/* the four pin/signal data types */
typedef float bl_float_t;
typedef bool bl_bit_t;
typedef int32_t bl_s32_t;
typedef uint32_t bl_u32_t;

/* pins are pointers to their respective data types */
typedef bl_bit_t *bl_pin_bit_t;
typedef bl_float_t *bl_pin_float_t;
typedef bl_s32_t *bl_pin_s32_t;
typedef bl_u32_t *bl_pin_u32_t;

/* "generic" signal data; implemented as a union of the four types */
typedef union bl_sig_data_u {
    bl_bit_t b;
    bl_float_t f;
    bl_s32_t s;
    bl_u32_t u;
} bl_sig_data_t;

/* "generic" pin; implemented as a union of the four pin types */
typedef union bl_pin_u {
    bl_pin_bit_t b;
    bl_pin_float_t f;
    bl_pin_s32_t s;
    bl_pin_u32_t u;
} bl_pin_t;

/* realtime data needed for a thread */
typedef struct bl_thread_data_s {
    uint32_t period_ns;
    struct bl_thread_entry_s *start;
} bl_thread_data_t;

/* a realtime function to be called from a thread
 * the function is passed a pointer to the instance data
 * and the calling period in nano-seconds
 */
typedef void (bl_rt_funct_t)(void *inst_data, uint32_t period_ns);

/* bl_thread_run() traverses a list of these structures */
typedef struct bl_thread_entry_s {
    bl_rt_funct_t *funct;
    void *inst_data;
    struct bl_thread_entry_s *next;
} bl_thread_entry_t;


/* return values for some API functions */
typedef enum {
    BL_SUCCESS = 0,
    BL_ERR_TYPE_MISMATCH = -1,
    BL_ERR_INST_NOT_FOUND = -2,
    BL_ERR_PIN_NOT_FOUND = -3,
    BL_ERR_SIG_NOT_FOUND = -4,
    BL_ERR_THREAD_NOT_FOUND = -5,
    BL_ERR_FUNCT_NOT_FOUND = -6, 
    BL_ERR_NOMEM = -7
} bl_retval_t;

// uncomment this define to print error messages
#define BL_ERROR_VERBOSE

/**************************************************************
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

/* the memory pools */
extern uint32_t bl_rt_pool[];
extern uint32_t bl_meta_pool[];

/* These asserts verify that the specified number of bits can 
   be used to address the specified pool size. */
_Static_assert((4<<(BL_RT_INDEX_BITS)) >= (BL_RT_POOL_SIZE), "not enough RT index bits");
_Static_assert((4<<(BL_META_INDEX_BITS)) >= (BL_META_POOL_SIZE), "not enough meta index bits");

/* A couple of other constants based on pool size */
#define BL_RT_INDEX_MASK ((1<<(BL_RT_INDEX_BITS))-1)
#define BL_META_INDEX_MASK ((1<<(BL_META_INDEX_BITS))-1)

/* returns the index of 'addr' in the respective pool, masked so it can
 * go into a bitfield without a conversion warning */
#define TO_RT_INDEX(addr) ((uint32_t)((uint32_t *)(addr)-bl_rt_pool) & BL_RT_INDEX_MASK)
#define TO_META_INDEX(addr) ((uint32_t)((uint32_t *)(addr)-bl_meta_pool) & BL_META_INDEX_MASK)
/* returns an address in the respective pool */
#define TO_RT_ADDR(index) ((void *)(&bl_rt_pool[index]))
#define TO_META_ADDR(index) ((void *)(&bl_meta_pool[index]))


/**************************************************************
 * Each instance of a component has "instance data" which is
 * in the RT memory pool.  The instance data size is specified
 * in bytes, and the size is stored in a bitfield.
 */

#ifndef BL_INST_DATA_SIZE_BITS
#define BL_INST_DATA_SIZE_BITS  10
#endif

#define BL_INST_DATA_MAX_SIZE (1<<(BL_INST_DATA_SIZE_BITS))
#define BL_INST_DATA_SIZE_MASK ((BL_INST_DATA_MAX_SIZE)-1)

/* masks 'size' so it can go into a bit field without a conversion warning */
#define TO_INST_SIZE(size) ((size) & BL_INST_DATA_SIZE_MASK)


/* pin count (number of pins in a component instance) is 
 * stored in bitfields, need to specify the size
 */
#ifndef BL_PIN_COUNT_BITS
#define BL_PIN_COUNT_BITS 8
#endif

#define BL_PIN_COUNT_MAX (1<<(BL_PIN_COUNT_BITS))

/* the number of functions provided by a component
 * is stored in bitfields, need to specify the size
 */
#ifndef BL_FUNCT_COUNT_BITS
#define BL_FUNCT_COUNT_BITS 3
#endif

#define BL_FUNCT_COUNT_MAX (1<<(BL_FUNCT_COUNT_BITS))

/**************************************************************
 * Data types for pins and signals.  Type is sometimes stored
 * in a bitfield, so we need to specify the bitfield length 
 * as well as the enum.
 */

typedef enum {
	BL_TYPE_FLOAT    = 0,
	BL_TYPE_BIT      = 1,
	BL_TYPE_S32      = 2,
	BL_TYPE_U32      = 3
} bl_type_t;

#define BL_TYPE_BITS 2

/**************************************************************
 * Data directions for pins.  Direction is sometimes stored
 * in a bitfield, so we need to specify the bitfield length
 * as well as the enum.
 */

typedef enum {
	BL_DIR_IN        = 1,
	BL_DIR_OUT       = 2,
	BL_DIR_IO        = 3,
} bl_dir_t;

#define BL_DIR_BITS  2

/**************************************************************
 * Floating point info for threads and functions.  Threads
 * defined as "no_fp" can contain only functions which are
 * also defined as "no_fp".  This flag is stored in a bitfield,
 * so we need to specify the bitfield length as well.
 */

typedef enum {
	BL_HAS_FP        = 0,
	BL_NO_FP         = 1
} bl_nofp_t;

#define BL_NOFP_BITS  1


/**************************************************************
 * The following data structures carry the metadata that      *
 * collectively describe a complete running realtime system.  *
 **************************************************************/

/**************************************************************
 * Data structure that describes a single component instance.
 * A list of these structures lives in the metadata pool, but
 * they point to instance data in the realtime pool.
 * 'data_index' and 'data_size' refer to the realtime instance
 * data; size is in bytes, while index is a uint32_t offset
 * from the base of the RT pool.  'pin_list' is a list of pins
 * that belong to this specific instance.
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

/**************************************************************
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

/**************************************************************
 * Data structure that describes a signal.  There is one list
 * of signals which lives in the metadata pool, but points to
 * data in the realtime pool.
 */

typedef struct bl_sig_meta_s {
    struct bl_sig_meta_s *next;
    uint32_t data_index   : BL_RT_INDEX_BITS;
    uint32_t data_type    : BL_TYPE_BITS;
    char const *name;
} bl_sig_meta_t;

/* Verify that bitfields fit in one uint32_t */
_Static_assert((BL_RT_INDEX_BITS+BL_TYPE_BITS) <= 32, "sig bitfields too big");

/**************************************************************
 * Data structure that describes a thread.  There is one list
 * of threads which lives in the metadata pool, but points to
 * data in the realtime pool.
 */

typedef struct bl_thread_meta_s {
    struct bl_thread_meta_s *next;
    uint32_t data_index   : BL_RT_INDEX_BITS;
    uint32_t nofp         : BL_NOFP_BITS;
    char const *name;
} bl_thread_meta_t;

/* Verify that bitfields fit in one uint32_t */
_Static_assert((BL_RT_INDEX_BITS+BL_NOFP_BITS) <= 32, "thread bitfields too big");


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
    bl_inst_meta_t * (*setup) (char const *inst_name, struct bl_comp_def_s const *comp_def, void const *personality);
    uint32_t data_size   : BL_INST_DATA_SIZE_BITS;
    uint32_t pin_count   : BL_PIN_COUNT_BITS;
    uint32_t funct_count : BL_FUNCT_COUNT_BITS;
    struct bl_pin_def_s const *pin_defs;
    struct bl_funct_def_s const *funct_defs;
} bl_comp_def_t;

/* Verify that bitfields fit in one uint32_t */
_Static_assert((BL_INST_DATA_SIZE_BITS+BL_PIN_COUNT_BITS+BL_FUNCT_COUNT_BITS) <= 32, "comp_def bitfields too big");

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
    uint32_t data_offset  : BL_INST_DATA_SIZE_BITS;
} bl_pin_def_t;

/* Verify that bitfields fit in one uint32_t */
_Static_assert((BL_INST_DATA_SIZE_BITS+BL_TYPE_BITS+BL_DIR_BITS) <= 32, "pin_def bitfields too big");

/**************************************************************
 * Data structure that defines a realtime function.
 * For components that have realtime functions, an array of
 * these structures in flash is pointed to by the component
 * definition.
 */

typedef struct bl_funct_def_s {
    char const *name;
    uint32_t nofp         : BL_NOFP_BITS;
    bl_rt_funct_t *fp;
} bl_funct_def_t;

/* Verify that bitfields fit in one uint32_t */
_Static_assert((BL_NOFP_BITS) <= 32, "funct_def bitfields too big");


/**************************************************************
 * Top-level EMBLOCS API functions used to build a system     *
 *                                                            *
 **************************************************************/

/**************************************************************
 * Create an instance of a component, using a component 
 * definition (typically in flash) and an optional personality.
 */
bl_inst_meta_t *bl_instance_new(char const *name, bl_comp_def_t const *comp_def, void const *personality);

/**************************************************************
 * Create a signal of the specified name and type
 */
bl_sig_meta_t *bl_signal_new(char const *name, bl_type_t type);

/**************************************************************
 * Link the specified pin to the specified signal
 */
bl_retval_t bl_link_pin_to_signal(bl_pin_meta_t const *pin, bl_sig_meta_t const *sig );
bl_retval_t bl_link_pin_to_signal_by_names(char const *inst_name, char const *pin_name, char const *sig_name );

/**************************************************************
 * Disconnect the specified pin from any signal
 */
bl_retval_t bl_unlink_pin(bl_pin_meta_t const *pin);
bl_retval_t bl_unlink_pin_by_name(char const *inst_name, char const *pin_name);

/**************************************************************
 * Set the specified signal to a value
 */
bl_retval_t bl_set_sig(bl_sig_meta_t const *sig, bl_sig_data_t const *value);
bl_retval_t bl_set_sig_by_name(char const *sig_name, bl_sig_data_t const *value);

/**************************************************************
 * Set the specified pin to a value
 */
bl_retval_t bl_set_pin(bl_pin_meta_t const *pin, bl_sig_data_t const *value);
bl_retval_t bl_set_pin_by_name(char const *inst_name, char const *pin_name, bl_sig_data_t const *value);

/**************************************************************
 * Create a thread to which functions can be added.
 * 'period_ns' will be passed to functions in the thread.
 * This API does not directly control the period of the thread;
 * see 'run_thread()' below.
 */
bl_thread_meta_t *bl_thread_new(char const *name, uint32_t period_ns, bl_nofp_t nofp);

/**************************************************************
 * Add the specified function to the end of the specified thread
 */
bl_retval_t bl_add_funct_to_thread(bl_funct_def_t const *funct, bl_inst_meta_t const *inst, bl_thread_meta_t const *thread);
bl_retval_t bl_add_funct_to_thread_by_names(char const *inst_name, char const *funct_name, char const *thread_name);

/**************************************************************
 * Runs a thread once by calling all of the functions that have
 * been added to the thread.  Typically bl_thread_run() will be
 * called from an ISR or an RTOS thread.  If 'period_ns' is 
 * non-zero, it will be passed to the thread functions; if zero,
 * the 'thread_ns' value from thread creation will be passed 
 * instead.
 */
void bl_thread_update(bl_thread_data_t const *thread, uint32_t period_ns);


/**************************************************************
 * Lower-level EMBLOCS API functions; typically helpers used  *
 * by the main API functions.  Some of these may become       *
 * private at some point.                                     *
 **************************************************************/

/**************************************************************
 * Helper function for bl_instance_new(); creates an instance
 * of a component using only the component definition.
 */
bl_inst_meta_t *bl_default_setup(char const *name, bl_comp_def_t const *comp_def);

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
bl_inst_meta_t *bl_inst_create(char const *name, bl_comp_def_t const *comp_def, uint32_t data_size);

/**************************************************************
 * helper function for new instance:
 * adds a pin as defined by 'def' to instance 'inst'
 * allocates a new bl_pin_meta_t struct in meta RAM 
 * allocates a dummy signal in RT ram
 * fills in all fields in the meta struct
 * links the pin to the dummy signal
 * adds the meta struct to 'inst' pin list
 */
bl_pin_meta_t *bl_inst_add_pin(bl_inst_meta_t *inst, bl_pin_def_t const *def);

/**************************************************************
 * Helper functions for finding things in the metadata
 * 
 * The first group finds the single matching item.
 * The second group finds the zero or more matching items,
 * calls a callback functions for each match (if 'callback'
 * is not NULL), and returns the number of matches.
 */
bl_inst_meta_t *bl_find_instance_by_name(char const *name);
bl_inst_meta_t *bl_find_instance_by_data_addr(void *data_addr);
bl_inst_meta_t *bl_find_instance_from_thread_entry(bl_thread_entry_t const *entry);
bl_pin_meta_t *bl_find_pin_in_instance_by_name(char const *name, bl_inst_meta_t const *inst);
bl_pin_meta_t *bl_find_pin_by_names(char const *inst_name, char const *pin_name);
bl_sig_meta_t *bl_find_signal_by_name(char const *name);
bl_sig_meta_t *bl_find_signal_by_index(uint32_t index);
bl_thread_meta_t *bl_find_thread_by_name(char const *name);
bl_thread_data_t *bl_find_thread_data_by_name(char const *name);
bl_funct_def_t *bl_find_funct_def_in_instance_by_name(char const *name, bl_inst_meta_t const *inst);
bl_funct_def_t *bl_find_funct_def_in_instance_by_address(bl_rt_funct_t *addr, bl_inst_meta_t const *inst);
bl_funct_def_t *bl_find_funct_def_from_thread_entry(bl_thread_entry_t const *entry);

int bl_find_pins_linked_to_signal(bl_sig_meta_t const *sig, void (*callback)(bl_inst_meta_t *inst, bl_pin_meta_t *pin));
int bl_find_functions_in_thread(bl_thread_meta_t const *thread, void (*callback)(bl_inst_meta_t *inst, bl_funct_def_t *funct));


/**************************************************************
 * Helper functions for viewing things in the metadata
 */

void bl_show_memory_status(void);
void bl_show_instance(bl_inst_meta_t const *inst);
void bl_show_all_instances(void);
void bl_show_pin(bl_pin_meta_t const *pin);
void bl_show_all_pins_of_instance(bl_inst_meta_t const *inst);
void bl_show_pin_value(bl_pin_meta_t const *pin);
void bl_show_pin_linkage(bl_pin_meta_t const *pin);
void bl_show_signal(bl_sig_meta_t const *sig);
void bl_show_signal_value(bl_sig_meta_t const *sig);
void bl_show_signal_linkage(bl_sig_meta_t const *sig);
void bl_show_sig_data_t_value(bl_sig_data_t const *data, bl_type_t type);
void bl_show_all_signals(void);
void bl_show_thread_entry(bl_thread_entry_t const *entry);
void bl_show_thread(bl_thread_meta_t const *thread);
void bl_show_all_threads(void);


/**************************************************************
 * For convenience, a system can be built by using compact    *
 * representations of multiple EMBLOCS commands.  These       *
 * structures and functions support that.                     *
 **************************************************************/

/**************************************************************
 * A NULL terminated array of "instance definitions" (usually
 * in FLASH) can be passed to bl_init_instances() to create
 * all of the component instances needed for a system.
 */

typedef struct inst_def_s {
    char const *name;
    bl_comp_def_t const *comp_def;
    void const *personality;
} bl_inst_def_t;

void bl_init_instances(bl_inst_def_t const instances[]);

/**************************************************************
 * A NULL terminated array of strings can be passed to 
 * bl_init_nets() to create all of the signals needed for a
 * system, and connect the signals to the appropriate pins.
 * The array starts with one of the type strings "FLOAT",
 * "BIT", "S32" or "U32", then a net name, followed by zero
 * or more instance name/pin name pairs.  Each pin name is
 * followed by either another instance/pin name (to add to 
 * the same net), or by a type string (to start a new net),
 * or by NULL to end the array.
 */

void bl_init_nets(char const * const nets[]);

/**************************************************************
 * A NULL terminated array of "setsig definitions" (usually
 * in FLASH) can be passed to bl_init_setsigs() to set the
 * values of all non-zero signals in a system.
 */

typedef struct bl_setsig_def_s {
    char const *name;
    bl_sig_data_t value;
} bl_setsig_def_t;

void bl_init_setsigs(bl_setsig_def_t const setsigs[]);

/**************************************************************
 * A NULL terminated array of "setpin definitions" (usually
 * in FLASH) can be passed to bl_init_setpins() to set the
 * values of all non-zero unconnected pins in a system.
 */

typedef struct bl_setpin_def_s {
    char const *inst_name;
    char const *pin_name;
    bl_sig_data_t value;
} bl_setpin_def_t;

void bl_init_setpins(bl_setpin_def_t const setpins[]);

/**************************************************************
 * A NULL terminated array of strings can be passed to 
 * bl_init_threads() to create all of the threads needed for
 * a system.  The array starts with either "HAS_FP" or "NO_FP"
 * to mark the beginning of a thread and determine whether that
 * thread should allow functions that need floating point.
 * The next string is a number (in ASCII) that is period_ns
 * for the new thread, followed by the name of the thread.
 * After the thread name, there must be one or more "instance
 * name" / "function name" pairs to define the functions called
 * by the thread, in calling order.  An instance name of either
 * "HAS_FP" or "NO_FP" begins another thread, while NULL ends
 * the array.
 */

void bl_init_threads(char const * const threads[]);


#endif // EMBLOCS_H
