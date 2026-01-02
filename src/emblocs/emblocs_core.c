#include "emblocs_priv.h"
#include "linked_list.h"
#include <string.h>         // strcmp
#include <stdio.h>      // FIXME - printf for rasp pi


/***********************************************
 * error handling
 */

bl_errno_t bl_errno;

static char const *error_strings[] = {
    "no error",
    "operand out of range",
    "unexpected null pointer",
    "insufficient realtime memory",
    "insufficient metadata memory",
    "component does not support personality",
    "name already exists",
    "type mismatch",
    "already linked",
    "not found",
    "object too large",
    "signal cannot be 'raw'",
    "internal data structure error",
    "unknown error"
};

_Static_assert((_countof(error_strings) == (BL_ERRNO_MAX+1)), "error_strings[] mismatch");

char const *bl_errstr(void)
{
    if ( bl_errno >= BL_ERRNO_MAX ) {
        return "unknown error";
    }
    return error_strings[bl_errno];
}

/***********************************************
 * memory pools
 */

uint32_t bl_rt_pool[BL_RT_POOL_SIZE >> 2]  __attribute__ ((aligned(4)));
uint32_t *bl_rt_pool_next = bl_rt_pool;
uint32_t bl_rt_pool_avail = sizeof(bl_rt_pool);
const uint32_t bl_rt_pool_size = sizeof(bl_rt_pool);

uint32_t bl_meta_pool[BL_META_POOL_SIZE >> 2]  __attribute__ ((aligned(4)));
uint32_t *bl_meta_pool_next = bl_meta_pool;
uint32_t bl_meta_pool_avail = sizeof(bl_meta_pool);
const uint32_t bl_meta_pool_size = sizeof(bl_meta_pool);

/* memory allocation functions */

/* I do a bunch of pointer manipulation 
   and type-punning in this file */
#pragma GCC optimize ("no-strict-aliasing")

static void *alloc_from_rt_pool(uint32_t size)
{
    void *retval;

    if ( size <= 0 ) ERROR_RETURN(BL_ERR_RANGE);
    // round size up to multiple of 4
    if ( size & 3 ) {
        size += 4;
        size &= ~3u;
    }
    if ( bl_rt_pool_avail < size) ERROR_RETURN(BL_ERR_NO_RT_RAM);
    retval = bl_rt_pool_next;
    bl_rt_pool_next += size/4;
    bl_rt_pool_avail -= size;
    return retval;
}

static void *alloc_from_meta_pool(uint32_t size)
{
    void *retval;

    if ( size <= 0 ) ERROR_RETURN(BL_ERR_RANGE);
    // round size up to multiple of 4
    if ( size & 3 ) {
        size += 4;
        size &= ~3u;
    }
    if ( bl_meta_pool_avail < size) ERROR_RETURN(BL_ERR_NO_META_RAM);
    retval = bl_meta_pool_next;
    bl_meta_pool_next += size/4;
    bl_meta_pool_avail -= size;
    return retval;
}


/* root of block linked list */
bl_block_meta_t *block_root;

/* root of signal linked list */
bl_signal_meta_t *signal_root;

/* root of thread linked list */
bl_thread_meta_t *thread_root;


/* linked list callback functions */
static int block_meta_compare_names(void *node1, void *node2)
{
    bl_block_meta_t  *np1 = node1;
    bl_block_meta_t  *np2 = node2;
    return strcmp(np1->name, np2->name);
}

static int pin_meta_compare_names(void *node1, void *node2)
{
    bl_pin_meta_t  *np1 = node1;
    bl_pin_meta_t  *np2 = node2;
    return strcmp(np1->name, np2->name);
}

static int function_meta_compare_names(void *node1, void *node2)
{
    bl_function_meta_t  *np1 = node1;
    bl_function_meta_t  *np2 = node2;
    return strcmp(np1->name, np2->name);
}

static int sig_meta_compare_names(void *node1, void *node2)
{
    bl_signal_meta_t  *np1 = node1;
    bl_signal_meta_t  *np2 = node2;
    return strcmp(np1->name, np2->name);
}

static int thread_meta_compare_names(void *node1, void *node2)
{
    bl_thread_meta_t  *np1 = node1;
    bl_thread_meta_t  *np2 = node2;
    return strcmp(np1->name, np2->name);
}


/**************************************************************
 * Top-level EMBLOCS API functions used to build a system     *
 **************************************************************/

