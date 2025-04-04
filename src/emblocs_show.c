#include "emblocs_priv.h"
#include "linked_list.h"
#include "printing.h"

#define halt()  do {} while (1)

/**************************************************************
 * Helper functions for finding things in the metadata
 *
 * The first group finds the single matching item.
 * The second group finds the zero or more matching items,
 * calls a callback functions for each match (if 'callback'
 * is not NULL), and returns the number of matches.
 */
static bl_instance_meta_t *bl_find_instance_by_data_addr(void *data_addr);
//static bl_instance_meta_t *bl_find_instance_from_thread_entry(bl_thread_entry_t const *entry);
static bl_signal_meta_t *bl_find_signal_by_index(uint32_t index);
static bl_function_def_t *bl_find_function_def_in_instance_by_address(bl_rt_function_t *addr, bl_instance_meta_t const *inst);
//static bl_function_def_t *bl_find_function_def_from_thread_entry(bl_thread_entry_t const *entry);

static int bl_find_pins_linked_to_signal(bl_signal_meta_t const *sig, void (*callback)(bl_instance_meta_t *inst, bl_pin_meta_t *pin));
//static int bl_find_functions_in_thread(bl_thread_meta_t const *thread, void (*callback)(bl_instance_meta_t *inst, bl_function_def_t *funct));

static void bl_show_all_pins_of_instance(bl_instance_meta_t const *inst);
static void bl_show_all_functions_of_instance(bl_instance_meta_t const *inst);
static void bl_show_pin_value(bl_pin_meta_t const *pin);
static void bl_show_pin_linkage(bl_pin_meta_t const *pin);
static void bl_show_signal_value(bl_signal_meta_t const *sig);
static void bl_show_signal_linkage(bl_signal_meta_t const *sig);
static void bl_show_sig_data_t_value(bl_sig_data_t const *data, bl_type_t type);
static void bl_show_function_rtdata(bl_function_rtdata_t const *funct);


static char const * const types[] = {
    "float", "bit  ", "s32  ", "u32  "
};

#ifdef BL_SHOW_VERBOSE
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

/* I do a bunch of pointer manipulation 
   and type-punning in this file */
#pragma GCC optimize ("no-strict-aliasing")

void bl_show_memory_status(void)
{
    printf("RT pool:   %d/%d, %d free\n", bl_rt_pool_size-bl_rt_pool_avail, bl_rt_pool_size, bl_rt_pool_avail);
    printf("Meta pool: %d/%d, %d free\n", bl_meta_pool_size-bl_meta_pool_avail, bl_meta_pool_size, bl_meta_pool_avail);
}

void bl_show_instance(struct bl_instance_meta_s const *inst)
{
#ifdef BL_SHOW_VERBOSE
    printf("INST: %20s <= %20s @ %p, %d RT bytes @ [%3d]=%p\n", inst->name, inst->comp_def->name,
                    inst, inst->data_size, inst->data_index, TO_RT_ADDR(inst->data_index) );
#else
    printf("instance '%s' of component '%s'\n", inst->name, inst->comp_def->name);
#endif
    bl_show_all_pins_of_instance(inst);
    bl_show_all_functions_of_instance(inst);
}

static void instance_meta_print_node(void *node)
{
    bl_show_instance((bl_instance_meta_t *)node);
}

void bl_show_all_instances(void)
{
    int ll_result;

    printf("List of all instances:\n");
    ll_result = ll_traverse((void **)(&instance_root), instance_meta_print_node);
    printf("Total of %d instances\n", ll_result);
}

