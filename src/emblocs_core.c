#include "emblocs_priv.h"
#include "linked_list.h"
#include <string.h>         // strcmp
#include "printing.h"

#define halt()  do {} while (1)

#ifdef BL_ERROR_HALT
#define halt_or_return(x) do {} while (1)
#else
#define halt_or_return(x) return (x)
#endif

/***********************************************
 * memory pools
 */

uint32_t bl_rt_pool[BL_RT_POOL_SIZE >> 2]  __attribute__ ((aligned(4)));
uint32_t *bl_rt_pool_next = bl_rt_pool;
int32_t bl_rt_pool_avail = sizeof(bl_rt_pool);
const int32_t bl_rt_pool_size = sizeof(bl_rt_pool);

uint32_t bl_meta_pool[BL_META_POOL_SIZE >> 2]  __attribute__ ((aligned(4)));
uint32_t *bl_meta_pool_next = bl_meta_pool;
int32_t bl_meta_pool_avail = sizeof(bl_meta_pool);
const int32_t bl_meta_pool_size = sizeof(bl_meta_pool);

/* memory allocation functions */

static void *alloc_from_rt_pool(int32_t size)
{
    void *retval;

    if ( size <= 0 ) halt();
    // round size up to multiple of 4
    if ( size & 3 ) {
        size += 4;
        size &= ~3;
    }
    if ( bl_rt_pool_avail < size) {
        #ifdef BL_ERROR_VERBOSE
        print_string("insufficient realtime RAM\n");
        #endif
        halt_or_return(NULL);
    }
    retval = bl_rt_pool_next;
    bl_rt_pool_next += size/4;
    bl_rt_pool_avail -= size;
    return retval;
}

static void *alloc_from_meta_pool(int32_t size)
{
    void *retval;

    if ( size <= 0 ) halt();
    // round size up to multiple of 4
    if ( size & 3 ) {
        size += 4;
        size &= ~3;
    }
    if ( bl_meta_pool_avail < size) {
        #ifdef BL_ERROR_VERBOSE
        print_string("insufficient metadata RAM\n");
        #endif
        halt_or_return(NULL);
    }
    retval = bl_meta_pool_next;
    bl_meta_pool_next += size/4;
    bl_meta_pool_avail -= size;
    return retval;
}


/* root of instance linked list */
bl_instance_meta_t *instance_root;

/* root of signal linked list */
bl_signal_meta_t *signal_root;

/* root of thread linked list */
bl_thread_meta_t *thread_root;


/* linked list callback functions */
static int instance_meta_compare_names(void *node1, void *node2)
{
    bl_instance_meta_t  *np1 = node1;
    bl_instance_meta_t  *np2 = node2;
    return strcmp(np1->name, np2->name);
}

