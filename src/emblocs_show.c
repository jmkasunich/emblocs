#include "emblocs_priv.h"
#include "linked_list.h"
#include "printing.h"

#define halt()  do {} while (1)


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

void bl_show_memory_status(void)
{
    printf("RT pool:   %d/%d, %d free\n", bl_rt_pool_size-bl_rt_pool_avail, bl_rt_pool_size, bl_rt_pool_avail);
    printf("Meta pool: %d/%d, %d free\n", bl_meta_pool_size-bl_meta_pool_avail, bl_meta_pool_size, bl_meta_pool_avail);
}

void bl_show_instance(bl_instance_meta_t const *inst)
{
#ifdef BL_SHOW_VERBOSE
    printf("INST: %20s <= %20s @ %p, %d RT bytes @ [%3d]=%p\n", inst->name, inst->comp_def->name,
                    inst, inst->data_size, inst->data_index, TO_RT_ADDR(inst->data_index) );
#else
    printf("instance '%s' of component '%s'\n", inst->name, inst->comp_def->name);
#endif
    bl_show_all_pins_of_instance(inst);
}

void bl_show_instance_by_name(char const *name)
{
    bl_instance_meta_t *inst;

    inst = bl_instance_find(name);
    if ( inst != NULL ) {
        bl_show_instance(inst);
    }
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

void bl_show_all_pins_of_instance(bl_instance_meta_t const *inst)
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

void bl_show_signal(bl_signal_meta_t const *sig)
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

void bl_show_signal_by_name(char const *name)
{
    bl_signal_meta_t *sig;

    sig = bl_signal_find(name);
    if ( sig != NULL ) {
        bl_show_signal(sig);
    }
}

void bl_show_signal_value(bl_signal_meta_t const *sig)
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

void bl_show_signal_linkage(bl_signal_meta_t const *sig)
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

void bl_show_thread_entry(bl_thread_entry_t const *entry)
{
#ifdef BL_SHOW_VERBOSE
    printf("  thread_entry @[%d]=%p, calls %p, inst data @%p\n", TO_RT_INDEX(entry), entry, entry->funct, entry->instance_data);
#else
    bl_instance_meta_t *inst;
    bl_function_def_t *funct;

    inst = bl_find_instance_by_data_addr(entry->instance_data);
    funct = bl_find_function_def_in_instance_by_address(entry->funct, inst);
    printf("     %s.%s\n", inst->name, funct->name);
#endif
}

void bl_show_thread(bl_thread_meta_t const *thread)
{
#ifdef BL_SHOW_VERBOSE
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

void bl_show_thread_by_name(char const *name)
{
    bl_thread_meta_t *thread;

    thread = bl_thread_find(name);
    if ( thread != NULL ) {
        bl_show_thread(thread);
    }
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