void bl_show_pin(bl_pin_meta_t const *pin)
{
#ifdef BL_SHOW_VERBOSE
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

static void pin_meta_print_node(void *node)
{
    bl_show_pin((bl_pin_meta_t *)node);
}

static void bl_show_all_pins_of_instance(bl_instance_meta_t const *inst)
{
    int ll_result;

    ll_result = ll_traverse((void **)(&inst->pin_list), pin_meta_print_node);
    printf("    %d pins\n", ll_result);
}

static void bl_show_pin_value(bl_pin_meta_t const *pin)
{
    bl_sig_data_t **pin_ptr_addr, *data;

    pin_ptr_addr = (bl_sig_data_t **)TO_RT_ADDR(pin->ptr_index);
    data = *pin_ptr_addr;
    bl_show_sig_data_t_value(data, pin->data_type);
}

static void bl_show_pin_linkage(bl_pin_meta_t const *pin)
{
    bl_sig_data_t *dummy_addr, **ptr_addr, *ptr_val;
    char const *dir;
    bl_signal_meta_t *sig;

    dummy_addr = (bl_sig_data_t *)TO_RT_ADDR(pin->dummy_index);
    ptr_addr = (bl_sig_data_t **)TO_RT_ADDR(pin->ptr_index);
    ptr_val = *ptr_addr;
    dir = dirs_ps[pin->pin_dir];
    if ( ptr_val == dummy_addr ) {
        printf("%s %-12s", dir, " ");
    } else {
        // find the matching signal
        sig = bl_find_signal_by_index(TO_RT_INDEX(ptr_val));
        printf("%s %-12s", dir, sig->name);
    }
}

void bl_show_function(bl_function_meta_t const *funct)
{
    bl_thread_meta_t *thread;

#ifdef BL_SHOW_VERBOSE
    bl_function_rtdata_t *rtdata_addr = (bl_function_rtdata_t *)TO_RT_ADDR(funct->rtdata_index);
    printf(" FUNCT: %20s  %s @ %p, rtdata @ [%3d]=%p\n",
                            funct->name, nofp[funct->nofp], funct,
                            funct->rtdata_index, rtdata_addr);
#else
    printf("  %-12s ", funct->name);
    if ( funct->thread_index == BL_META_MAX_INDEX ) {
        printf(" (no thread)");
    } else {
        thread = TO_META_ADDR(funct->thread_index);
        printf(" %s", thread->name);
    }
    printf("\n");
#endif
}

static void function_meta_print_node(void *node)
{
    bl_show_function((bl_function_meta_t *)node);
}

static void bl_show_all_functions_of_instance(bl_instance_meta_t const *inst)
{
    int ll_result;

    ll_result = ll_traverse((void **)(&inst->function_list), function_meta_print_node);
    printf("    %d functions\n", ll_result);
}

void bl_show_signal(struct bl_signal_meta_s const *sig)
{
#ifdef BL_SHOW_VERBOSE
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

static void bl_show_signal_value(bl_signal_meta_t const *sig)
{
    bl_sig_data_t *data;

    data = (bl_sig_data_t *)TO_RT_ADDR(sig->data_index);
    bl_show_sig_data_t_value(data, sig->data_type);
}

static void signal_linkage_callback(bl_instance_meta_t *inst, bl_pin_meta_t *pin)
{
    char const *dir;

    dir = dirs_sp[pin->pin_dir];
    printf("     %s %s.%s\n", dir, inst->name, pin->name);
}

static void bl_show_signal_linkage(bl_signal_meta_t const *sig)
{
    bl_find_pins_linked_to_signal(sig, signal_linkage_callback);
}

static void bl_show_sig_data_t_value(bl_sig_data_t const *data, bl_type_t type)
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
        halt();
    }
}

static void sig_meta_print_node(void *node)
{
    bl_show_signal((bl_signal_meta_t *)node);
}

void bl_show_all_signals(void)
{
    int ll_result;

    printf("List of all signals:\n");
    ll_result = ll_traverse((void **)(&signal_root), sig_meta_print_node);
    printf("Total of %d signals\n", ll_result);
}

static void bl_show_function_rtdata(bl_function_rtdata_t const *rtdata)
{
#ifdef BL_SHOW_VERBOSE
    printf("  function_rtdata @[%d]=%p, calls %p, inst data @%p\n", TO_RT_INDEX(rtdata), rtdata, rtdata->funct, rtdata->instance_data);
#else
    bl_instance_meta_t *inst;
    bl_function_def_t *funct;

    inst = bl_find_instance_by_data_addr(rtdata->instance_data);
    funct = bl_find_function_def_in_instance_by_address(rtdata->funct, inst);
    printf("     %s.%s\n", inst->name, funct->name);
#endif
}

