#include "emblocs.h"
#include "linked_list.h"
#include <assert.h>
#include <string.h>
#include "printing.h"

/***********************************************
 * memory pools
 */

uint32_t bl_rt_pool[BL_RT_POOL_SIZE >> 2]  __attribute__ ((aligned(4)));
static uint32_t *rt_pool_next = bl_rt_pool;
static int32_t rt_pool_avail = sizeof(bl_rt_pool);

uint32_t bl_meta_pool[BL_META_POOL_SIZE >> 2]  __attribute__ ((aligned(4)));
static uint32_t *meta_pool_next = bl_meta_pool;
static int32_t meta_pool_avail = sizeof(bl_meta_pool);

/* memory allocation functions */

static void *alloc_from_rt_pool(int32_t size)
{
    void *retval;

    assert ( size > 0 );
    // round size up to multiple of 4
    if ( size & 3 ) {
        size += 4;
        size &= ~3;
    }
    assert( rt_pool_avail >= size);
    retval = rt_pool_next;
    rt_pool_next += size/4;
    rt_pool_avail -= size;
    return retval;
}

static void *alloc_from_meta_pool(int32_t size)
{
    void *retval;

    assert ( size > 0 );
    // round size up to multiple of 4
    if ( size & 3 ) {
        size += 4;
        size &= ~3;
    }
    assert( meta_pool_avail >= size);
    retval = meta_pool_next;
    meta_pool_next += size/4;
    meta_pool_avail -= size;
    return retval;
}


/* root of instance linked list */
static bl_inst_meta_t *instance_root;

/* root of signal linked list */
static bl_sig_meta_t *signal_root;

/* root of thread linked list */
static bl_thread_meta_t *thread_root;


/* linked list callback functions */
static int inst_meta_cmp_name_key(void *node, void *key)
{
    bl_inst_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
}

static int inst_meta_cmp_index_key(void *node, void *key)
{
    bl_inst_meta_t *np = node;
    uint32_t *kp = key;
    return (np->data_index - *kp);
}

static int inst_meta_cmp_names(void *node1, void *node2)
{
    bl_inst_meta_t  *np1 = node1;
    bl_inst_meta_t  *np2 = node2;
    return strcmp(np1->name, np2->name);
}

static void inst_meta_print_node(void *node)
{
    bl_show_instance((bl_inst_meta_t *)node);
}

static int pin_meta_cmp_name_key(void *node, void *key)
{
    bl_pin_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
}

static int pin_meta_cmp_names(void *node1, void *node2)
{
    bl_pin_meta_t  *np1 = node1;
    bl_pin_meta_t  *np2 = node2;
    return strcmp(np1->name, np2->name);
}

static void pin_meta_print_node(void *node)
{
    bl_show_pin((bl_pin_meta_t *)node);
}

static int sig_meta_cmp_name_key(void *node, void *key)
{
    bl_sig_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
}

static int sig_meta_cmp_index_key(void *node, void *key)
{
    bl_sig_meta_t *np = node;
    uint32_t *kp = key;
    return np->data_index-*kp;
}

static int sig_meta_cmp_names(void *node1, void *node2)
{
    bl_sig_meta_t  *np1 = node1;
    bl_sig_meta_t  *np2 = node2;
    return strcmp(np1->name, np2->name);
}

static void sig_meta_print_node(void *node)
{
    bl_show_signal((bl_sig_meta_t *)node);
}

static int thread_meta_cmp_name_key(void *node, void *key)
{
    bl_thread_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
}

static int thread_meta_cmp_names(void *node1, void *node2)
{
    bl_thread_meta_t  *np1 = node1;
    bl_thread_meta_t  *np2 = node2;
    return strcmp(np1->name, np2->name);
}

static void thread_meta_print_node(void *node)
{
    bl_show_thread((bl_thread_meta_t *)node);
}



/**************************************************************
 * Top-level EMBLOCS API functions used to build a system     *
 **************************************************************/