static int pin_meta_compare_names(void *node1, void *node2)
{
    bl_pin_meta_t  *np1 = node1;
    bl_pin_meta_t  *np2 = node2;
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

struct bl_instance_meta_s *bl_instance_new(char const *name, struct bl_comp_def_s const *comp_def, void const *personality)
{
    struct bl_instance_meta_s *retval;

    if ( comp_def->setup == NULL ) {
        // no setup function, cannot support personality
        if ( personality != NULL) {
            #ifdef BL_ERROR_VERBOSE
            print_strings(3, "component: '", comp_def->name, "' does not support personality\n");
            #endif
            halt_or_return(NULL);
        }
        // call default setup function
        retval = bl_default_setup(name, comp_def);
    } else {
        // call component-specific setup function
        retval = comp_def->setup(name, comp_def, personality);
    }
    if ( retval == NULL ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(4, "cound not create ", "instance '", name, "'\n");
        #endif
        halt_or_return(retval);
    }
    return retval;
}

struct bl_signal_meta_s *bl_signal_new(char const *name, bl_type_t type)
{
    struct bl_signal_meta_s *meta;
    bl_sig_data_t *data;
    int ll_result;

    // allocate memory for metadata
    meta = alloc_from_meta_pool(sizeof(bl_signal_meta_t));
    // allocate memory for signal data
    data = alloc_from_rt_pool(sizeof(bl_sig_data_t));
    #ifndef BL_ERROR_HALT
    if ( ( meta == NULL ) || ( data == NULL ) ) {
        goto error;
    }
    #endif
    // initialize signal to zero
    data->u = 0;
    // initialise metadata fields
    meta->data_index = TO_RT_INDEX(data);
    meta->data_type = type;
    meta->name = name;
    // add metadata to master signal list
    ll_result = ll_insert((void **)(&(signal_root)), (void *)meta, sig_meta_compare_names);
    if ( ll_result != 0 ) {
        #ifdef BL_ERROR_VERBOSE
        print_string("duplicate name\n");
        #endif
        goto error;
    }
    return meta;

    error:
    #ifdef BL_ERROR_VERBOSE
    print_strings(4, "could not create ", "signal: '", name, "'\n");
    #endif
    halt_or_return(NULL);
}

bl_retval_t bl_pin_linkto_signal(bl_pin_meta_t const *pin, bl_signal_meta_t const *sig )
{
    bl_sig_data_t *sig_data_addr, **pin_ptr_addr;

    // check types
    if ( pin->data_type != sig->data_type ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(7, "type mismatch: ", "pin: '", pin->name, "' vs ", "signal: '", sig->name, "'\n");
        #endif
        halt_or_return(BL_ERR_TYPE_MISMATCH);
    }
    // convert indexes to addresses
    pin_ptr_addr = TO_RT_ADDR(pin->ptr_index);
    sig_data_addr = TO_RT_ADDR(sig->data_index);
    // make the link
    *pin_ptr_addr = sig_data_addr;
    return BL_SUCCESS;
}

bl_retval_t bl_pin_unlink(bl_pin_meta_t const *pin)
{
    bl_sig_data_t *pin_dummy_addr, **pin_ptr_addr, *pin_ptr_value;

    // convert indexes to addresses
    pin_ptr_addr = TO_RT_ADDR(pin->ptr_index);
    pin_dummy_addr = TO_RT_ADDR(pin->dummy_index);
    // copy current signal value to dummy
    pin_ptr_value = *pin_ptr_addr;
    *pin_dummy_addr = *pin_ptr_value;
    // link pin to its dummy
    *pin_ptr_addr = pin_dummy_addr;
    return BL_SUCCESS;
}

bl_retval_t bl_signal_set(bl_signal_meta_t const *sig, bl_sig_data_t const *value)
{
    bl_sig_data_t *sig_data;

    sig_data = TO_RT_ADDR(sig->data_index);
    *sig_data = *value;
    return BL_SUCCESS;
}

bl_retval_t bl_pin_set(bl_pin_meta_t const *pin, bl_sig_data_t const *value)
{
    bl_sig_data_t **pin_ptr, *sig_data;

    pin_ptr = TO_RT_ADDR(pin->ptr_index);
    sig_data = *pin_ptr;
    *sig_data = *value;
    return BL_SUCCESS;
}

struct bl_thread_meta_s *bl_thread_new(char const *name, uint32_t period_ns, bl_nofp_t nofp)
{
    bl_thread_meta_t *meta;
    bl_thread_data_t *data;
    int ll_result;

    // allocate memory for metadata
    meta = alloc_from_meta_pool(sizeof(bl_thread_meta_t));
    // allocate memory for RT thread data
    data = alloc_from_rt_pool(sizeof(bl_thread_data_t));
    #ifndef BL_ERROR_HALT
    if ( ( meta == NULL ) || ( data == NULL ) ) {
        goto error;
    }
    #endif
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
        #ifdef BL_ERROR_VERBOSE
        print_string("duplicate name\n");
        #endif
        goto error;
    }
    return meta;

    error:
    #ifdef BL_ERROR_VERBOSE
    print_strings(4, "could not create ", "thread: '", name, "'\n");
    #endif
    halt_or_return(NULL);
}