void bl_show_thread(struct bl_thread_meta_s const *thread)
{
#ifdef BL_SHOW_VERBOSE
    bl_thread_data_t *data;
    bl_function_rtdata_t *funct_data;

    data = TO_RT_ADDR(thread->data_index);
    funct_data = data->start;
    printf(" thread '%s' @[%d]=%p, no_fp = %d, period_ns = %d, RT data at [%d]=%p\n", thread->name, 
                                TO_RT_INDEX(thread), thread, thread->nofp, data->period_ns,
                                thread->data_index, data);
    while ( funct_data != NULL ) {
        bl_show_function_rtdata(funct_data);
        funct_data = funct_data->next;
    }
#else
    bl_thread_data_t *data;
    bl_function_rtdata_t *funct_data;
    char *fp_str;

    data = TO_RT_ADDR(thread->data_index);
    funct_data = data->start;
    if ( thread->nofp ) {
        fp_str = "no fp ";
    } else {
        fp_str = "has fp";
    }
    printf("  %-12s = %s : %10d nsec\n", thread->name, fp_str, data->period_ns);
    while ( funct_data != NULL ) {
        bl_show_function_rtdata(funct_data);
        funct_data = funct_data->next;
    }
#endif
}

static void thread_meta_print_node(void *node)
{
    bl_show_thread((bl_thread_meta_t *)node);
}

void bl_show_all_threads(void)
{
    int ll_result;

    printf("List of all threads:\n");
    ll_result = ll_traverse((void **)(&thread_root), thread_meta_print_node);
    printf("Total of %d threads\n", ll_result);
}


/* linked list callback functions */
static int instance_meta_compare_index_key(void *node, void *key)
{
    bl_instance_meta_t *np = node;
    uint32_t *kp = key;
    return (np->data_index - *kp);
}

static int sig_meta_compare_index_key(void *node, void *key)
{
    bl_signal_meta_t *np = node;
    uint32_t *kp = key;
    return np->data_index-*kp;
}

/* "find" functions */
static bl_instance_meta_t *bl_find_instance_by_data_addr(void *data_addr)
{
    uint32_t index;
    bl_instance_meta_t *retval;

    index = TO_RT_INDEX(data_addr);
    retval = ll_find((void **)(&(instance_root)), (void *)(&index), instance_meta_compare_index_key);
    if ( retval == NULL ) {
        #ifdef BL_PRINT_ERRORS
        print_string("data corruption\n");
        #endif
        halt();
    }
    return retval;
}

#if 0
static bl_instance_meta_t *bl_find_instance_from_thread_entry(bl_thread_entry_t const *entry)
{
    return bl_find_instance_by_data_addr(entry->instance_data);
}
#endif

static bl_signal_meta_t *bl_find_signal_by_index(uint32_t index)
{
    bl_signal_meta_t *retval;

    retval = ll_find((void **)(&(signal_root)), (void *)(&index), sig_meta_compare_index_key);
    if ( retval == NULL ) {
        #ifdef BL_PRINT_ERRORS
        print_string("data corruption\n");
        #endif
        halt();
    }
    return retval;
}

static bl_function_def_t *bl_find_function_def_in_instance_by_address(bl_rt_function_t *addr, bl_instance_meta_t const *inst)
{
    bl_comp_def_t const *comp;
    bl_function_def_t const *fdef;

    comp = inst->comp_def;
    for ( int n = 0 ; n < comp->function_count ; n++ ) {
        fdef = &(comp->function_defs[n]);
        if ( addr == fdef->fp ) {
            return (bl_function_def_t *)fdef;
        }
    }
    #ifdef BL_PRINT_ERRORS
    print_string("data corruption\n");
    #endif
    halt();
}

#if 0
static bl_function_def_t *bl_find_function_def_from_thread_entry(bl_thread_entry_t const *entry)
{
    bl_instance_meta_t *inst;

    inst = bl_find_instance_by_data_addr(entry->instance_data);
    return bl_find_function_def_in_instance_by_address(entry->funct, inst);
}
#endif

static int bl_find_pins_linked_to_signal(bl_signal_meta_t const *sig, void (*callback)(bl_instance_meta_t *inst, bl_pin_meta_t *pin))
{
    bl_instance_meta_t *inst;
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

#if 0
static int bl_find_functions_in_thread(bl_thread_meta_t const *thread, void (*callback)(bl_instance_meta_t *inst, bl_function_def_t *funct))
{
    bl_thread_data_t *data;
    bl_thread_entry_t *entry;
    bl_instance_meta_t *inst;
    bl_function_def_t *funct;
    int matches;

    data = TO_RT_ADDR(thread->data_index);
    entry = data->start;
    matches = 0;
    while ( entry != NULL ) {
        inst = bl_find_instance_by_data_addr(entry->instance_data);
        funct = bl_find_function_def_in_instance_by_address(entry->funct, inst);
        matches++;
        if ( callback != NULL ) {
            callback(inst, funct);
        }
    }
    return matches;
}
#endif

#pragma GCC reset_options
