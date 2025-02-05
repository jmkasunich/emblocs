#include "emblocs.h"
#include "linked_list.h"
#include <assert.h>
#include <string.h>
#include "printing.h"

/***********************************************
 * memory pools
 */

static uint32_t bl_rt_pool[BL_RT_POOL_SIZE >> 2]  __attribute__ ((aligned(4)));
static uint32_t *rt_pool_next = bl_rt_pool;
static int32_t rt_pool_avail = sizeof(bl_rt_pool);

static uint32_t bl_meta_pool[BL_META_POOL_SIZE >> 2]  __attribute__ ((aligned(4)));
static uint32_t *meta_pool_next = bl_meta_pool;
static int32_t meta_pool_avail = sizeof(bl_meta_pool);

/* returns the index of 'addr' in the respective pool, masked so it can
 * go into a bitfield without a conversion warning */
#define TO_RT_INDEX(addr) ((uint32_t)((uint32_t *)(addr)-bl_rt_pool) & BL_RT_INDEX_MASK)
#define TO_META_INDEX(addr) ((uint32_t)((uint32_t *)(addr)-bl_meta_pool) & BL_META_INDEX_MASK)
/* returns an address in the respective pool */
#define TO_RT_ADDR(index) ((void *)(&bl_rt_pool[index]))
#define TO_META_ADDR(index) ((void *)(&bl_meta_pool[index]))
/* masks 'size' so it can go into a bit field without a conversion warning */
#define TO_INST_SIZE(size) ((size) & BL_INST_DATA_SIZE_MASK)



static void *alloc_from_rt_pool(int32_t size)
{
    void *retval;

    printf("alloc rt   (%d)", size);
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
    printf(" @ %p, %d left\n", retval, rt_pool_avail);
    return retval;
}

static void *alloc_from_meta_pool(int32_t size)
{
    void *retval;

    printf("alloc meta (%d)", size);
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
    printf(" %p, %d left\n", retval, meta_pool_avail);
    return retval;
}

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

bl_inst_meta_t *bl_default_setup(char const *name, bl_comp_def_t const *comp_def)
{
    bl_inst_meta_t *meta;

    meta = bl_inst_create(name, comp_def->data_size);
    for ( int i = 0 ; i < comp_def->pin_count ; i++ ) {
        bl_inst_add_pin(meta, &(comp_def->pin_defs[i]));
    }
    return meta;
}


/* linked list helpers for instance data */
static int inst_meta_cmp_node_key(void *node, void *key)
{
    bl_inst_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
}

static int inst_meta_cmp_nodes(void *node1, void *node2)
{
    bl_inst_meta_t  *np1 = node1;
    bl_inst_meta_t  *np2 = node2;
    return strcmp(np1->name, np2->name);
}

static void inst_meta_print_node(void *node)
{
    bl_inst_meta_t *np = node;

    printf("FIXME - bl_inst_meta_t\n",  np, np->next, np->name );
}

/* root of instance linked list */
static bl_inst_meta_t *instance_root;

bl_inst_meta_t *bl_inst_create(char const *name, uint32_t data_size)
{
    bl_inst_meta_t *meta;
    void *data;
    int ll_result;

    assert(data_size < BL_INST_DATA_MAX_SIZE);
    // allocate memory for metadata
    meta = alloc_from_meta_pool(sizeof(bl_inst_meta_t));
    // allocate memory for realtime data
    data = alloc_from_rt_pool(data_size);
    // initialise metadata fields
    meta->data_index = TO_RT_INDEX(data);
    meta->data_size = TO_INST_SIZE(data_size);
    meta->name = name;
    meta->pin_list = NULL;
    // add metadata to master instance list
    ll_result = ll_insert((void **)(&instance_root), (void *)meta, inst_meta_cmp_nodes);
    assert(ll_result == 0);
    return meta;
}


/* linked list helpers for pin data */
static int pin_meta_cmp_node_key(void *node, void *key)
{
    bl_pin_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
}

static int pin_meta_cmp_nodes(void *node1, void *node2)
{
    bl_pin_meta_t  *np1 = node1;
    bl_pin_meta_t  *np2 = node2;
    return strcmp(np1->name, np2->name);
}

static void pin_meta_print_node(void *node)
{
    bl_inst_meta_t *np = node;

    printf("FIXME - bl_pin_meta_t\n",  np, np->next, np->name );
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
    // initialize dummy signal to zero
    // FIXME - this is pedantic, I know that 0x00000000 is zero for all types
    // so I could do 'data->u = 0;' without the switch
    // but if I ever want non-zero default values I'll need the switch
    switch ( def->data_type ) {
        case BL_TYPE_BIT: {
            data->b = 0;
            break;
        }
        case BL_TYPE_FLOAT: {
            data->b = 0.0;
            break;
        }
        case BL_TYPE_S32: {
            data->s = 0;
            break;
        }
        case BL_TYPE_U32: {
            data->u = 0U;
            break;
        }
        default: {
            assert(0);
            break;
        }
    }
    // initialise metadata fields
    meta->ptr_index = TO_RT_INDEX(ptr_addr);
    meta->dummy_index = TO_RT_INDEX(data);
    meta->data_type = def->data_type;
    meta->pin_dir = def->pin_dir;
    meta->name = def->name;
    // add metadata to instances's pin list
    ll_result = ll_insert((void **)(&(inst->pin_list)), (void *)meta, pin_meta_cmp_nodes);
    assert(ll_result == 0);
    return meta;
}


