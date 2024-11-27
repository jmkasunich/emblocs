#include "emblocs.h"


bl_sigdata_t *bl_free_signal_list = NULL;
bl_inst_header_t *bl_instance_list = NULL;

void add_to_signal_pool(bl_sigdata_t *pool, int entries)
{
    bl_sigdata_t *oldroot;

    while ( entries > 0 ) {
        oldroot = bl_free_signal_list;
        bl_free_signal_list = pool;
        pool->next_free = oldroot;
        pool++;
    }
}

bl_sigdata_t * get_sig_from_pool(void)
{
    bl_sigdata_t *retval;

    retval = bl_free_signal_list;
    if ( retval == NULL ) {
        // handle error here
    }
    bl_free_signal_list = retval->next_free;
    retval->next_free = NULL;
    return retval;
}

void return_sig_to_pool(bl_sigdata_t *sig)
{
    sig->next_free = bl_free_signal_list;
    bl_free_signal_list = sig;
}

void new_inst(bl_comp_def_t *comp_def, bl_inst_header_t *inst_data, char const *name)
{
    bl_pin_def_t const *pin_def;
    bl_sigdata_t *dummy_sig;
    bl_sigdata_t **pin_ptr_addr;

    // fill in instance data
    inst_data->definition = comp_def;
    inst_data->inst_name = name;
    // link new instance into main instance list
    inst_data->next = bl_instance_list;
    bl_instance_list = inst_data;

    // point each pin at a dummy signal and initialize the signal
    pin_def = comp_def->pin_defs;
    for ( int n = 0; n < comp_def->pin_count ; n++ ) {
        dummy_sig = get_sig_from_pool();
        // use char * arithmetic to determine where the pin pointer is stored
        pin_ptr_addr = (bl_sigdata_t **)((char *)(inst_data) + pin_def->offset);
        // point it at the dummy signal
        *pin_ptr_addr = dummy_sig;
        // store an appropriate initial value
        switch ( pin_def->type ) {
            case BL_PINTYPE_BIT:
            dummy_sig->b = 0;
            break;
            case BL_PINTYPE_FLOAT:
            dummy_sig->f = 0.0;
            break;
            case BL_PINTYPE_SINT:
            dummy_sig->s = 0;
            break;
            case BL_PINTYPE_UINT:
            dummy_sig->u = 0U;
            break;
            default:
            // handle error here
            break;
        }
    }
}


#include "printing.h"

void list_all_instances(void)
{
    bl_inst_header_t *inst;

    inst = bl_instance_list;
    while ( inst != NULL ) {
        printf ( "Instance '%s' of type '%s'\n", inst->inst_name, inst->definition->name);
    }
}


void list_all_pins_in_instance(bl_inst_header_t *inst)
{
    bl_sigdata_t *pin_ptr, **pin_ptr_addr;
    bl_pin_def_t const *pindefs = inst->definition->pin_defs;
    int num_pins = inst->definition->pin_count;

    for ( int n = 0 ; n < num_pins ; n++ ) {
        printf ( "  Pin '%s' is type %2d, dir %2d, at offset %3d. Current value is ", 
                pindefs[n].name, pindefs[n].type, pindefs[n].dir, pindefs[n].offset);
        pin_ptr_addr = (bl_sigdata_t **)((char *)(inst) + pindefs[n].offset);
        pin_ptr = *pin_ptr_addr;
        switch ( pindefs[n].type ) {
            case BL_PINTYPE_BIT:
            printf ( "%s\n", pin_ptr->b ? "TRUE" : "FALSE" );
            break;
            case BL_PINTYPE_FLOAT:
            printf ( "float represented by %8x\n", (uint32_t)pin_ptr->f );
            break;
            case BL_PINTYPE_SINT:
            printf ( "%+d\n", pin_ptr->s);
            break;
            case BL_PINTYPE_UINT:
            printf ( "%u\n", pin_ptr->u);
            break;
            default:
            // handle error here
            break;
        }
    }
}


