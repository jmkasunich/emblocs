#include "emblocs.h"
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
bl_inst_meta_t *instance_root;

/* root of signal linked list */
bl_sig_meta_t *signal_root;

/* root of thread linked list */
bl_thread_meta_t *thread_root;


/* linked list callback functions */
static int inst_meta_compare_name_key(void *node, void *key)
{
    bl_inst_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
}

static int inst_meta_compare_index_key(void *node, void *key)
{
    bl_inst_meta_t *np = node;
    uint32_t *kp = key;
    return (np->data_index - *kp);
}

static int inst_meta_compare_names(void *node1, void *node2)
{
    bl_inst_meta_t  *np1 = node1;
    bl_inst_meta_t  *np2 = node2;
    return strcmp(np1->name, np2->name);
}

static int pin_meta_compare_name_key(void *node, void *key)
{
    bl_pin_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
}

static int pin_meta_compare_names(void *node1, void *node2)
{
    bl_pin_meta_t  *np1 = node1;
    bl_pin_meta_t  *np2 = node2;
    return strcmp(np1->name, np2->name);
}

static int sig_meta_compare_name_key(void *node, void *key)
{
    bl_sig_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
}

static int sig_meta_compare_index_key(void *node, void *key)
{
    bl_sig_meta_t *np = node;
    uint32_t *kp = key;
    return np->data_index-*kp;
}

static int sig_meta_compare_names(void *node1, void *node2)
{
    bl_sig_meta_t  *np1 = node1;
    bl_sig_meta_t  *np2 = node2;
    return strcmp(np1->name, np2->name);
}

static int thread_meta_compare_name_key(void *node, void *key)
{
    bl_thread_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
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

bl_inst_meta_t *bl_instance_new(char const *name, bl_comp_def_t const *comp_def, void const *personality)
{
    bl_inst_meta_t *retval;

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
        halt_or_return(NULL);
    }
    return retval;
}