struct bl_block_meta_s *bl_block_new(char const *name, struct bl_comp_def_s const *comp_def, void const *personality)
{
    struct bl_block_meta_s *retval;

    CHECK_NULL(name);
    CHECK_NULL(comp_def);
    if ( comp_def->setup == NULL ) {
        // no setup function, cannot support personality
        if ( personality != NULL) {
            ERROR_RETURN(BL_ERR_NO_PERSONALITY);
        }
        // call default setup function
        bl_errno = BL_ERRNO_MAX;  // FIXME - why did I do this?
        retval = bl_default_setup(name, comp_def);
    } else {
        // call component-specific setup function
        bl_errno = BL_ERRNO_MAX;
        retval = comp_def->setup(name, comp_def, personality);
    }
#ifdef BL_ERROR_HALT
    if ( retval == NULL ) {
        printf("setup function failed, halting\n");
        while(1);
//        halt();
    }
#endif
    return retval;
}

struct bl_signal_meta_s *bl_signal_new(char const *name, bl_type_t type)
{
    struct bl_signal_meta_s *meta;
    bl_sig_data_t *data;
    int ll_result;

    CHECK_NULL(name);
    // signals cannot be 'raw'
    if ( type >= BL_TYPE_RAW ) {
        ERROR_RETURN(BL_ERR_RAW_SIGNAL);
    }
    // allocate memory for metadata
    meta = alloc_from_meta_pool(sizeof(bl_signal_meta_t));
    CHECK_RETURN(meta);
    // allocate memory for signal data
    data = alloc_from_rt_pool(sizeof(bl_sig_data_t));
    CHECK_RETURN(data);
    // initialize signal to zero
    data->u = 0;
    // initialise metadata fields
    meta->data_index = TO_RT_INDEX(data);
    meta->data_type = type;
    meta->name = name;
    // add metadata to master signal list
    ll_result = ll_insert((void **)(&(signal_root)), (void *)meta, sig_meta_compare_names);
    if ( ll_result != 0 ) {
        ERROR_RETURN(BL_ERR_NAME_EXISTS);
    }
    return meta;
}

bool bl_pin_linkto_signal(bl_pin_meta_t const *pin, bl_signal_meta_t const *sig )
{
    bl_sig_data_t *sig_data_addr, **pin_ptr_addr;

    CHECK_NULL(pin);
    CHECK_NULL(sig);
    // check types
    if ( ( pin->data_type != sig->data_type ) && ( pin->data_type != BL_TYPE_RAW ) ) {
        ERROR_RETURN(BL_ERR_TYPE_MISMATCH);
    }
    // convert indexes to addresses
    pin_ptr_addr = TO_RT_ADDR(pin->ptr_index);
    sig_data_addr = TO_RT_ADDR(sig->data_index);
    #ifndef BL_ENABLE_IMPLICIT_UNLINK
    bl_sig_data_t *dummy_addr = TO_RT_ADDR(pin->dummy_index);
    if ( *pin_ptr_addr != dummy_addr ) {
        ERROR_RETURN(BL_ERR_ALREADY_LINKED);
    }
    #endif
    // make the link (this automatically undoes any previous linkage)
    *pin_ptr_addr = sig_data_addr;
    return true;

}

#ifdef BL_ENABLE_UNLINK
bool bl_pin_unlink(bl_pin_meta_t const *pin)
{
    bl_sig_data_t *pin_dummy_addr, **pin_ptr_addr, *pin_ptr_value;

    CHECK_NULL(pin);
    // convert indexes to addresses
    pin_ptr_addr = TO_RT_ADDR(pin->ptr_index);
    pin_dummy_addr = TO_RT_ADDR(pin->dummy_index);
    // copy current signal value to dummy
    pin_ptr_value = *pin_ptr_addr;
    *pin_dummy_addr = *pin_ptr_value;
    // link pin to its dummy
    *pin_ptr_addr = pin_dummy_addr;
    return true;
}
#endif

bool bl_signal_set(bl_signal_meta_t const *sig, bl_sig_data_t const *value)
{
    bl_sig_data_t *sig_data;

    CHECK_NULL(sig);
    CHECK_NULL(value);
    sig_data = TO_RT_ADDR(sig->data_index);
    *sig_data = *value;
    return true;
}