bl_inst_meta_t *bl_instance_new(char const *name, bl_comp_def_t const *comp_def, void const *personality)
{
    if ( comp_def->setup == NULL ) {
        // no setup function, cannot support personality
        assert(personality == NULL);
        // call default setup function
        return bl_default_setup(name, comp_def);
    } else {
        // call component-specific setup function
        return comp_def->setup(name, comp_def, personality);
    }
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
    // initialize signal to zero
    data->u = 0;
    // initialise metadata fields
    meta->data_index = TO_RT_INDEX(data);
    meta->data_type = type;
    meta->name = name;
    // add metadata to master signal list
    ll_result = ll_insert((void **)(&(signal_root)), (void *)meta, sig_meta_cmp_names);
    assert(ll_result == 0);
    return meta;
}

bl_retval_t bl_link_pin_to_signal(bl_pin_meta_t const *pin, bl_sig_meta_t const *sig )
{
    bl_sig_data_t *sig_data_addr, **pin_ptr_addr;

    // check types
    if ( pin->data_type != sig->data_type ) {
        return BL_ERR_TYPE_MISMATCH;
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
    bl_pin_meta_t *pin;
    bl_sig_meta_t *sig;

    pin = bl_find_pin_by_names(inst_name, pin_name);
    if ( pin == NULL ) {
        return BL_ERR_PIN_NOT_FOUND;
    }
    sig = bl_find_signal_by_name(sig_name);
    if ( sig == NULL ) {
        return BL_ERR_SIG_NOT_FOUND;
    }
    return bl_link_pin_to_signal(pin, sig);
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
    bl_pin_meta_t *pin;

    pin = bl_find_pin_by_names(inst_name, pin_name);
    if ( pin == NULL ) {
        return BL_ERR_PIN_NOT_FOUND;
    }
    bl_unlink_pin(pin);
    return BL_SUCCESS;
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
    bl_sig_meta_t *sig;

    sig = bl_find_signal_by_name(sig_name);
    if ( sig == NULL ) {
        return BL_ERR_SIG_NOT_FOUND;
    }
    bl_set_sig(sig, value);
    return BL_SUCCESS;
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
    bl_pin_meta_t *pin;

    pin = bl_find_pin_by_names(inst_name, pin_name);
    if ( pin == NULL ) {
        return BL_ERR_PIN_NOT_FOUND;
    }
    bl_set_pin(pin, value);
    return BL_SUCCESS;
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
    // initialize data fields
    data->period_ns = period_ns;
    data->start = NULL;
    // initialise metadata fields
    meta->data_index = TO_RT_INDEX(data);
    meta->nofp = nofp;
    meta->name = name;
    // add metadata to master thread list
    ll_result = ll_insert((void **)(&(thread_root)), (void *)meta, thread_meta_cmp_names);
    assert(ll_result == 0);
    return meta;
}

bl_retval_t bl_add_funct_to_thread(bl_funct_def_t const *funct, bl_inst_meta_t const *inst, bl_thread_meta_t const *thread)
{
    bl_thread_entry_t *new_entry;
    bl_thread_data_t *thread_data;
    bl_thread_entry_t *prev, **prev_ptr;

    // validate floating point
    if ( ( thread->nofp == BL_NO_FP) && ( funct->nofp == BL_HAS_FP ) ) {
        return BL_ERR_TYPE_MISMATCH;
    }
    // allocate memory for thread entry
    new_entry = alloc_from_rt_pool(sizeof(bl_thread_entry_t));
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
    bl_inst_meta_t *inst;
    bl_funct_def_t const *funct;
    bl_thread_meta_t *thread;

    inst = bl_find_instance_by_name(inst_name);
    if ( inst == NULL ) {
        return BL_ERR_INST_NOT_FOUND;
    }
    funct = bl_find_funct_def_in_instance_by_name(funct_name, inst);
    if ( inst == NULL ) {
        return BL_ERR_FUNCT_NOT_FOUND;
    }
    thread = bl_find_thread_by_name(thread_name);
    if ( inst == NULL ) {
        return BL_ERR_THREAD_NOT_FOUND;
    }
    return bl_add_funct_to_thread(funct, inst, thread);
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

    meta = bl_inst_create(name, comp_def, 0);
    for ( int i = 0 ; i < comp_def->pin_count ; i++ ) {
        bl_inst_add_pin(meta, &(comp_def->pin_defs[i]));
    }
    return meta;
}

bl_inst_meta_t *bl_inst_create(char const *name, bl_comp_def_t const *comp_def, uint32_t data_size)
{
    bl_inst_meta_t *meta;
    void *data;
    int ll_result;

    if ( data_size == 0 ) {
        data_size = comp_def->data_size;
    }
    assert(data_size < BL_INST_DATA_MAX_SIZE);
    // allocate memory for metadata
    meta = alloc_from_meta_pool(sizeof(bl_inst_meta_t));
    // allocate memory for realtime data
    data = alloc_from_rt_pool(data_size);
    // initialise metadata fields
    meta->comp_def = comp_def;
    meta->data_index = TO_RT_INDEX(data);
    meta->data_size = TO_INST_SIZE(data_size);
    meta->name = name;
    meta->pin_list = NULL;
    // add metadata to master instance list
    ll_result = ll_insert((void **)(&instance_root), (void *)meta, inst_meta_cmp_names);
    assert(ll_result == 0);
    return meta;
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
    ll_result = ll_insert((void **)(&(inst->pin_list)), (void *)meta, pin_meta_cmp_names);
    assert(ll_result == 0);
    return meta;
}


bl_inst_meta_t *bl_find_instance_by_name(char const *name)
{
    return ll_find((void **)(&(instance_root)), (void *)(name), inst_meta_cmp_name_key);
}

bl_inst_meta_t *bl_find_instance_by_data_addr(void *data_addr)
{
    uint32_t index;

    index = TO_RT_INDEX(data_addr);
    return ll_find((void **)(&(instance_root)), (void *)(&index), inst_meta_cmp_index_key);
}

bl_inst_meta_t *bl_find_instance_from_thread_entry(bl_thread_entry_t const *entry)
{
    return bl_find_instance_by_data_addr(entry->inst_data);
}

bl_pin_meta_t *bl_find_pin_in_instance_by_name(char const *name, bl_inst_meta_t const *inst)
{
    return ll_find((void **)(&(inst->pin_list)), (void *)(name), pin_meta_cmp_name_key);
}

bl_pin_meta_t *bl_find_pin_by_names(char const *inst_name, char const *pin_name)
{
    bl_inst_meta_t *inst;
    
    inst = bl_find_instance_by_name(inst_name);
    if ( inst == NULL ) {
        return NULL;
    }
    return bl_find_pin_in_instance_by_name(pin_name, inst);
}

bl_sig_meta_t *bl_find_signal_by_name(char const *name)
{
    return ll_find((void **)(&(signal_root)), (void *)(name), sig_meta_cmp_name_key);
}

bl_sig_meta_t *bl_find_signal_by_index(uint32_t index)
{
    return ll_find((void **)(&(signal_root)), (void *)(&index), sig_meta_cmp_index_key);
}

bl_thread_meta_t *bl_find_thread_by_name(char const *name)
{
    return ll_find((void **)(&(thread_root)), (void *)(name), thread_meta_cmp_name_key);
}

bl_thread_data_t *bl_find_thread_data_by_name(char const *name)
{
    bl_thread_meta_t *thread;

    thread = bl_find_thread_by_name(name);
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
    return NULL;
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
    return NULL;
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
        assert(inst != NULL);
        funct = bl_find_funct_def_in_instance_by_address(entry->funct, inst);
        assert(funct != NULL);
        matches++;
        if ( callback != NULL ) {
            callback(inst, funct);
        }
    }
    return matches;
}


