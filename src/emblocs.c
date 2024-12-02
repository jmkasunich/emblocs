#include "emblocs.h"
#include <assert.h>
#include "printing.h"

/***********************************************
 * memory pools
 */

#define BLOCS_RT_POOL_SIZE 1024
#define BLOCS_META_POOL_SIZE 512

uint8_t blocs_rt_pool[BLOCS_RT_POOL_SIZE & ~3]  __attribute__ ((aligned(4)));
static uint8_t *rt_pool_next = blocs_rt_pool;
static uint32_t rt_pool_avail = sizeof(blocs_rt_pool);

uint8_t blocs_meta_pool[BLOCS_META_POOL_SIZE & ~3]  __attribute__ ((aligned(4)));
static uint8_t *meta_pool_next = blocs_meta_pool;
static uint32_t meta_pool_avail = sizeof(blocs_meta_pool);

static void *alloc_from_rt_pool(uint32_t size)
{
    void *retval;

    printf("alloc rt   (%d)", size);
    // round size up to multiple of 4
    if ( size & 3 ) {
        size += 4;
        size &= ~3;
    }
    assert( rt_pool_avail >= size);
    retval = rt_pool_next;
    rt_pool_next += size;
    rt_pool_avail -= size;
    printf(" %p, %d left\n", retval, rt_pool_avail);
    return retval;
}

static void *alloc_from_meta_pool(uint32_t size)
{
    void *retval;

    printf("alloc meta (%d)", size);
    // round size up to multiple of 4
    if ( size & 3 ) {
        size += 4;
        size &= ~3;
    }
    assert( meta_pool_avail >= size);
    retval = meta_pool_next;
    meta_pool_next += size;
    meta_pool_avail -= size;
    printf(" %p, %d left\n", retval, meta_pool_avail);
    return retval;
}

/***********************************************
 * list management
 */