bool bl_pin_set(bl_pin_meta_t const *pin, bl_sig_data_t const *value)
{
    bl_sig_data_t **pin_ptr, *sig_data;

    CHECK_NULL(pin);
    CHECK_NULL(value);
    pin_ptr = TO_RT_ADDR(pin->ptr_index);
    sig_data = *pin_ptr;
    *sig_data = *value;
    return true;
}

struct bl_thread_meta_s *bl_thread_new(char const *name, uint32_t period_ns, bl_nofp_t nofp)
{
    bl_thread_meta_t *meta;
    bl_thread_data_t *data;
    int ll_result;

    CHECK_NULL(name);
    // allocate memory for metadata
    meta = alloc_from_meta_pool(sizeof(bl_thread_meta_t));
    CHECK_RETURN(meta);
    // allocate memory for RT thread data
    data = alloc_from_rt_pool(sizeof(bl_thread_data_t));
    CHECK_RETURN(data);
    // initialize data fields
    data->period_ns = period_ns;
    data->start = NULL;
    // initialise metadata fields
    meta->data_index = TO_RT_INDEX(data);
    meta->nofp = nofp;
    meta->name = name;
    // add metadata to master thread list
    ll_result = ll_insert((void **)(&(thread_root)), (void *)meta, thread_meta_compare_names);
    if ( ll_result != 0 ) {
        ERROR_RETURN(BL_ERR_NAME_EXISTS);
    }
    return meta;
}

bool bl_function_linkto_thread(struct bl_function_meta_s *funct, struct bl_thread_meta_s const *thread)
{
    bl_function_rtdata_t *funct_data;
    bl_thread_data_t *thread_data;
    bl_function_rtdata_t *prev, **prev_ptr;

    CHECK_NULL(funct);
    CHECK_NULL(thread);
    // validate floating point
    if ( ( thread->nofp == BL_NO_FP) && ( funct->nofp == BL_HAS_FP ) ) {
        ERROR_RETURN(BL_ERR_TYPE_MISMATCH);
    }
    if ( funct->thread_index != BL_META_MAX_INDEX ) {
        #ifdef BL_ENABLE_IMPLICIT_UNLINK
        bl_function_unlink(funct);
        #else
        ERROR_RETURN(BL_ERR_ALREADY_LINKED);
        #endif
    }
    // link function metadata back to the thread
    funct->thread_index = TO_META_INDEX(thread);
    // get pointers to realtime data
    funct_data = TO_RT_ADDR(funct->rtdata_index);
    thread_data = TO_RT_ADDR(thread->data_index);
    // find end of thread
    prev_ptr = &(thread_data->start);
    prev = *prev_ptr;
    while ( prev != NULL ) {
        prev_ptr = &(prev->next);
        prev = *prev_ptr;
    }
    // append function RT data to thread
    funct_data->next = NULL;
    *prev_ptr = funct_data;
    return true;
}

#ifdef  BL_ENABLE_UNLINK
bool bl_function_unlink(struct bl_function_meta_s *funct)
{
    bl_thread_meta_t *thread;
    bl_function_rtdata_t *funct_data;
    bl_thread_data_t *thread_data;
    bl_function_rtdata_t *prev, **prev_ptr;

    CHECK_NULL(funct);
    if ( funct->thread_index == BL_META_MAX_INDEX ) {
        // function is not in a thread; done
        return true;
    }
    thread = TO_META_ADDR(funct->thread_index);
    // get pointers to realtime data
    funct_data = TO_RT_ADDR(funct->rtdata_index);
    thread_data = TO_RT_ADDR(thread->data_index);
    // traverse thread list
    prev_ptr = &(thread_data->start);
    prev = *prev_ptr;
    while ( prev != NULL ) {
        if ( prev == funct_data ) {
            // found it, unlink
            *prev_ptr = funct_data->next;
            // reset metadata to 'unlinked'
            funct->thread_index = BL_META_MAX_INDEX;
            return true;
        }
        prev_ptr = &(prev->next);
        prev = *prev_ptr;
    }
    // not found in thread
    ERROR_RETURN(BL_ERR_INTERNAL);
}
#endif

void bl_thread_run(struct bl_thread_data_s const *thread, uint32_t period_ns)
{
    bl_function_rtdata_t *function;

    if ( period_ns == 0 ) {
        period_ns = thread->period_ns;
    }
    function = thread->start;
    while ( function != NULL ) {
        // call the function
        (*(function->funct))(function->block_data, period_ns);
        function = function->next;
    }
}

