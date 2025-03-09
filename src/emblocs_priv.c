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

static int pin_meta_compare_name_key(void *node, void *key)
{
    bl_pin_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
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

static int thread_meta_compare_name_key(void *node, void *key)
{
    bl_thread_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
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

