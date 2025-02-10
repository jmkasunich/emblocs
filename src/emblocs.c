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
    printf("%s: instance of %s, compdef @ %p, personality @ %p\n", name, comp_def->name, comp_def, personality);
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

    meta = bl_inst_create(name, comp_def, 0);
    for ( int i = 0 ; i < comp_def->pin_count ; i++ ) {
        bl_inst_add_pin(meta, &(comp_def->pin_defs[i]));
    }
    return meta;
}


/* linked list callback functions */
static int inst_meta_cmp_name_key(void *node, void *key)
{
    bl_inst_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
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
    return strcmp(np->sig_name, kp);
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
    return strcmp(np1->sig_name, np2->sig_name);
}

static void sig_meta_print_node(void *node)
{
    bl_show_signal((bl_sig_meta_t *)node);
}


/* root of instance linked list */
static bl_inst_meta_t *instance_root;

/* root of signal linked list */
static bl_sig_meta_t *signal_root;


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
    meta->sig_name = name;
    // add metadata to master signal list
    ll_result = ll_insert((void **)(&(signal_root)), (void *)meta, sig_meta_cmp_names);
    assert(ll_result == 0);
    return meta;
}


bl_retval_t bl_link_pin_to_signal_by_names(char const *inst_name, char const *pin_name, char const *sig_name )
{
    bl_inst_meta_t *inst;
    bl_pin_meta_t *pin;
    bl_sig_meta_t *sig;

    inst = bl_find_instance_by_name(inst_name);
    if ( inst == NULL ) {
        return BL_INST_NOT_FOUND;
    }
    pin = bl_find_pin_in_instance_by_name(pin_name, inst);
    if ( pin == NULL ) {
        return BL_PIN_NOT_FOUND;
    }
    sig = bl_find_signal_by_name(sig_name);
    if ( sig == NULL ) {
        return BL_SIG_NOT_FOUND;
    }
    bl_link_pin_to_signal(pin, sig );
    return BL_SUCCESS;
}


bl_retval_t bl_link_pin_to_signal(bl_pin_meta_t *pin, bl_sig_meta_t *sig )
{
    bl_sig_data_t *sig_data_addr, **pin_ptr_addr;

    // check types
    if ( pin->data_type != sig->data_type ) {
        return BL_TYPE_MISMATCH;
    }
    // convert indexes to addresses
    pin_ptr_addr = TO_RT_ADDR(pin->ptr_index);
    sig_data_addr = TO_RT_ADDR(sig->data_index);
    // make the link
    *pin_ptr_addr = sig_data_addr;
    return BL_SUCCESS;
}


bl_retval_t bl_unlink_pin_by_name(char const *inst_name, char const *pin_name)
{
    bl_inst_meta_t *inst;
    bl_pin_meta_t *pin;

    inst = bl_find_instance_by_name(inst_name);
    if ( inst == NULL ) {
        return BL_INST_NOT_FOUND;
    }
    pin = bl_find_pin_in_instance_by_name(pin_name, inst);
    if ( pin == NULL ) {
        return BL_PIN_NOT_FOUND;
    }
    bl_unlink_pin(pin);
    return BL_SUCCESS;
}


void bl_unlink_pin(bl_pin_meta_t *pin)
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
}


bl_inst_meta_t *bl_find_instance_by_name(char const *name)
{
    return ll_find((void **)(&(instance_root)), (void *)(name), inst_meta_cmp_name_key);
}

bl_pin_meta_t *bl_find_pin_in_instance_by_name(char const *name, bl_inst_meta_t *inst)
{
    return ll_find((void **)(&(inst->pin_list)), (void *)(name), pin_meta_cmp_name_key);
}

bl_sig_meta_t *bl_find_signal_by_name(char const *name)
{
    return ll_find((void **)(&(signal_root)), (void *)(name), sig_meta_cmp_name_key);
}

bl_sig_meta_t *bl_find_signal_by_index(uint32_t index)
{
    return ll_find((void **)(&(signal_root)), (void *)(&index), sig_meta_cmp_index_key);
}

void bl_find_pins_linked_to_signal(bl_sig_meta_t *sig, void (*callback)(bl_inst_meta_t *inst, bl_pin_meta_t *pin))
{
    bl_inst_meta_t *inst;
    bl_pin_meta_t *pin;
    bl_sig_data_t *sp, **pp;

    sp = TO_RT_ADDR(sig->data_index);
    inst = instance_root;
    while ( inst != NULL ) {
        pin = inst->pin_list;
        while ( pin != NULL ) {
            pp = TO_RT_ADDR(pin->ptr_index);
            if ( *pp == sp ) {
                callback(inst, pin);
            }
            pin = pin->next;
        }
        inst = inst->next;
    }

}




void bl_show_memory_status(void)
{
    printf("RT pool:   %d/%d, %d free\n", sizeof(bl_rt_pool)-rt_pool_avail, sizeof(bl_rt_pool), rt_pool_avail);
    printf("Meta pool: %d/%d, %d free\n", sizeof(bl_meta_pool)-meta_pool_avail, sizeof(bl_meta_pool), meta_pool_avail);
}


void bl_show_instance(bl_inst_meta_t *inst)
{
    printf("INST: %20s <= %20s @ %p, %d RT bytes @ [%3d]=%p\n", inst->name, inst->comp_def->name,
                    inst, inst->data_size, inst->data_index, TO_RT_ADDR(inst->data_index) );
    bl_show_all_pins_of_instance(inst);

}

