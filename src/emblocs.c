#include "emblocs.h"
#include <assert.h>
#include "printing.h"

extern bl_inst_def_t *instances;


static int name_comp(char const *name1, char const *name2)
{
    unsigned char const *s1 = (unsigned char const *) name1;
    unsigned char const *s2 = (unsigned char const *) name2;
    unsigned char c1, c2;
    if ( s1 == s2 ) {
        // if the pointers match then the strings are the same
        return 0;
    }
    do {
        c1 = (unsigned char) *s1++;
        c2 = (unsigned char) *s2++;
        if (c1 == '\0') {
	        return c1 - c2;
        }
    } while (c1 == c2);
    return c1 - c2;
}

bl_inst_def_t *find_instance_by_name(char const *name)
{
    bl_inst_def_t *root;

    root = instances;
    while ( root->inst_name != NULL ) {
        if ( name_comp(root->inst_name, name) == 0 ) {
            return root;
        }
        root++;
    }
    return NULL;
}


void bl_init_instance(bl_inst_def_t const *inst_def)
{
    bl_pin_def_t const *pin_def;
    bl_comp_def_t const *comp_def;
    bl_pin_t *pin;

    if ( inst_def->inst_data == NULL ) return;
    assert(inst_def->definition != NULL );
    assert(inst_def->inst_data != NULL );
    comp_def = inst_def->definition;
    // point each pin at a dummy signal and initialize the signal
    pin_def = comp_def->pin_defs;
    for ( int n = 0; n < comp_def->pin_count ; n++ ) {
        // use char pointer arithmetic to determine where the pin pointer is stored
        pin = (bl_pin_t *)((char *)(inst_def->inst_data) + pin_def[n].offset);
        // point it at the dummy signal and
        // store an appropriate initial value
        switch ( pin_def[n].type ) {
            case BL_PINTYPE_BIT:
            pin->b.pin = &(pin->b.dummy);
            pin->b.dummy = 0;
            break;
            case BL_PINTYPE_FLOAT:
            pin->f.pin = &(pin->f.dummy);
            pin->f.dummy = 0.0;
            break;
            case BL_PINTYPE_SINT:
            pin->s.pin = &(pin->s.dummy);
            pin->s.dummy = 0;
            break;
            case BL_PINTYPE_UINT:
            pin->u.pin = &(pin->u.dummy);
            pin->u.dummy = 0;
            break;
            default:
            // handle error here
            break;
        }
    }
}


bl_pin_def_t const *find_pindef_by_name(bl_comp_def_t *comp, char const *name)
{
    bl_pin_def_t const *retval;

    retval = comp->pin_defs;
    for ( int n = 0 ; n < comp->pin_count ; n++ ) {
        if ( name_comp(retval->name, name) == 0 ) {
            return retval;
        }
        retval++;
    }
    return NULL;
}


void list_all_instances(void)
{
    bl_inst_def_t *inst;

    inst = instances;
    while ( inst->inst_name != NULL ) {
        printf ( "Instance '%s' of type '%s' at %p\n", inst->inst_name, inst->definition->name, inst);
        list_all_pins_in_instance(inst);
        inst++;
    }
}

char const * const types[] = {
    "float",
    "bit  ",
    "s32  ",
    "u32  "
};

char const * const dirs[] = {
    "xxx",
    "in ",
    "out",
    "i/o"
};

void list_all_pins_in_instance(bl_inst_def_t *inst)
{
    bl_sigdata_t *pin_ptr, **pin_ptr_addr;
    bl_pin_def_t const *pindefs = inst->definition->pin_defs;
    int num_pins = inst->definition->pin_count;

    for ( int n = 0 ; n < num_pins ; n++ ) {
        printf ( " %10s: %s, %s, offset %3d, ", 
                pindefs[n].name, types[pindefs[n].type], dirs[pindefs[n].dir>>2], pindefs[n].offset);
        pin_ptr_addr = (bl_sigdata_t **)((char *)(inst) + pindefs[n].offset);
        pin_ptr = *pin_ptr_addr;
        printf(" addr: %p, points to %p, current value: ", pin_ptr_addr, pin_ptr);
        switch ( pindefs[n].type ) {
            case BL_PINTYPE_BIT:
            printf ( "%s\n", pin_ptr->b ? "TRUE" : "FALSE" );
            break;
            case BL_PINTYPE_FLOAT:
            printf ( "float represented by 0x%8x\n", (uint32_t)pin_ptr->f );
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