bl_retval_t bl_thread_add_function(bl_thread_meta_t const *thread, bl_instance_meta_t const *inst, bl_function_def_t const *funct)
{
    bl_thread_entry_t *new_entry;
    bl_thread_data_t *thread_data;
    bl_thread_entry_t *prev, **prev_ptr;

    // validate floating point
    if ( ( thread->nofp == BL_NO_FP) && ( funct->nofp == BL_HAS_FP ) ) {
        #ifdef BL_ERROR_VERBOSE
        print_string("cannot put FP function in non-FP thread\n");
        #endif
        halt_or_return(BL_ERR_TYPE_MISMATCH);
    }
    // allocate memory for thread entry
    new_entry = alloc_from_rt_pool(sizeof(bl_thread_entry_t));
    #ifndef BL_ERROR_HALT
    if ( new_entry == NULL ) {
         return BL_ERR_NOMEM;
    }
    #endif
    // set entry's fields
    new_entry->funct = funct->fp;
    new_entry->instance_data = TO_RT_ADDR(inst->data_index);
    // find end of thread
    thread_data = TO_RT_ADDR(thread->data_index);
    prev_ptr = &(thread_data->start);
    prev = *prev_ptr;
    while ( prev != NULL ) {
        prev_ptr = &(prev->next);
        prev = *prev_ptr;
    }
    // append new entry
    new_entry->next = NULL;
    *prev_ptr = new_entry;
    return BL_SUCCESS;
}


void bl_thread_run(struct bl_thread_data_s const *thread, uint32_t period_ns)
{
    bl_thread_entry_t *entry;

    if ( period_ns == 0 ) {
        period_ns = thread->period_ns;
    }
    entry = thread->start;
    while ( entry != NULL ) {
        (*(entry->funct))(entry->instance_data, period_ns);
        entry = entry->next;
    }
}

struct bl_thread_data_s *bl_thread_get_data(struct bl_thread_meta_s *thread)
{
    return TO_RT_ADDR(thread->data_index);
}

/* linked list callback functions */
static int instance_meta_compare_name_key(void *node, void *key)
{
    bl_instance_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
}

static int sig_meta_compare_name_key(void *node, void *key)
{
    bl_signal_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
}

static int thread_meta_compare_name_key(void *node, void *key)
{
    bl_thread_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
}

static int pin_meta_compare_name_key(void *node, void *key)
{
    bl_pin_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
}




struct bl_instance_meta_s *bl_instance_find(char const *name)
{
    bl_instance_meta_t *retval;

    retval = ll_find((void **)(&(instance_root)), (void *)(name), instance_meta_compare_name_key);
    if ( retval == NULL ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(4, "not found: ", "instance: '", name, "'\n");
        #endif
        halt_or_return(NULL);
    }
    return retval;
}

struct bl_signal_meta_s *bl_signal_find(char const *name)
{
    bl_signal_meta_t *retval;

    retval = ll_find((void **)(&(signal_root)), (void *)(name), sig_meta_compare_name_key);
    if ( retval == NULL ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(4, "not found: ", "signal: '", name, "'\n");
        #endif
        halt_or_return(NULL);
    }
    return retval;
}

struct bl_thread_meta_s *bl_thread_find(char const *name)
{
    bl_thread_meta_t *retval;

    retval = ll_find((void **)(&(thread_root)), (void *)(name), thread_meta_compare_name_key);
    if ( retval == NULL ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(4, "not found: ", "thread: '", name, "'\n");
        #endif
        halt_or_return(NULL);
    }
    return retval;
}

struct bl_pin_meta_s *bl_pin_find_in_instance(char const *name, struct bl_instance_meta_s *inst)
{
    bl_pin_meta_t *retval;

    retval = ll_find((void **)(&(inst->pin_list)), (void *)(name), pin_meta_compare_name_key);
    if ( retval == NULL ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(7, "not found: ", "pin: '", name, "' in ", "instance: '", inst->name, "'\n");
        #endif
        halt_or_return(NULL);
    }
    return retval;
}

struct bl_function_def_s *bl_function_find_in_instance(char const *name, struct bl_instance_meta_s *inst)
{
    bl_comp_def_t const *comp;
    bl_function_def_t const *fdef;

    comp = inst->comp_def;
    for ( int n = 0 ; n < comp->function_count ; n++ ) {
        fdef = &(comp->function_defs[n]);
        if ( strcmp(name, fdef->name ) == 0 ) {
            return (bl_function_def_t *)fdef;
        }
    }
    #ifdef BL_ERROR_VERBOSE
    print_strings(7, "not found: ", "function: '", name, "' in ", "instance: '", inst->name, "'\n");
    #endif
    halt_or_return(NULL);
}