#if 0

/***********************************************
 * list management
 */

static int name_cmp(char const *name1, char const *name2)
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
        if ( name_cmp(p->name, name) == 0 ) {
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
        cmp = name_cmp((*pp)->name, name);
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

static int sig_meta_cmp_node_key(void *node, void *key)
{
    bl_sig_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
}

static int sig_meta_cmp_nodes(void *node1, void *node2)
{
    bl_sig_meta_t  *np1 = node1;
    bl_sig_meta_t  *np2 = node2;
    return strcmp(np1->name, np2->name);
}

static void sig_meta_print_node(void *node)
{
    bl_sig_meta_t *np = node;
    printf("sig_meta_t node at %p; next at %p, type: %s, data at %p, name: '%s'\n",
        np, np->next, types[GET_TYPE(np->dpwt)], GET_DPTR(np->dpwt), np->name );
}

static int sig_meta_insert(bl_sig_meta_t **root, bl_sig_meta_t *node)
{
    return ll_insert((void **)root, (void *)node, sig_meta_cmp_nodes);
}

static int sig_meta_print_list(bl_sig_meta_t **root)
{
    return ll_traverse((void **)root, sig_meta_print_node);
}

static bl_sig_meta_t *sig_meta_find(bl_sig_meta_t **root, char *key)
{
    return ll_find((void **)root, (void *)key, sig_meta_cmp_node_key);
}

static bl_sig_meta_t *sig_meta_delete(bl_sig_meta_t **root, char *key)
{
    return ll_delete((void **)root, (void *)key, sig_meta_cmp_node_key);
}

bl_sig_meta_t *bl_newsig(bl_type_t type, char const * sig_name)
{
    bl_sig_meta_t *sig_meta;
    bl_sig_data_t *sig_data;
    int insert_result;

    // allocate memory for metadata
    sig_meta = alloc_from_meta_pool(sizeof(bl_sig_meta_t));
    // allocate memory for realtime data
    sig_data = alloc_from_rt_pool(sizeof(bl_sig_data_t));
    // make metadata point at the realtime data
    sig_meta->dpwt = MAKE_DPWT(sig_data, type);
    sig_meta->name = sig_name;
    // insert metadata into list
    insert_result = sig_meta_insert(&sig_list, sig_meta);
    assert( (insert_result==0) );
    return sig_meta;
}

static bl_pin_def_t const *find_pin_def_by_name(char const *pin_name, bl_comp_def_t *comp)
{
    for ( int n = 0 ; n < comp->pin_count ; n++ ) {
        if ( name_cmp(pin_name, comp->pin_defs[n].name) == 0 ) {
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


void emblocs_init(void)
{
    bl_inst_def_t *idp;  // instance definition pointer
    char **snp;  // signal name pointer
    bl_link_def_t *ldp;  // link defintion pointer

    idp = bl_instances;
    while ( idp->name != NULL ) {
        bl_newinst(idp->comp_def, idp->name);
        idp++;
    }
    snp = bl_signals_float;
    while ( *snp != NULL ) {
        bl_newsig(BL_TYPE_FLOAT, *snp);
        snp++;
    }
    snp = bl_signals_bit;
    while ( *snp != NULL ) {
        bl_newsig(BL_TYPE_BIT, *snp);
        snp++;
    }
    snp = bl_signals_s32;
    while ( *snp != NULL ) {
        bl_newsig(BL_TYPE_S32, *snp);
        snp++;
    }
    snp = bl_signals_u32;
    while ( *snp != NULL ) {
        bl_newsig(BL_TYPE_U32, *snp);
        snp++;
    }
printf("signal_init_done\n");
list_all_signals();
    ldp = bl_links;
    while ( ldp->sig_name != NULL ) {
        bl_linksp(ldp->sig_name, ldp->inst_name, ldp->pin_name);
        ldp++;
    }
}

void list_all_signals(void)
{
    bl_sig_meta_t *sig;

    printf("named signal linked list:\n");
    sig_meta_print_list(&sig_list);
    printf("old listing function:\n");
    sig = sig_list;
    while ( sig != NULL ) {
        printf ( "Sig %10s: %s, meta at %p, rt at %p, value = ", 
            sig->name, types[GET_TYPE(sig->dpwt)], sig, GET_DPTR(sig->dpwt));
        switch ( GET_TYPE(sig->dpwt)) {
            case BL_TYPE_BIT: {
                bl_bit_t *p = GET_DPTR(sig->dpwt);
                printf ( "%s ", *p ? "TRUE" : "FALSE" );
                break;
            }
            case BL_TYPE_FLOAT: {
                bl_float_t *p = GET_DPTR(sig->dpwt);
                printf ( "%f", *p );
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
        sig = (bl_sig_meta_t *)sig->next;
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
printf("list_all_instances\n");
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
printf("list_all_pins_in_instance\n");
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
                printf ( "%f", *p->pin );
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
printf("list_pin_signal\n");

    // need to scan the signal list to find the match
    sig = sig_list;
    while ( sig != NULL ) {
        if ( sig_addr == GET_DPTR(sig->dpwt) ) {
            printf("%s", sig->name);
            return;
        }
        sig = (bl_sig_meta_t *)sig->next;
    }
}

#endif // 0