bl_sig_meta_t *bl_signal_new(char const *name, bl_type_t type)
{
    bl_sig_meta_t *meta;
    bl_sig_data_t *data;
    int ll_result;

    // allocate memory for metadata
    meta = alloc_from_meta_pool(sizeof(bl_sig_meta_t));
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

bl_retval_t bl_link_pin_to_signal(bl_pin_meta_t const *pin, bl_sig_meta_t const *sig )
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

bl_retval_t bl_link_pin_to_signal_by_names(char const *inst_name, char const *pin_name, char const *sig_name )
{
    bl_retval_t retval;
    bl_pin_meta_t *pin;
    bl_sig_meta_t *sig;

    pin = bl_find_pin_by_names(inst_name, pin_name);
    sig = bl_find_signal_by_name(sig_name);
    #ifndef BL_ERROR_HALT
    if ( ( pin == NULL ) || ( sig == NULL ) ) {
        retval = BL_ERR_NOT_FOUND;
        goto done;
    }
    #endif
    retval = bl_link_pin_to_signal(pin, sig);
    #ifndef BL_ERROR_HALT
    done:
    if ( retval != BL_SUCCESS ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(9, "could not link ", "pin: '", inst_name, ".", pin_name, "' to ", "signal: '", sig_name, "'\n");
        #endif
    }
    #endif
    return retval;
}

bl_retval_t bl_unlink_pin(bl_pin_meta_t const *pin)
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

bl_retval_t bl_unlink_pin_by_name(char const *inst_name, char const *pin_name)
{
    bl_retval_t retval;
    bl_pin_meta_t *pin;

    pin = bl_find_pin_by_names(inst_name, pin_name);
    #ifndef BL_ERROR_HALT
    if ( pin == NULL ) {
        retval = BL_ERR_NOT_FOUND;
        goto done;
    }
    #endif
    retval = bl_unlink_pin(pin);
    #ifndef BL_ERROR_HALT
    done:
    if ( retval != BL_SUCCESS ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(6, "could not unlink ", "pin: '", inst_name, ".", pin_name, "'\n");
        #endif
    }
    #endif
    return retval;
}

bl_retval_t bl_set_sig(bl_sig_meta_t const *sig, bl_sig_data_t const *value)
{
    bl_sig_data_t *sig_data;

    sig_data = TO_RT_ADDR(sig->data_index);
    *sig_data = *value;
    return BL_SUCCESS;
}

bl_retval_t bl_set_sig_by_name(char const *sig_name, bl_sig_data_t const *value)
{
    bl_retval_t retval;
    bl_sig_meta_t *sig;

    sig = bl_find_signal_by_name(sig_name);
    #ifndef BL_ERROR_HALT
    if ( sig == NULL ) {
        retval = BL_ERR_NOT_FOUND;
        goto done;
    }
    #endif
    retval = bl_set_sig(sig, value);
    #ifndef BL_ERROR_HALT
    done:
    if ( retval != BL_SUCCESS ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(4, "could not set ", "signal: '", sig_name, "'\n");
        #endif
    }
    #endif
    return retval;
}

bl_retval_t bl_set_pin(bl_pin_meta_t const *pin, bl_sig_data_t const *value)
{
    bl_sig_data_t **pin_ptr, *sig_data;

    pin_ptr = TO_RT_ADDR(pin->ptr_index);
    sig_data = *pin_ptr;
    *sig_data = *value;
    return BL_SUCCESS;
}

bl_retval_t bl_set_pin_by_name(char const *inst_name, char const *pin_name, bl_sig_data_t const *value)
{
    bl_retval_t retval;
    bl_pin_meta_t *pin;

    pin = bl_find_pin_by_names(inst_name, pin_name);
    #ifndef BL_ERROR_HALT
    if ( pin == NULL ) {
        retval = BL_ERR_NOT_FOUND;
        goto done;
    }
    #endif
    retval = bl_set_pin(pin, value);
    #ifndef BL_ERROR_HALT
    done:
    if ( retval != BL_SUCCESS ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(6, "could not set ", "pin: '", inst_name, ".", pin_name, "'\n");
        #endif
    }
    #endif
    return retval;
}

bl_thread_meta_t *bl_thread_new(char const *name, uint32_t period_ns, bl_nofp_t nofp)
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

bl_retval_t bl_add_funct_to_thread(bl_funct_def_t const *funct, bl_inst_meta_t const *inst, bl_thread_meta_t const *thread)
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
    new_entry->inst_data = TO_RT_ADDR(inst->data_index);
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

bl_retval_t bl_add_funct_to_thread_by_names(char const *inst_name, char const *funct_name, char const *thread_name)
{
    bl_retval_t retval;
    bl_inst_meta_t *inst;
    bl_funct_def_t const *funct;
    bl_thread_meta_t *thread;

    inst = bl_find_instance_by_name(inst_name);
    #ifndef BL_ERROR_HALT
    if ( inst == NULL ) {
        retval = BL_ERR_NOT_FOUND;
        goto done;
    }
    #endif
    funct = bl_find_funct_def_in_instance_by_name(funct_name, inst);
    thread = bl_find_thread_by_name(thread_name);
    #ifndef BL_ERROR_HALT
    if ( ( funct == NULL ) || ( thread == NULL ) ) {
        retval = BL_ERR_NOT_FOUND;
        goto done;
    }
    #endif
    retval = bl_add_funct_to_thread(funct, inst, thread);
    #ifndef BL_ERROR_HALT
    done:
    if ( retval != BL_SUCCESS ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(9, "could not link ", "function: '", inst_name, ".", funct_name, "' to ", "thread: '", thread_name, "'\n");
        #endif
    }
    #endif
    return retval;
}

void bl_thread_update(bl_thread_data_t const *thread, uint32_t period_ns)
{
    bl_thread_entry_t *entry;

    if ( period_ns == 0 ) {
        period_ns = thread->period_ns;
    }
    entry = thread->start;
    while ( entry != NULL ) {
        (*(entry->funct))(entry->inst_data, period_ns);
        entry = entry->next;
    }
}


bl_inst_meta_t *bl_default_setup(char const *name, bl_comp_def_t const *comp_def)
{
    bl_inst_meta_t *meta;
    bl_pin_meta_t *pin __attribute__ ((unused));

    meta = bl_inst_create(name, comp_def, 0);
    #ifndef BL_ERROR_HALT
    if ( meta == NULL ) {
        goto error;
    }
    #endif
    for ( int i = 0 ; i < comp_def->pin_count ; i++ ) {
        pin = bl_inst_add_pin(meta, &(comp_def->pin_defs[i]));
        #ifndef BL_ERROR_HALT
        if ( pin == NULL ) {
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

bl_inst_meta_t *bl_inst_create(char const *name, bl_comp_def_t const *comp_def, uint32_t data_size)
{
    bl_inst_meta_t *meta;
    void *data;
    int ll_result;

    if ( data_size == 0 ) {
        data_size = comp_def->data_size;
    }
    if ( data_size >= BL_INST_DATA_MAX_SIZE ) {
        #ifdef BL_ERROR_VERBOSE
        print_string("instance data too large\n");
        #endif
        goto error;
    }
    // allocate memory for metadata
    meta = alloc_from_meta_pool(sizeof(bl_inst_meta_t));
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
    meta->data_size = TO_INST_SIZE(data_size);
    meta->name = name;
    meta->pin_list = NULL;
    // add metadata to master instance list
    ll_result = ll_insert((void **)(&instance_root), (void *)meta, inst_meta_compare_names);
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

bl_pin_meta_t *bl_inst_add_pin(bl_inst_meta_t *inst, bl_pin_def_t const *def)
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
    return meta;

    error:
    #ifdef BL_ERROR_VERBOSE
    print_strings(6, "could not create ", "pin: '", inst->name, ".", def->name, "'\n");
    #endif
    halt_or_return(NULL);
}


bl_inst_meta_t *bl_find_instance_by_name(char const *name)
{
    bl_inst_meta_t *retval;

    retval = ll_find((void **)(&(instance_root)), (void *)(name), inst_meta_compare_name_key);
    if ( retval == NULL ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(4, "not found: ", "instance: '", name, "'\n");
        #endif
        halt_or_return(NULL);
    }
    return retval;
}

bl_inst_meta_t *bl_find_instance_by_data_addr(void *data_addr)
{
    uint32_t index;
    bl_inst_meta_t *retval;

    index = TO_RT_INDEX(data_addr);
    retval = ll_find((void **)(&(instance_root)), (void *)(&index), inst_meta_compare_index_key);
    if ( retval == NULL ) {
        #ifdef BL_ERROR_VERBOSE
        print_string("data corruption\n");
        #endif
        halt();
    }
    return retval;
}

bl_inst_meta_t *bl_find_instance_from_thread_entry(bl_thread_entry_t const *entry)
{
    return bl_find_instance_by_data_addr(entry->inst_data);
}

bl_pin_meta_t *bl_find_pin_in_instance_by_name(char const *name, bl_inst_meta_t const *inst)
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

bl_pin_meta_t *bl_find_pin_by_names(char const *inst_name, char const *pin_name)
{
    bl_inst_meta_t *inst;
    
    inst = bl_find_instance_by_name(inst_name);
    #ifndef BL_ERROR_HALT
    if ( inst == NULL ) {
        return NULL;
    }
    #endif
    return bl_find_pin_in_instance_by_name(pin_name, inst);
}

bl_sig_meta_t *bl_find_signal_by_name(char const *name)
{
    bl_sig_meta_t *retval;

    retval = ll_find((void **)(&(signal_root)), (void *)(name), sig_meta_compare_name_key);
    if ( retval == NULL ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(4, "not found: ", "signal: '", name, "'\n");
        #endif
        halt_or_return(NULL);
    }
    return retval;
}

bl_sig_meta_t *bl_find_signal_by_index(uint32_t index)
{
    bl_sig_meta_t *retval;

    retval = ll_find((void **)(&(signal_root)), (void *)(&index), sig_meta_compare_index_key);
    if ( retval == NULL ) {
        #ifdef BL_ERROR_VERBOSE
        print_string("data corruption\n");
        #endif
        halt();
    }
    return retval;
}

bl_thread_meta_t *bl_find_thread_by_name(char const *name)
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

bl_thread_data_t *bl_find_thread_data_by_name(char const *name)
{
    bl_thread_meta_t *thread;

    thread = bl_find_thread_by_name(name);
    #ifndef BL_ERROR_HALT
    if ( thread == NULL ) {
        return NULL;
    }
    #endif
    return TO_RT_ADDR(thread->data_index);
}

bl_funct_def_t *bl_find_funct_def_in_instance_by_name(char const *name, bl_inst_meta_t const *inst)
{
    bl_comp_def_t const *comp;
    bl_funct_def_t const *fdef;

    comp = inst->comp_def;
    for ( int n = 0 ; n < comp->funct_count ; n++ ) {
        fdef = &(comp->funct_defs[n]);
        if ( strcmp(name, fdef->name ) == 0 ) {
            return (bl_funct_def_t *)fdef;
        }
    }
    #ifdef BL_ERROR_VERBOSE
    print_strings(7, "not found: ", "function: '", name, "' in ", "instance: '", inst->name, "'\n");
    #endif
    halt_or_return(NULL);
}

bl_funct_def_t *bl_find_funct_def_by_names(char const *inst_name, char const *funct_name)
{
    bl_inst_meta_t *inst;

    inst = bl_find_instance_by_name(inst_name);
    #ifndef BL_ERROR_HALT
    if ( inst == NULL ) {
        return NULL;
    }
    #endif
    return bl_find_funct_def_in_instance_by_name(funct_name, inst);
}

bl_funct_def_t *bl_find_funct_def_in_instance_by_address(bl_rt_funct_t *addr, bl_inst_meta_t const *inst)
{
    bl_comp_def_t const *comp;
    bl_funct_def_t const *fdef;

    comp = inst->comp_def;
    for ( int n = 0 ; n < comp->funct_count ; n++ ) {
        fdef = &(comp->funct_defs[n]);
        if ( addr == fdef->fp ) {
            return (bl_funct_def_t *)fdef;
        }
    }
    #ifdef BL_ERROR_VERBOSE
    print_string("data corruption\n");
    #endif
    halt();
}

bl_funct_def_t *bl_find_funct_def_from_thread_entry(bl_thread_entry_t const *entry)
{
    bl_inst_meta_t *inst;

    inst = bl_find_instance_by_data_addr(entry->inst_data);
    return bl_find_funct_def_in_instance_by_address(entry->funct, inst);
}

int bl_find_pins_linked_to_signal(bl_sig_meta_t const *sig, void (*callback)(bl_inst_meta_t *inst, bl_pin_meta_t *pin))
{
    bl_inst_meta_t *inst;
    bl_pin_meta_t *pin;
    bl_sig_data_t *sp, **pp;
    int matches;

    sp = TO_RT_ADDR(sig->data_index);
    inst = instance_root;
    matches = 0;
    while ( inst != NULL ) {
        pin = inst->pin_list;
        while ( pin != NULL ) {
            pp = TO_RT_ADDR(pin->ptr_index);
            if ( *pp == sp ) {
                matches++;
                if ( callback != NULL ) {
                    callback(inst, pin);
                }
            }
            pin = pin->next;
        }
        inst = inst->next;
    }
    return matches;
}

int bl_find_functions_in_thread(bl_thread_meta_t const *thread, void (*callback)(bl_inst_meta_t *inst, bl_funct_def_t *funct))
{
    bl_thread_data_t *data;
    bl_thread_entry_t *entry;
    bl_inst_meta_t *inst;
    bl_funct_def_t *funct;
    int matches;

    data = TO_RT_ADDR(thread->data_index);
    entry = data->start;
    matches = 0;
    while ( entry != NULL ) {
        inst = bl_find_instance_by_data_addr(entry->inst_data);
        funct = bl_find_funct_def_in_instance_by_address(entry->funct, inst);
        matches++;
        if ( callback != NULL ) {
            callback(inst, funct);
        }
    }
    return matches;
}