static char const * const types[] = {
    "float", "bit  ", "s32  ", "u32  "
};

#ifdef SHOW_VERBOSE
static char const * const dirs[] = {
    "xxx", "in ", "out", "i/o"
};
#endif

static char const * const dirs_ps[] = {
    "xxx", "<==", "==>", "<=>"
};

static char const * const dirs_sp[] = {
    "xxx", "==>", "<==", "<=>"
};

void bl_show_memory_status(void)
{
    printf("RT pool:   %d/%d, %d free\n", sizeof(bl_rt_pool)-rt_pool_avail, sizeof(bl_rt_pool), rt_pool_avail);
    printf("Meta pool: %d/%d, %d free\n", sizeof(bl_meta_pool)-meta_pool_avail, sizeof(bl_meta_pool), meta_pool_avail);
}

void bl_show_instance(bl_inst_meta_t const *inst)
{
#ifdef SHOW_VERBOSE
    printf("INST: %20s <= %20s @ %p, %d RT bytes @ [%3d]=%p\n", inst->name, inst->comp_def->name,
                    inst, inst->data_size, inst->data_index, TO_RT_ADDR(inst->data_index) );
#else
    printf("instance '%s' of component '%s'\n", inst->name, inst->comp_def->name);
#endif
    bl_show_all_pins_of_instance(inst);
}