struct bl_thread_data_s *bl_thread_get_data(struct bl_thread_meta_s *thread)
{
    CHECK_NULL(thread);
    return TO_RT_ADDR(thread->data_index);
}


/* linked list callback functions */
int bl_block_meta_compare_name_key(void *node, void *key)
{
    bl_block_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
}

int bl_sig_meta_compare_name_key(void *node, void *key)
{
    bl_signal_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
}

int bl_thread_meta_compare_name_key(void *node, void *key)
{
    bl_thread_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
}

int bl_pin_meta_compare_name_key(void *node, void *key)
{
    bl_pin_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
}

int bl_function_meta_compare_name_key(void *node, void *key)
{
    bl_function_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
}

struct bl_block_meta_s *bl_block_find(char const *name)
{
    bl_block_meta_t *retval;

    CHECK_NULL(name);
    retval = ll_find((void **)(&(block_root)), (void *)(name), bl_block_meta_compare_name_key);
    if ( retval == NULL ) {
        ERROR_RETURN(BL_ERR_NOT_FOUND);
    }
    return retval;
}

struct bl_signal_meta_s *bl_signal_find(char const *name)
{
    bl_signal_meta_t *retval;

    CHECK_NULL(name);
    retval = ll_find((void **)(&(signal_root)), (void *)(name), bl_sig_meta_compare_name_key);
    if ( retval == NULL ) {
        ERROR_RETURN(BL_ERR_NOT_FOUND);
    }
    return retval;
}

struct bl_thread_meta_s *bl_thread_find(char const *name)
{
    bl_thread_meta_t *retval;

    CHECK_NULL(name);
    retval = ll_find((void **)(&(thread_root)), (void *)(name), bl_thread_meta_compare_name_key);
    if ( retval == NULL ) {
        ERROR_RETURN(BL_ERR_NOT_FOUND);
    }
    return retval;
}

struct bl_pin_meta_s *bl_pin_find_in_block(char const *name, struct bl_block_meta_s *blk)
{
    bl_pin_meta_t *retval;

    CHECK_NULL(name);
    retval = ll_find((void **)(&(blk->pin_list)), (void *)(name), bl_pin_meta_compare_name_key);
    if ( retval == NULL ) {
        ERROR_RETURN(BL_ERR_NOT_FOUND);
    }
    return retval;
}

struct bl_function_meta_s *bl_function_find_in_block(char const *name, struct bl_block_meta_s *blk)
{
    bl_function_meta_t *retval;

    CHECK_NULL(name);
    retval = ll_find((void **)(&(blk->function_list)), (void *)(name), bl_function_meta_compare_name_key);
    if ( retval == NULL ) {
        ERROR_RETURN(BL_ERR_NOT_FOUND);
    }
    return retval;
}

struct bl_block_meta_s *bl_default_setup(char const *name, bl_comp_def_t const *comp_def)
{
    bl_block_meta_t *meta;
    bool retval __attribute__ ((unused));

    CHECK_NULL(name);
    CHECK_NULL(comp_def);
    meta = bl_block_create(name, comp_def, 0);
    CHECK_RETURN(meta);
    retval = bl_block_add_pins(meta, comp_def);
    CHECK_RETURN(retval);
    retval = bl_block_add_functions(meta, comp_def);
    CHECK_RETURN(retval);
    return meta;
}

struct bl_block_meta_s *bl_block_create(char const *name, bl_comp_def_t const *comp_def, uint32_t data_size)
{
    bl_block_meta_t *meta;
    void *data;
    int ll_result;

    CHECK_NULL(name);
    CHECK_NULL(comp_def);
    if ( data_size == 0 ) {
        data_size = comp_def->data_size;
    }
    if ( data_size >= BL_BLOCK_DATA_MAX_SIZE ) {
        ERROR_RETURN(BL_ERR_TOO_BIG);
    }
    // allocate memory for metadata
    meta = alloc_from_meta_pool(sizeof(bl_block_meta_t));
    CHECK_RETURN(meta);
    // allocate memory for realtime data
    data = alloc_from_rt_pool(data_size);
    CHECK_RETURN(data);
    // initialise metadata fields
    meta->comp_def = comp_def;
    meta->data_index = TO_RT_INDEX(data);
    meta->data_size = TO_BLOCK_SIZE(data_size);
    meta->name = name;
    meta->pin_list = NULL;
    // add metadata to master block list
    ll_result = ll_insert((void **)(&block_root), (void *)meta, block_meta_compare_names);
    if ( ll_result != 0 ) {
        ERROR_RETURN(BL_ERR_NAME_EXISTS);
    }
    return meta;
}