static int name_comp(char const *name1, char const *name2)
{
    unsigned char const *s1 = (unsigned char const *) name1;
    unsigned char const *s2 = (unsigned char const *) name2;
    unsigned char c1, c2;

    assert(s1 != NULL);
    assert(s2 != NULL);
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

bl_list_entry_t *find_name_in_list(char const *name, bl_list_entry_t *list)
{
    bl_list_entry_t *p;

    p = list;
    while ( p != NULL ) {
        if ( name_comp(p->name, name) == 0 ) {
            return p;
        }
        p = p->next;
    }
    return NULL;
}

bl_list_entry_t **find_insertion_point(char const *name, bl_list_entry_t **list)
{
    bl_list_entry_t **pp;
    int cmp;

    pp = list;
    while (1) {
        if ( *pp == NULL ) {
            // reached end of list, insert here
            return pp;
        }
        cmp = name_comp((*pp)->name, name);
        if ( cmp == 0 ) {
            // name is already present, can't insert
            return NULL;
        }
        if ( cmp > 0 ) {
            // insert here
            return pp;
        }
        // check next
        pp = &((*pp)->next);
    }
}

/***********************************************
 * strings for printing type and direction
 */

static char const * const types[] = {
    "float",
    "bit  ",
    "s32  ",
    "u32  "
};

static char const * const dirs[] = {
    "xxx",
    "in ",
    "out",
    "i/o"
};

/***********************************************
 * named signal list
 */

bl_sig_meta_t *sig_list = NULL;

/***********************************************
 * component instance list
 */

bl_inst_meta_t *inst_list = NULL;

/***********************************************
 * named signal list functions
 */

bl_sig_meta_t *bl_newsig(bl_type_t type, char const * sig_name)
{
    bl_list_entry_t **pp, *new;
    bl_sig_meta_t *sig_meta;
    bl_sig_data_t *sig_data;

    // find insertion point in list
    pp = find_insertion_point(sig_name, (bl_list_entry_t **)&sig_list);
    assert(pp != NULL);
    // allocate memory for metadata
    sig_meta = alloc_from_meta_pool(sizeof(bl_sig_meta_t));
    // allocate memory for realtime data
    sig_data = alloc_from_rt_pool(sizeof(bl_sig_data_t));
    // insert metadata into list
    new = (bl_list_entry_t *)sig_meta;
    new->name = sig_name;
    new->next = *pp;
    *pp = new;
    // make metadata point at the realtime data
    sig_meta->dpwt = MAKE_DPWT(sig_data, type);
    return sig_meta;
}

static bl_pin_def_t const *find_pin_def_by_name(char const *pin_name, bl_comp_def_t *comp)
{
    for ( int n = 0 ; n < comp->pin_count ; n++ ) {
        if ( name_comp(pin_name, comp->pin_defs[n].name) == 0 ) {
            return &(comp->pin_defs[n]);
        }
    }
    return NULL;
}

void bl_linksp(char const *sig_name, char const *inst_name, char const *pin_name)
{
    bl_sig_meta_t *sig;
    bl_inst_meta_t *inst;
    bl_comp_def_t *comp;
    bl_pin_def_t const *pindef;
    void *pin_addr;

    sig = (bl_sig_meta_t *)find_name_in_list(sig_name, (bl_list_entry_t *)sig_list);
    assert(sig != NULL);
    inst = (bl_inst_meta_t *)find_name_in_list(inst_name, (bl_list_entry_t *)inst_list);
    assert(inst != NULL);
    comp = inst->comp_def;
    pindef = find_pin_def_by_name(pin_name, comp);
    assert(pindef != NULL);
    assert(GET_TYPE(sig->dpwt) == pindef->type);
    // use char pointer arithmetic to determine where the pin is stored
    pin_addr = (void *)((char *)(inst->inst_data) + pindef->offset);
    // connect the pin to the signal
    switch(pindef->type) {
        case BL_TYPE_BIT: {
            bl_pin_bit_t *p = (bl_pin_bit_t *)pin_addr;
            p->pin = GET_DPTR(sig->dpwt);
            break;
        }
        case BL_TYPE_FLOAT: {
            bl_pin_float_t *p = (bl_pin_float_t *)pin_addr;
            p->pin = GET_DPTR(sig->dpwt);
            break;
        }
        case BL_TYPE_S32: {
            bl_pin_s32_t *p = (bl_pin_s32_t *)pin_addr;
            p->pin = GET_DPTR(sig->dpwt);
            break;
        }
        case BL_TYPE_U32: {
            bl_pin_u32_t *p = (bl_pin_u32_t *)pin_addr;
            p->pin = GET_DPTR(sig->dpwt);
            break;
        }
        default: {
            assert(0);
            break;
        }
    }
}


void list_all_signals(void)
{
    bl_sig_meta_t *sig;

    sig = sig_list;
    while ( sig != NULL ) {
        printf ( "Sig %10s: %s, meta at %p, rt at %p, value = ", 
            sig->header.name, types[GET_TYPE(sig->dpwt)], sig, GET_DPTR(sig->dpwt));
        switch ( GET_TYPE(sig->dpwt)) {
            case BL_TYPE_BIT: {
                bl_bit_t *p = GET_DPTR(sig->dpwt);
                printf ( "%s ", *p ? "TRUE" : "FALSE" );
                break;
            }
            case BL_TYPE_FLOAT: {
                bl_float_t *p = GET_DPTR(sig->dpwt);
                printf ( "float represented by 0x%8x", (uint32_t)*p );
                break;
            }
            case BL_TYPE_S32: {
                bl_s32_t *p = GET_DPTR(sig->dpwt);
                printf ( "%+d", *p);
                break;
            }
            case BL_TYPE_U32: {
                bl_u32_t *p = GET_DPTR(sig->dpwt);
                printf ( "%u", *p);
                break;
            }
            default: {
                assert(0);
                break;
            }
        }
        printf("\n");
        list_signal_pins(sig);
        sig = (bl_sig_meta_t *)sig->header.next;
    }
}

void list_signal_pins(bl_sig_meta_t *sig)
{
    bl_inst_meta_t *inst;
    bl_pin_def_t const *pindefs;
    int num_pins;
    void *inst_data, *pin_addr, *sig_addr;

    sig_addr = GET_DPTR(sig->dpwt);
    // to list pins connected to a signal we need to check all pins
    inst = inst_list;
    // loop through instances
    while ( inst != NULL ) {
        pindefs = inst->comp_def->pin_defs;
        num_pins = inst->comp_def->pin_count;
        inst_data = inst->inst_data;
        // loop through each instance's pins
        for ( int n = 0 ; n < num_pins ; n++ ) {
            pin_addr = *((void **)((char *)(inst_data) + pindefs[n].offset));
            if ( pin_addr == sig_addr ) {
                if ( pindefs[n].dir == BL_DIR_IN ) {
                    printf("  -->");
                } else if ( pindefs[n].dir == BL_DIR_OUT ) {
                    printf("  <--");
                } else if ( pindefs[n].dir == BL_DIR_IO ) {
                    printf("  <->");
                }
                printf("  %s.%s\n", inst->header.name, pindefs[n].name);
            }
        }
        inst = (bl_inst_meta_t *)inst->header.next;
    }
}





/***********************************************
 * component instance list functions
 */


bl_inst_meta_t *bl_newinst(bl_comp_def_t *comp_def, char const *inst_name)
{
    bl_list_entry_t **pp, *new;
    bl_inst_meta_t *inst_meta;
    void *inst_data;
    bl_pin_def_t const *pin_def;
    void *pin_addr;

    // find insertion point in list
    pp = find_insertion_point(inst_name, (bl_list_entry_t **)&inst_list);
    assert(pp != NULL);
    // allocate memory for metadata
    inst_meta = alloc_from_meta_pool(sizeof(bl_inst_meta_t));
    // allocate memory for realtime data
    inst_data = alloc_from_rt_pool(comp_def->inst_data_size);
    // insert metadata into list
    new = (bl_list_entry_t *)inst_meta;
    new->name = inst_name;
    new->next = *pp;
    *pp = new;
    // make metadata point at the component definition
    inst_meta->comp_def = comp_def;
    // and the realtime data
    inst_meta->inst_data = inst_data;
     // point each pin at its dummy signal and initialize the signal
    pin_def = comp_def->pin_defs;
    for ( int n = 0; n < comp_def->pin_count ; n++ ) {
        // use char pointer arithmetic to determine where the pin is stored
        pin_addr = (void *)((char *)(inst_data) + pin_def[n].offset);
        // set up pin data; type specific, but the steps are:
        //    make pointer to the pin struct
        //    point the pin at its dummy
        //    store an initial value in the dummy
        switch ( pin_def[n].type ) {
            case BL_TYPE_BIT: {
                bl_pin_bit_t *p = (bl_pin_bit_t *)pin_addr;
                p->pin = &p->dummy;
                p->dummy = 0;
                break;
            }
            case BL_TYPE_FLOAT: {
                bl_pin_float_t *p = (bl_pin_float_t *)pin_addr;
                p->pin = &p->dummy;
                p->dummy = 0.0;
                break;
            }
            case BL_TYPE_S32: {
                bl_pin_s32_t *p = (bl_pin_s32_t *)pin_addr;
                p->pin = &p->dummy;
                p->dummy = 0;
                break;
            }
            case BL_TYPE_U32: {
                bl_pin_u32_t *p = (bl_pin_u32_t *)pin_addr;
                p->pin = &p->dummy;
                p->dummy = 0U;
                break;
            }
            default: {
                assert(0);
                break;
            }
        }
    }
    return inst_meta;
}

void list_all_instances(void)
{
    bl_inst_meta_t *inst;

    inst = inst_list;
    while ( inst != NULL ) {
        printf ( "Inst %10s: type %10s, meta at %p, rt at %p\n", inst->header.name, inst->comp_def->name, inst, inst->inst_data);
        list_all_pins_in_instance(inst);
        inst = (bl_inst_meta_t *)inst->header.next;
    }
}

void list_all_pins_in_instance(bl_inst_meta_t *inst)
{
    bl_pin_def_t const *pindefs;
    int num_pins;
    void *inst_data, *pin_addr, *sig_addr;

    pindefs = inst->comp_def->pin_defs;
    num_pins = inst->comp_def->pin_count;
    inst_data = inst->inst_data;
    for ( int n = 0 ; n < num_pins ; n++ ) {
        printf ( "  pin %10s: %s, %s, offset %3d, ", 
                pindefs[n].name, types[pindefs[n].type], dirs[pindefs[n].dir>>2], pindefs[n].offset);
        pin_addr = (bl_sig_data_t **)((char *)(inst_data) + pindefs[n].offset);
        printf("addr: %p = ", pin_addr);
        sig_addr = NULL;
        switch ( pindefs[n].type ) {
            case BL_TYPE_BIT: {
                bl_pin_bit_t *p = (bl_pin_bit_t *)pin_addr;
                printf ( "%s ", *p->pin ? "TRUE" : "FALSE" );
                if ( p->pin != &p->dummy ) {
                    sig_addr = p->pin;
                }
                break;
            }
            case BL_TYPE_FLOAT: {
                bl_pin_float_t *p = (bl_pin_float_t *)pin_addr;
                printf ( "float represented by 0x%8x", (uint32_t)*p->pin );
                if ( p->pin != &p->dummy ) {
                    sig_addr = p->pin;
                }
                break;
            }
            case BL_TYPE_S32: {
                bl_pin_s32_t *p = (bl_pin_s32_t *)pin_addr;
                printf ( "%+d", *p->pin);
                if ( p->pin != &p->dummy ) {
                    sig_addr = p->pin;
                }
                break;
            }
            case BL_TYPE_U32: {
                bl_pin_u32_t *p = (bl_pin_u32_t *)pin_addr;
                printf ( "%u", *p->pin);
                if ( p->pin != &p->dummy ) {
                    sig_addr = p->pin;
                }
                break;
            }
            default: {
                assert(0);
                break;
            }
        }
        if ( pindefs[n].dir == BL_DIR_IN ) {
            printf(" <-- ");
        } else if ( pindefs[n].dir == BL_DIR_OUT ) {
            printf(" --> ");
        } else if ( pindefs[n].dir == BL_DIR_IO ) {
            printf(" <-> ");
        }
        if ( sig_addr != NULL ) {
            list_pin_signal(sig_addr);
        } else {
            printf("(dummy)");
        }
        printf("\n");
    }
}

void list_pin_signal(void *sig_addr)
{
    bl_sig_meta_t *sig;

    // need to scan the signal list to find the match
    sig = sig_list;
    while ( sig != NULL ) {
        if ( sig_addr == GET_DPTR(sig->dpwt) ) {
            printf("%s", sig->header.name);
            return;
        }
        sig = (bl_sig_meta_t *)sig->header.next;
    }
}