void bl_show_all_instances(void)
{
    int ll_result;

    printf("List of all instances:\n");
    ll_result = ll_traverse((void **)(&instance_root), inst_meta_print_node);
    printf("Total of %d instances\n", ll_result);
}

void bl_show_pin(bl_pin_meta_t const *pin)
{
#ifdef SHOW_VERBOSE
    bl_sig_data_t *dummy_addr, **ptr_addr, *ptr_val;

    dummy_addr = (bl_sig_data_t *)TO_RT_ADDR(pin->dummy_index);
    ptr_addr = (bl_sig_data_t **)TO_RT_ADDR(pin->ptr_index);
    ptr_val = *ptr_addr;

    printf(" PIN: %20s  %s, %s @ %p, dummy @ [%3d]=%p, ptr @ [%3d]=%p, points at %p ",
                            pin->name, types[pin->data_type], dirs[pin->pin_dir], pin,
                            pin->dummy_index, dummy_addr, pin->ptr_index, ptr_addr, ptr_val );
    bl_show_pin_linkage(pin);
    printf(" = ");
    bl_show_pin_value(pin);
    printf("\n");
#else
    printf("  %-12s ", pin->name);
    bl_show_pin_linkage(pin);
    printf(" = %s : ", types[pin->data_type]);
    bl_show_pin_value(pin);
    printf("\n");
#endif

}

void bl_show_all_pins_of_instance(bl_inst_meta_t const *inst)
{
    int ll_result;

    ll_result = ll_traverse((void **)(&inst->pin_list), pin_meta_print_node);
    printf("    %d pins\n", ll_result);
}

void bl_show_pin_value(bl_pin_meta_t const *pin)
{
    bl_sig_data_t **pin_ptr_addr, *data;

    pin_ptr_addr = (bl_sig_data_t **)TO_RT_ADDR(pin->ptr_index);
    data = *pin_ptr_addr;
    bl_show_sig_data_t_value(data, pin->data_type);
}

void bl_show_pin_linkage(bl_pin_meta_t const *pin)
{
    bl_sig_data_t *dummy_addr, **ptr_addr, *ptr_val;
    char const *dir;
    bl_sig_meta_t *sig;

    dummy_addr = (bl_sig_data_t *)TO_RT_ADDR(pin->dummy_index);
    ptr_addr = (bl_sig_data_t **)TO_RT_ADDR(pin->ptr_index);
    ptr_val = *ptr_addr;
    dir = dirs_ps[pin->pin_dir];
    if ( ptr_val == dummy_addr ) {
        printf("%s %-12s", dir, " ");
    } else {
        // find the matching signal
        sig = bl_find_signal_by_index(TO_RT_INDEX(ptr_val));
        assert(sig != NULL);
        printf("%s %-12s", dir, sig->name);
    }
}

void bl_show_signal(bl_sig_meta_t const *sig)
{
#ifdef SHOW_VERBOSE
    bl_sig_data_t *data_addr;

    data_addr = TO_RT_ADDR(sig->data_index);
    printf("SIG: %20s  %s @ %p, data @ [%3d]=%p = ",
                            sig->name, types[sig->data_type], sig, sig->data_index, data_addr);
    bl_show_signal_value(sig);
    printf("\n");
    bl_show_signal_linkage(sig);
#else
    printf("  %-12s = %s : ", sig->name, types[sig->data_type]);
    bl_show_signal_value(sig);
    printf("\n");
    bl_show_signal_linkage(sig);
#endif
}

void bl_show_signal_value(bl_sig_meta_t const *sig)
{
    bl_sig_data_t *data;

    data = (bl_sig_data_t *)TO_RT_ADDR(sig->data_index);
    bl_show_sig_data_t_value(data, sig->data_type);
}

static void signal_linkage_callback(bl_inst_meta_t *inst, bl_pin_meta_t *pin)
{
    char const *dir;

    dir = dirs_sp[pin->pin_dir];
    printf("     %s %s.%s\n", dir, inst->name, pin->name);
}