void *bl_block_data_addr(struct bl_block_meta_s *blk)
{
    CHECK_NULL(blk);
    return TO_RT_ADDR(blk->data_index);
}

bool bl_block_add_pin(struct bl_block_meta_s *blk, bl_pin_def_t const *def)
{
    bl_pin_meta_t *meta;
    bl_sig_data_t *data;
    bl_sig_data_t **ptr_addr;
    int ll_result;

    CHECK_NULL(blk);
    CHECK_NULL(def);
    // allocate memory for metadata
    meta = alloc_from_meta_pool(sizeof(bl_pin_meta_t));
    CHECK_RETURN(meta);
    // allocate memory for dummy signal
    data = alloc_from_rt_pool(sizeof(bl_sig_data_t));
    CHECK_RETURN(data);
    // determine address of pin pointer
    ptr_addr = (bl_sig_data_t **)((char *)(TO_RT_ADDR(blk->data_index)) + def->data_offset);
    // link pin to dummy signal
    *ptr_addr = data;
    // initialize dummy signal to zero (independent of type)
    data->u = 0;
    // initialise metadata fields
    meta->ptr_index = TO_RT_INDEX(ptr_addr);
    meta->dummy_index = TO_RT_INDEX(data);
    meta->data_type = def->data_type;
    meta->pin_dir = def->pin_dir;
    meta->name = def->name;
    // add metadata to block's pin list
    ll_result = ll_insert((void **)(&(blk->pin_list)), (void *)meta, pin_meta_compare_names);
    if ( ll_result != 0 ) {
        ERROR_RETURN(BL_ERR_NAME_EXISTS);
    }
    return true;
}

bool bl_block_add_pins(struct bl_block_meta_s *blk, bl_comp_def_t const *def)
{
    bool retval;
    int errors = 0;

    CHECK_NULL(blk);
    CHECK_NULL(def);
    for ( int i = 0 ; i < def->num_pin_defs ; i++ ) {
        retval = bl_block_add_pin(blk, &(def->pin_defs[i]));
        if ( ! retval ) {
            errors++;
        }
    }
    if ( errors > 0 ) {
        return false;
    } else {
        return true;
    }
}

bool bl_block_add_function(struct bl_block_meta_s *blk, bl_function_def_t const *def)
{
    bl_function_meta_t *meta;
    bl_function_rtdata_t *data;
    int ll_result;

    CHECK_NULL(blk);
    CHECK_NULL(def);
    // allocate memory for metadata
    meta = alloc_from_meta_pool(sizeof(bl_function_meta_t));
    CHECK_RETURN(meta);
    // allocate memory for realtime data
    data = alloc_from_rt_pool(sizeof(bl_function_rtdata_t));
    CHECK_RETURN(data);
    // initialize realtime data fields
    data->funct = def->fp;
    data->block_data = TO_RT_ADDR(blk->data_index);
    data->next = NULL;
    // initialise metadata fields
    meta->rtdata_index = TO_RT_INDEX(data);
    meta->nofp = def->nofp;
    meta->name = def->name;
    meta->thread_index = BL_META_MAX_INDEX;  // MAX means not in a thread
    // add metadata to block's function list
    ll_result = ll_insert((void **)(&(blk->function_list)), (void *)meta, function_meta_compare_names);
    if ( ll_result != 0 ) {
        ERROR_RETURN(BL_ERR_NAME_EXISTS);
    }
    return true;
}

bool bl_block_add_functions(struct bl_block_meta_s *blk, bl_comp_def_t const *def)
{
    bool retval;
    int errors = 0;

    CHECK_NULL(blk);
    CHECK_NULL(def);
    for ( int i = 0 ; i < def->num_function_defs ; i++ ) {
        retval = bl_block_add_function(blk, &(def->function_defs[i]));
        if ( ! retval ) {
            errors++;
        }
    }
    if ( errors > 0 ) {
        return false;
    } else {
        return true;
    }
}

#pragma GCC reset_options
