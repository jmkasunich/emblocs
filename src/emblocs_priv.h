/***************************************************************
 * 
 * emblocs_priv.h - private header for EMBLOCS library
 * 
 * Embedded Block-Oriented Control System
 * 
 * 
 * 
 **************************************************************/

#ifndef EMBLOCS_PRIV_H
#define EMBLOCS_PRIV_H

#include "emblocs_api.h"
#include "emblocs_comp.h"

/* the memory pools */
extern uint32_t bl_rt_pool[];
extern uint32_t *bl_rt_pool_next;
extern int32_t bl_rt_pool_avail;
extern const int32_t bl_rt_pool_size;

extern uint32_t bl_meta_pool[];
extern uint32_t *bl_meta_pool_next;
extern int32_t bl_meta_pool_avail;
extern const int32_t bl_meta_pool_size;

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

/* realtime data needed for a thread */
typedef struct bl_thread_data_s {
    uint32_t period_ns;
    struct bl_thread_entry_s *start;
} bl_thread_data_t;

/* bl_thread_run() traverses a list of these structures */
typedef struct bl_thread_entry_s {
    bl_rt_funct_t *funct;
    void *inst_data;
    struct bl_thread_entry_s *next;
} bl_thread_entry_t;


/* Verify that bitfields fit in one uint32_t */
_Static_assert((BL_RT_INDEX_BITS+BL_NOFP_BITS) <= 32, "thread bitfields too big");

/* root of instance linked list */
extern bl_inst_meta_t *instance_root;

/* root of signal linked list */
extern bl_sig_meta_t *signal_root;

/* root of thread linked list */
extern bl_thread_meta_t *thread_root;

/**************************************************************
 * Link the specified pin to the specified signal
 */
bl_retval_t bl_link_pin_to_signal(bl_pin_meta_t const *pin, bl_sig_meta_t const *sig );

/**************************************************************
 * Disconnect the specified pin from any signal
 */
bl_retval_t bl_unlink_pin(bl_pin_meta_t const *pin);

/**************************************************************
 * Set the specified signal to a value
 */
bl_retval_t bl_set_sig(bl_sig_meta_t const *sig, bl_sig_data_t const *value);

/**************************************************************
 * Set the specified pin to a value
 */
bl_retval_t bl_set_pin(bl_pin_meta_t const *pin, bl_sig_data_t const *value);

/**************************************************************
 * Add the specified function to the end of the specified thread
 */
bl_retval_t bl_add_funct_to_thread(bl_funct_def_t const *funct, bl_inst_meta_t const *inst, bl_thread_meta_t const *thread);


/**************************************************************
 * Lower-level EMBLOCS API functions; typically helpers used  *
 * by the main API functions.  Some of these may become       *
 * private at some point.                                     *
 **************************************************************/

/**************************************************************
 * Helper function for bl_instance_new(); creates an instance
 * of a component using only the component definition.
 */
bl_retval_t bl_default_setup(char const *name, bl_comp_def_t const *comp_def);

/**************************************************************
 * Helper functions for finding things in the metadata
 * 
 * These functions are implemented in emblocs_priv.c
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
bl_funct_def_t *bl_find_funct_def_in_instance_by_name(char const *name, bl_inst_meta_t const *inst);
bl_funct_def_t *bl_find_funct_def_by_names(char const *inst_name, char const *funct_name);
bl_funct_def_t *bl_find_funct_def_in_instance_by_address(bl_rt_funct_t *addr, bl_inst_meta_t const *inst);
bl_funct_def_t *bl_find_funct_def_from_thread_entry(bl_thread_entry_t const *entry);

int bl_find_pins_linked_to_signal(bl_sig_meta_t const *sig, void (*callback)(bl_inst_meta_t *inst, bl_pin_meta_t *pin));
int bl_find_functions_in_thread(bl_thread_meta_t const *thread, void (*callback)(bl_inst_meta_t *inst, bl_funct_def_t *funct));

/**************************************************************
 * Helper functions for viewing things in the metadata        *
 *                                                            *
 * These functions are defined in emblocs_show.c              *
 *                                                            *
 **************************************************************/

void bl_show_instance(bl_inst_meta_t const *inst);
void bl_show_pin(bl_pin_meta_t const *pin);
void bl_show_all_pins_of_instance(bl_inst_meta_t const *inst);
void bl_show_pin_value(bl_pin_meta_t const *pin);
void bl_show_pin_linkage(bl_pin_meta_t const *pin);
void bl_show_signal(bl_sig_meta_t const *sig);
void bl_show_signal_value(bl_sig_meta_t const *sig);
void bl_show_signal_linkage(bl_sig_meta_t const *sig);
void bl_show_sig_data_t_value(bl_sig_data_t const *data, bl_type_t type);
void bl_show_thread_entry(bl_thread_entry_t const *entry);
void bl_show_thread(bl_thread_meta_t const *thread);


#endif // EMBLOCS_PRIV_H