void bl_show_signal_linkage(bl_sig_meta_t const *sig)
{
    bl_find_pins_linked_to_signal(sig, signal_linkage_callback);
}

void bl_show_sig_data_t_value(bl_sig_data_t const *data, bl_type_t type)
{
    switch(type) {
    case BL_TYPE_BIT:
        if ( data->b ) {
            printf(" TRUE");
        } else {
            printf("FALSE");
        }
        break;
    case BL_TYPE_FLOAT:
        printf("%f", data->f);
        break;
    case BL_TYPE_S32:
        printf("%d", data->s);
        break;
    case BL_TYPE_U32:
        printf("%u", data->u);
        break;
    default:
        assert(0);
    }
}

void bl_show_all_signals(void)
{
    int ll_result;

    printf("List of all signals:\n");
    ll_result = ll_traverse((void **)(&signal_root), sig_meta_print_node);
    printf("Total of %d signals\n", ll_result);
}

void bl_show_thread_entry(bl_thread_entry_t const *entry)
{
#ifdef SHOW_VERBOSE
    printf("  thread_entry @[%d]=%p, calls %p, inst data @%p\n", TO_RT_INDEX(entry), entry, entry->funct, entry->inst_data);
#else
    bl_inst_meta_t *inst;
    bl_funct_def_t *funct;

    inst = bl_find_instance_by_data_addr(entry->inst_data);
    funct = bl_find_funct_def_in_instance_by_address(entry->funct, inst);
    printf("     %s.%s\n", inst->name, funct->name);
#endif
}

void bl_show_thread(bl_thread_meta_t const *thread)
{
#ifdef SHOW_VERBOSE
    bl_thread_data_t *data;
    bl_thread_entry_t *entry;

    data = TO_RT_ADDR(thread->data_index);
    entry = data->start;
    printf(" thread '%s' @[%d]=%p, no_fp = %d, period_ns = %d, RT data at [%d]=%p\n", thread->name, 
                                TO_RT_INDEX(thread), thread, thread->nofp, data->period_ns,
                                thread->data_index, data);
    while ( entry != NULL ) {
        bl_show_thread_entry(entry);
        entry = entry->next;
    }
#else
    bl_thread_data_t *data;
    bl_thread_entry_t *entry;
    char *fp_str;

    data = TO_RT_ADDR(thread->data_index);
    entry = data->start;
    if ( thread->nofp ) {
        fp_str = "no fp ";
    } else {
        fp_str = "has fp";
    }
    printf("  %-12s = %s : %10d nsec\n", thread->name, fp_str, data->period_ns);
    while ( entry != NULL ) {
        bl_show_thread_entry(entry);
        entry = entry->next;
    }
#endif
}

void bl_show_all_threads(void)
{
    int ll_result;

    printf("List of all threads:\n");
    ll_result = ll_traverse((void **)(&thread_root), thread_meta_print_node);
    printf("Total of %d threads\n", ll_result);
}

/**************************************************************
 * These functions support building a system from arrays of
 * structs and/or strings in flash.
 */

void bl_init_instances(bl_inst_def_t const instances[])
{
    bl_inst_def_t const *idp;  // instance definition pointer
    bl_inst_meta_t *inst;

    idp = instances;
    while ( idp->name != NULL ) {
        inst = bl_instance_new(idp->name, idp->comp_def, idp->personality);
        assert(inst != NULL);
        idp++;
    }
}

static int is_sig_type_str(char const *str, bl_type_t *result)
{
    if ( strcmp(str, "BIT") == 0 ) {
        *result = BL_TYPE_BIT;
        return 1;
    }
    if ( strcmp(str, "FLOAT") == 0 ) {
        *result = BL_TYPE_FLOAT;
        return 1;
    }
    if ( strcmp(str, "S32") == 0 ) {
        *result = BL_TYPE_S32;
        return 1;
    }
    if ( strcmp(str, "U32") == 0 ) {
        *result = BL_TYPE_U32;
        return 1;
    }
    return 0;
}

