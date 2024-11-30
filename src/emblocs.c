#include "emblocs.h"
#include <assert.h>
#include "printing.h"


#define BLOCS_POOL_SIZE 1024

uint32_t blocs_pool[BLOCS_POOL_SIZE/4];
uint32_t *pool_next = blocs_pool;
uint32_t pool_avail = BLOCS_POOL_SIZE;


bl_sigdata_t *bl_free_signal_list = NULL;
bl_inst_header_t *bl_instance_list = NULL;

static void *alloc_from_pool(uint32_t size)
{
    void *retval;

printf("alloc_from_pool(%d)\n", size);
    // round size up to multiple of 4
    if ( size & 3 ) {
        size += 4;
        size &= ~3;
    }
    assert( pool_avail >= size);
    retval = pool_next;
    pool_next += size/4;
    pool_avail -= size;
    return retval;
}


static bl_sigdata_t *alloc_sigdata(void)
{
    bl_sigdata_t *retval;

    if ( bl_free_signal_list != NULL ) {
        // allocate from the free signal list
        retval = bl_free_signal_list;
        bl_free_signal_list = retval->next_free;
    } else {
        // allocate from the pool
        retval = alloc_from_pool(sizeof(bl_sigdata_t));
    }
    return retval;
}

static void free_sigdata(bl_sigdata_t *old)
{
    old->next_free = bl_free_signal_list;
    bl_free_signal_list = old;
}


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

bl_inst_header_t *find_instance_by_name(char const *name)
{
    bl_inst_header_t *root;

    root = bl_instance_list;
    while ( root != NULL ) {
        if ( name_comp(root->inst_name, name) == 0 ) {
            return root;
        }
        root = root->next_inst;
    }
    return NULL;
}

bl_inst_header_t **find_instance_insertion_point(char const *name)
{
    bl_inst_header_t **root;
    int cmp;

    root = &bl_instance_list;
    while (1) {
        if ( *root == NULL ) {
            // reached end of list, insert here
            return root;
        }
        cmp = name_comp((*root)->inst_name, name);
        if ( cmp == 0 ) {
            // name is already present, can't insert
            return NULL;
        }
        if ( cmp > 0 ) {
            // insert here
            return root;
        }
        // check next
        root = &((*root)->next_inst);
    }
}


bl_inst_header_t *bl_newinst(bl_comp_def_t *comp_def, char const *inst_name)
{
    bl_inst_header_t **insertion_pt;
    bl_inst_header_t *newinst;
    bl_pin_def_t const *pin_def;
    bl_sigdata_t *dummy_sig;
    bl_sigdata_t **pin_ptr_addr;

    // find insertion point
    insertion_pt = find_instance_insertion_point(inst_name);
    assert ( insertion_pt != NULL );
    // allocate instance data from pool
    newinst = (bl_inst_header_t *) alloc_from_pool(comp_def->inst_data_size);
    // link into instance list
    newinst->next_inst = *insertion_pt;
    *insertion_pt = newinst;
    // fill in instance data
    newinst->inst_name = inst_name;
    newinst->definition = comp_def;
    // point each pin at a dummy signal and initialize the signal
    pin_def = comp_def->pin_defs;
    for ( int n = 0; n < comp_def->pin_count ; n++ ) {
        dummy_sig = alloc_sigdata();
        // use char pointer arithmetic to determine where the pin pointer is stored
        pin_ptr_addr = (bl_sigdata_t **)((char *)(newinst) + pin_def[n].offset);
        // point it at the dummy signal
        *pin_ptr_addr = dummy_sig;
        // store an appropriate initial value
        switch ( pin_def[n].type ) {
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
    return newinst;
}



void list_all_instances(void)
{
    bl_inst_header_t *inst;

    inst = bl_instance_list;
    while ( inst != NULL ) {
        printf ( "Instance '%s' of type '%s' at %p\n", inst->inst_name, inst->definition->name, inst);
        list_all_pins_in_instance(inst);
        inst = inst->next_inst;
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

void list_all_pins_in_instance(bl_inst_header_t *inst)
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


