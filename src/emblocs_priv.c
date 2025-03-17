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
bl_instance_meta_t *bl_find_instance_by_data_addr(void *data_addr)
{
    uint32_t index;
    bl_instance_meta_t *retval;

    index = TO_RT_INDEX(data_addr);
    retval = ll_find((void **)(&(instance_root)), (void *)(&index), instance_meta_compare_index_key);
    if ( retval == NULL ) {
        #ifdef BL_ERROR_VERBOSE
        print_string("data corruption\n");
        #endif
        halt();
    }
    return retval;
}

bl_instance_meta_t *bl_find_instance_from_thread_entry(bl_thread_entry_t const *entry)
{
    return bl_find_instance_by_data_addr(entry->instance_data);
}

bl_signal_meta_t *bl_find_signal_by_index(uint32_t index)
{
    bl_signal_meta_t *retval;

    retval = ll_find((void **)(&(signal_root)), (void *)(&index), sig_meta_compare_index_key);
    if ( retval == NULL ) {
        #ifdef BL_ERROR_VERBOSE
        print_string("data corruption\n");
        #endif
        halt();
    }
    return retval;
}

bl_function_def_t *bl_find_function_def_in_instance_by_address(bl_rt_function_t *addr, bl_instance_meta_t const *inst)
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
    #ifdef BL_ERROR_VERBOSE
    print_string("data corruption\n");
    #endif
    halt();
}

bl_function_def_t *bl_find_function_def_from_thread_entry(bl_thread_entry_t const *entry)
{
    bl_instance_meta_t *inst;

    inst = bl_find_instance_by_data_addr(entry->instance_data);
    return bl_find_function_def_in_instance_by_address(entry->funct, inst);
}

int bl_find_pins_linked_to_signal(bl_signal_meta_t const *sig, void (*callback)(bl_instance_meta_t *inst, bl_pin_meta_t *pin))
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

int bl_find_functions_in_thread(bl_thread_meta_t const *thread, void (*callback)(bl_instance_meta_t *inst, bl_function_def_t *funct))
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