void bl_init_nets(char const *const nets[])
{
    bl_retval_t retval;
    bl_type_t net_type;
    bl_sig_meta_t *sig;
    bl_inst_meta_t *inst;
    bl_pin_meta_t *pin;
    enum {
        START,
        GET_SIG,
        GOT_SIG,
        GET_PIN
    } state;

    state = START;
    while ( *nets != NULL ) {
        switch (state) {
        case START:
            if ( is_sig_type_str(*nets, &net_type) ) {
                state = GET_SIG;
            } else {
                assert(0);
            }
            break;
        case GET_SIG:
            sig = bl_signal_new(*nets, net_type);
            assert(sig != NULL);
            state = GOT_SIG;
            break;
        case GOT_SIG:
            if ( is_sig_type_str(*nets, &net_type) ) {
                // done with previous net, start a new one
                state = GET_SIG;
            } else {
                inst = bl_find_instance_by_name(*nets);
                assert(inst != NULL);
                state = GET_PIN;
            }
            break;
        case GET_PIN:
            pin = bl_find_pin_in_instance_by_name(*nets, inst);
            assert(pin != NULL);
            retval = bl_link_pin_to_signal(pin, sig);
            assert(retval == BL_SUCCESS);
            state = GOT_SIG;
            break;
        default:
            assert(0);
        }
        nets++;
    }
}

void bl_init_setsigs(bl_setsig_def_t const setsigs[])
{
    bl_setsig_def_t const *sdp;
    bl_retval_t retval;

    sdp = setsigs;
    while ( sdp->name != NULL ) {
        retval = bl_set_sig_by_name(sdp->name, &sdp->value);
        assert(retval == BL_SUCCESS);
        sdp++;
    }
}

void bl_init_setpins(bl_setpin_def_t const setpins[])
{
    bl_setpin_def_t const *sdp;
    bl_retval_t retval;

    sdp = setpins;
    while ( sdp->inst_name != NULL ) {
        retval = bl_set_pin_by_name(sdp->inst_name, sdp->pin_name, &sdp->value);
        assert(retval == BL_SUCCESS);
        sdp++;
    }
}

static int is_thread_type_str(char const *str, bl_nofp_t *result)
{
    if ( strcmp(str, "HAS_FP") == 0 ) {
        *result = BL_HAS_FP;
        return 1;
    }
    if ( strcmp(str, "NO_FP") == 0 ) {
        *result = BL_NO_FP;
        return 1;
    }
    return 0;
}

static int is_uint32_str(char const *str, uint32_t *result)
{
    uint32_t r = 0;

    do {
        if ( ( *str < '0' ) || ( *str > '9' )  ) {
            return 0;
        }
        r *= 10;
        r += *str - '0';
        str++;
    } while ( *str != '\0' );
    *result = r;
    return 1;
}

void bl_init_threads(char const * const threads[])
{
    bl_retval_t retval;
    bl_nofp_t thread_type;
    uint32_t period_ns;
    bl_thread_meta_t *thread;
    bl_inst_meta_t *inst;
    bl_funct_def_t const *funct_def;

    enum {
        START,
        GET_PERIOD,
        GET_NAME,
        GOT_NAME,
        GET_FUNCT
    } state;

    state = START;
    while ( *threads != NULL ) {
        switch (state) {
        case START:
            if ( is_thread_type_str(*threads, &thread_type) ) {
                state = GET_PERIOD;
            } else {
                assert(0);
            }
            break;
        case GET_PERIOD:
            if ( ! is_uint32_str(*threads, &period_ns) ) {
                assert(0);
            }
            state = GET_NAME;
            break;
        case GET_NAME:
            thread = bl_thread_new(*threads, period_ns, thread_type);
            assert(thread != NULL);
            state = GOT_NAME;
            break;
        case GOT_NAME:
            if ( is_thread_type_str(*threads, &thread_type) ) {
                // done with previous thread, start a new one
                state = GET_PERIOD;
            } else {
                inst = bl_find_instance_by_name(*threads);
                assert(inst != NULL);
                state = GET_FUNCT;
            }
            break;
        case GET_FUNCT:
            funct_def = bl_find_funct_def_in_instance_by_name(*threads, inst);
            assert(funct_def != NULL);
            retval = bl_add_funct_to_thread(funct_def, inst, thread);
            assert(retval == BL_SUCCESS);
            state = GOT_NAME;
            break;
        default:
            assert(0);
        }
        threads++;
    }
}