struct bl_instance_meta_s *bl_default_setup(char const *name, bl_comp_def_t const *comp_def)
{
    bl_instance_meta_t *meta;
    bl_retval_t retval __attribute__ ((unused));

    meta = bl_instance_create(name, comp_def, 0);
    #ifndef BL_ERROR_HALT
    if ( meta == NULL ) {
        goto error;
    }
    #endif
    for ( int i = 0 ; i < comp_def->pin_count ; i++ ) {
        retval = bl_instance_add_pin(meta, &(comp_def->pin_defs[i]));
        #ifndef BL_ERROR_HALT
        if ( retval != BL_SUCCESS ) {
            goto error;
        }
        #endif
    }
    return meta;

    #ifndef BL_ERROR_HALT
    error:
    #ifdef BL_ERROR_VERBOSE
    print_strings(7, "could not set up ", "instance: '", name, "' of ", "component: '", comp_def->name, "'\n");
    #endif
    halt_or_return(NULL);
    #endif
}

struct bl_instance_meta_s *bl_instance_create(char const *name, bl_comp_def_t const *comp_def, uint32_t data_size)
{
    bl_instance_meta_t *meta;
    void *data;
    int ll_result;

    if ( data_size == 0 ) {
        data_size = comp_def->data_size;
    }
    if ( data_size >= BL_INSTANCE_DATA_MAX_SIZE ) {
        #ifdef BL_ERROR_VERBOSE
        print_string("instance data too large\n");
        #endif
        goto error;
    }
    // allocate memory for metadata
    meta = alloc_from_meta_pool(sizeof(bl_instance_meta_t));
    // allocate memory for realtime data
    data = alloc_from_rt_pool(data_size);
    #ifndef BL_ERROR_HALT
    if ( ( meta == NULL ) || ( data == NULL ) ) {
        goto error;
    }
    #endif
    // initialise metadata fields
    meta->comp_def = comp_def;
    meta->data_index = TO_RT_INDEX(data);
    meta->data_size = TO_INSTANCE_SIZE(data_size);
    meta->name = name;
    meta->pin_list = NULL;
    // add metadata to master instance list
    ll_result = ll_insert((void **)(&instance_root), (void *)meta, instance_meta_compare_names);
    if ( ll_result != 0 ) {
        #ifdef BL_ERROR_VERBOSE
        print_string("duplicate name\n");
        #endif
        goto error;
    }
    return meta;

    error:
    #ifdef BL_ERROR_VERBOSE
    print_strings(4, "could not create ", "instance: '", name, "'\n");
    #endif
    halt_or_return(NULL);
}

void *bl_instance_data_addr(struct bl_instance_meta_s *inst)
{
    return TO_RT_ADDR(inst->data_index);
}

bl_retval_t bl_instance_add_pin(struct bl_instance_meta_s *inst, bl_pin_def_t const *def)
{
    bl_pin_meta_t *meta;
    bl_sig_data_t *data;
    bl_sig_data_t **ptr_addr;
    int ll_result;

    // allocate memory for metadata
    meta = alloc_from_meta_pool(sizeof(bl_pin_meta_t));
    // allocate memory for dummy signal
    data = alloc_from_rt_pool(sizeof(bl_sig_data_t));
    #ifndef BL_ERROR_HALT
    if ( ( meta == NULL ) || ( data == NULL ) ) {
        goto error;    
    }
    #endif
    // determine address of pin pointer
    ptr_addr = (bl_sig_data_t **)((char *)(TO_RT_ADDR(inst->data_index)) + def->data_offset);
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
    // add metadata to instances's pin list
    ll_result = ll_insert((void **)(&(inst->pin_list)), (void *)meta, pin_meta_compare_names);
    if ( ll_result != 0 ) {
        #ifdef BL_ERROR_VERBOSE
        print_string("duplicate name\n");
        #endif
        goto error;
    }
    return BL_SUCCESS;

    error:
    #ifdef BL_ERROR_VERBOSE
    print_strings(6, "could not create ", "pin: '", inst->name, ".", def->name, "'\n");
    #endif
    halt_or_return(BL_ERR_GENERAL);
}

