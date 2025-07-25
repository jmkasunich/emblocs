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

/**************************************************************
 * Realtime data and object metadata are stored in separate
 * memory pools, the RT pool and the META pool.  Each pool is
 * an array of uint32_t, and in the metadata, pool addresses
 * are stored as array indexes in bitfields.  As an example,
 * if a pool is 4K bytes, indexes range from 0 to 1023, and
 * they can be stored in a 10 bit field.
 */

/* default sizes if not defined elsewhere */
#ifndef BL_RT_POOL_SIZE
#define BL_RT_POOL_SIZE     (2048)
#endif
#ifndef BL_META_POOL_SIZE
#define BL_META_POOL_SIZE   (4096)
#endif

/* compute related values */
#define BL_RT_MAX_INDEX     ((BL_RT_POOL_SIZE>>2)-1)
#define BL_RT_INDEX_BITS    (BITS2STORE(BL_RT_MAX_INDEX))

#define BL_META_MAX_INDEX   ((BL_META_POOL_SIZE>>2)-1)
#define BL_META_INDEX_BITS  (BITS2STORE(BL_META_MAX_INDEX))

/* the memory pools */
extern uint32_t bl_rt_pool[];
extern uint32_t *bl_rt_pool_next;
extern uint32_t bl_rt_pool_avail;
extern const uint32_t bl_rt_pool_size;

extern uint32_t bl_meta_pool[];
extern uint32_t *bl_meta_pool_next;
extern uint32_t bl_meta_pool_avail;
extern const uint32_t bl_meta_pool_size;

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

typedef struct bl_instance_meta_s {
    struct bl_instance_meta_s *next;
    struct bl_comp_def_s const *comp_def;
    uint32_t data_index  : BL_RT_INDEX_BITS;
    uint32_t data_size   : BL_INSTANCE_DATA_SIZE_BITS;
    char const *name;
    struct bl_pin_meta_s *pin_list;
    struct bl_function_meta_s *function_list;
} bl_instance_meta_t;

/* Verify that bitfields fit in one uint32_t */
_Static_assert((BL_RT_INDEX_BITS+BL_INSTANCE_DATA_SIZE_BITS) <= 32, "instance bitfields too big");

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
 * Data structure that describes a function.  Each instance
 * has a list of functions.  These structures live in the
 * metadata pool, but point to data in the realtime pool.
 * (note: thread_index is set to BL_META_MAX_INDEX if the
 *  function is NOT in a thread; can't use zero for that
 *  since if a thread was the first object created its
 *  index would be zero)
 */

 typedef struct bl_function_meta_s {
    struct bl_function_meta_s *next;
    uint32_t rtdata_index  : BL_RT_INDEX_BITS;
    uint32_t nofp          : BL_NOFP_BITS;
    uint32_t thread_index  : BL_META_INDEX_BITS;
    char const *name;
} bl_function_meta_t;

/* Verify that bitfields fit in one uint32_t */
_Static_assert((BL_RT_INDEX_BITS+BL_NOFP_BITS+BL_META_INDEX_BITS) <= 32, "function bitfields too big");

/**************************************************************
 * Realtime data for a function.  These structures are created
 * when the instance is created.  Later, when the function is
 * added to a realtime thread, the 'next' field is used to
 * link this structure into the list that corresponds to the
 * thread.
 */
typedef struct bl_function_rtdata_s {
    bl_rt_function_t *funct;
    void *instance_data;
    struct bl_function_rtdata_s *next;
} bl_function_rtdata_t;

/**************************************************************
 * Data structure that describes a signal.  There is one list
 * of signals which lives in the metadata pool, but points to
 * data in the realtime pool.
 */

typedef struct bl_signal_meta_s {
    struct bl_signal_meta_s *next;
    uint32_t data_index   : BL_RT_INDEX_BITS;
    uint32_t data_type    : BL_TYPE_BITS;
    char const *name;
} bl_signal_meta_t;

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

/* realtime data needed for a thread */
typedef struct bl_thread_data_s {
    uint32_t period_ns;
    struct bl_function_rtdata_s *start;
} bl_thread_data_t;

/* root of instance linked list */
extern bl_instance_meta_t *instance_root;

/* root of signal linked list */
extern bl_signal_meta_t *signal_root;

/* root of thread linked list */
extern bl_thread_meta_t *thread_root;

/**************************************************************
 * Lower-level EMBLOCS API functions; typically helpers used  *
 * by the main API functions.  Some of these may become       *
 * static at some point.                                      *
 **************************************************************/

/* callback functions for linked lists */
int bl_instance_meta_compare_name_key(void *node, void *key);
int bl_sig_meta_compare_name_key(void *node, void *key);
int bl_thread_meta_compare_name_key(void *node, void *key);
int bl_pin_meta_compare_name_key(void *node, void *key);
int bl_function_meta_compare_name_key(void *node, void *key);

#endif // EMBLOCS_PRIV_H