void bl_show_all_instances(void)
{
    int ll_result;

    printf("List of all instances:\n");
    ll_result = ll_traverse((void **)(&instance_root), inst_meta_print_node);
    printf("Total of %d instances\n", ll_result);
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

static char const * const dirs_ps[] = {
    "xxx",
    "<==",
    "==>",
    "<=>"
};

static char const * const dirs_sp[] = {
    "xxx",
    "==>",
    "<==",
    "<=>"
};

void bl_show_pin(bl_pin_meta_t *pin)
{
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
}

void bl_show_all_pins_of_instance(bl_inst_meta_t *inst)
{
    int ll_result;

    ll_result = ll_traverse((void **)(&inst->pin_list), pin_meta_print_node);
    printf("Total of %d pins\n", ll_result);
}

void bl_show_pin_value(bl_pin_meta_t *pin)
{
    bl_sig_data_t **pin_ptr_addr, *data;

    pin_ptr_addr = (bl_sig_data_t **)TO_RT_ADDR(pin->ptr_index);
    data = *pin_ptr_addr;
    bl_show_sig_data_t_value(data, pin->data_type);
}


void bl_show_pin_linkage(bl_pin_meta_t *pin)
{
    bl_sig_data_t *dummy_addr, **ptr_addr, *ptr_val;
    char const *dir;
    bl_sig_meta_t *sig;

    dummy_addr = (bl_sig_data_t *)TO_RT_ADDR(pin->dummy_index);
    ptr_addr = (bl_sig_data_t **)TO_RT_ADDR(pin->ptr_index);
    ptr_val = *ptr_addr;
    dir = dirs_ps[pin->pin_dir];
    if ( ptr_val == dummy_addr ) {
        printf("%s (dummy)", dir);
    } else {
        // find the matching signal
        sig = bl_find_signal_by_index(TO_RT_INDEX(ptr_val));
        assert(sig != NULL);
        printf("%s %s", dir, sig->sig_name);
    }
}


void bl_show_signal(bl_sig_meta_t *sig)
{
    bl_sig_data_t *data_addr;

    data_addr = TO_RT_ADDR(sig->data_index);
    printf("SIG: %20s  %s @ %p, data @ [%3d]=%p = ",
                            sig->sig_name, types[sig->data_type], sig, sig->data_index, data_addr);
    bl_show_signal_value(sig);
    printf("\n");
    bl_show_signal_linkage(sig);
}


void bl_show_signal_value(bl_sig_meta_t *sig)
{
    bl_sig_data_t *data;

    data = (bl_sig_data_t *)TO_RT_ADDR(sig->data_index);
    bl_show_sig_data_t_value(data, sig->data_type);
}


static void signal_linkage_callback(bl_inst_meta_t *inst, bl_pin_meta_t *pin)
{
    char const *dir;

    dir = dirs_sp[pin->pin_dir];
    printf("    %s %s.%s\n", dir, inst->name, pin->name);
}


void bl_show_signal_linkage(bl_sig_meta_t *sig)
{
    bl_find_pins_linked_to_signal(sig, signal_linkage_callback);
}


void bl_show_sig_data_t_value(bl_sig_data_t *data, bl_type_t type)
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
#endif

#ifdef INIT_BY_NET
static int is_type_str(char const *str, bl_type_t *result)
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
#endif


void emblocs_init(void)
{
    bl_inst_def_t const *idp;  // instance definition pointer
#ifndef INIT_BY_NET
    char const * const *snp;  // signal name pointer
    bl_link_def_t const *ldp;  // link defintion pointer
#endif
    bl_retval_t retval;
#ifdef INIT_BY_NET
    char const * const *netp;
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

#endif

    idp = bl_instances;
    while ( idp->name != NULL ) {
        bl_instance_new(idp->name, idp->comp_def, idp->personality);
        idp++;
    }
#ifndef INIT_BY_NET
    snp = bl_signals_float;
    while ( *snp != NULL ) {
        bl_signal_new(*snp, BL_TYPE_FLOAT);
        snp++;
    }
    snp = bl_signals_bit;
    while ( *snp != NULL ) {
        bl_signal_new(*snp, BL_TYPE_BIT);
        snp++;
    }
    snp = bl_signals_s32;
    while ( *snp != NULL ) {
        bl_signal_new(*snp, BL_TYPE_S32);
        snp++;
    }
    snp = bl_signals_u32;
    while ( *snp != NULL ) {
        bl_signal_new(*snp, BL_TYPE_U32);
        snp++;
    }
    ldp = bl_links;
    while ( ldp->sig_name != NULL ) {
        retval = bl_link_pin_to_signal_by_names(ldp->inst_name, ldp->pin_name, ldp->sig_name);
        assert(retval == BL_SUCCESS);
        ldp++;
    }
#endif
#ifdef INIT_BY_NET
    netp = bl_nets;
    state = START;
    while ( *netp != NULL ) {
        switch (state) {
        case START:
            if ( is_type_str(*netp, &net_type) ) {
                state = GET_SIG;
            } else {
                assert(0);
            }
            break;
        case GET_SIG:
            sig = bl_signal_new(*netp, net_type);
            assert(sig != NULL);
            state = GOT_SIG;
            break;
        case GOT_SIG:
            if ( is_type_str(*netp, &net_type) ) {
                // done with previous net, start a new one
                state = GET_SIG;
            } else {
                inst = bl_find_instance_by_name(*netp);
                assert(inst != NULL);
                state = GET_PIN;
            }
            break;
        case GET_PIN:
            pin = bl_find_pin_in_instance_by_name(*netp, inst);
            assert(pin != NULL);
            retval = bl_link_pin_to_signal(pin, sig);
            assert(retval == BL_SUCCESS);
            state = GOT_SIG;
            break;
        default:
            assert(0);
        }
        netp++;
    }
#endif
}

#if 0
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
