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

/***********************************************
 * memory pools
 */

uint32_t bl_rt_pool[BL_RT_POOL_SIZE >> 2]  __attribute__ ((aligned(4)));
uint32_t *bl_rt_pool_next = bl_rt_pool;
int32_t bl_rt_pool_avail = sizeof(bl_rt_pool);
const int32_t bl_rt_pool_size = sizeof(bl_rt_pool);

uint32_t bl_meta_pool[BL_META_POOL_SIZE >> 2]  __attribute__ ((aligned(4)));
uint32_t *bl_meta_pool_next = bl_meta_pool;
int32_t bl_meta_pool_avail = sizeof(bl_meta_pool);
const int32_t bl_meta_pool_size = sizeof(bl_meta_pool);

/* memory allocation functions */

/* I do a bunch of pointer manipulation 
   and type-punning in this file */
#pragma GCC optimize ("no-strict-aliasing")

static void *alloc_from_rt_pool(int32_t size)
{
    void *retval;

    if ( size <= 0 ) halt();
    // round size up to multiple of 4
    if ( size & 3 ) {
        size += 4;
        size &= ~3;
    }
    if ( bl_rt_pool_avail < size) {
        #ifdef BL_ERROR_VERBOSE
        print_string("insufficient realtime RAM\n");
        #endif
        halt_or_return(NULL);
    }
    retval = bl_rt_pool_next;
    bl_rt_pool_next += size/4;
    bl_rt_pool_avail -= size;
    return retval;
}

static void *alloc_from_meta_pool(int32_t size)
{
    void *retval;

    if ( size <= 0 ) halt();
    // round size up to multiple of 4
    if ( size & 3 ) {
        size += 4;
        size &= ~3;
    }
    if ( bl_meta_pool_avail < size) {
        #ifdef BL_ERROR_VERBOSE
        print_string("insufficient metadata RAM\n");
        #endif
        halt_or_return(NULL);
    }
    retval = bl_meta_pool_next;
    bl_meta_pool_next += size/4;
    bl_meta_pool_avail -= size;
    return retval;
}


/* root of instance linked list */
bl_instance_meta_t *instance_root;

/* root of signal linked list */
bl_signal_meta_t *signal_root;

/* root of thread linked list */
bl_thread_meta_t *thread_root;


/* linked list callback functions */
static int instance_meta_compare_names(void *node1, void *node2)
{
    bl_instance_meta_t  *np1 = node1;
    bl_instance_meta_t  *np2 = node2;
    return strcmp(np1->name, np2->name);
}

static int pin_meta_compare_names(void *node1, void *node2)
{
    bl_pin_meta_t  *np1 = node1;
    bl_pin_meta_t  *np2 = node2;
    return strcmp(np1->name, np2->name);
}

static int function_meta_compare_names(void *node1, void *node2)
{
    bl_function_meta_t  *np1 = node1;
    bl_function_meta_t  *np2 = node2;
    return strcmp(np1->name, np2->name);
}

static int sig_meta_compare_names(void *node1, void *node2)
{
    bl_signal_meta_t  *np1 = node1;
    bl_signal_meta_t  *np2 = node2;
    return strcmp(np1->name, np2->name);
}

static int thread_meta_compare_names(void *node1, void *node2)
{
    bl_thread_meta_t  *np1 = node1;
    bl_thread_meta_t  *np2 = node2;
    return strcmp(np1->name, np2->name);
}


/**************************************************************
 * Top-level EMBLOCS API functions used to build a system     *
 **************************************************************/

struct bl_instance_meta_s *bl_instance_new(char const *name, struct bl_comp_def_s const *comp_def, void const *personality)
{
    struct bl_instance_meta_s *retval;

    if ( comp_def->setup == NULL ) {
        // no setup function, cannot support personality
        if ( personality != NULL) {
            #ifdef BL_ERROR_VERBOSE
            print_strings(3, "component: '", comp_def->name, "' does not support personality\n");
            #endif
            halt_or_return(NULL);
        }
        // call default setup function
        retval = bl_default_setup(name, comp_def);
    } else {
        // call component-specific setup function
        retval = comp_def->setup(name, comp_def, personality);
    }
    if ( retval == NULL ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(4, "cound not create ", "instance '", name, "'\n");
        #endif
        halt_or_return(retval);
    }
    return retval;
}

struct bl_signal_meta_s *bl_signal_new(char const *name, bl_type_t type)
{
    struct bl_signal_meta_s *meta;
    bl_sig_data_t *data;
    int ll_result;

    // allocate memory for metadata
    meta = alloc_from_meta_pool(sizeof(bl_signal_meta_t));
    // allocate memory for signal data
    data = alloc_from_rt_pool(sizeof(bl_sig_data_t));
    #ifndef BL_ERROR_HALT
    if ( ( meta == NULL ) || ( data == NULL ) ) {
        goto error;
    }
    #endif
    // initialize signal to zero
    data->u = 0;
    // initialise metadata fields
    meta->data_index = TO_RT_INDEX(data);
    meta->data_type = type;
    meta->name = name;
    // add metadata to master signal list
    ll_result = ll_insert((void **)(&(signal_root)), (void *)meta, sig_meta_compare_names);
    if ( ll_result != 0 ) {
        #ifdef BL_ERROR_VERBOSE
        print_string("duplicate name\n");
        #endif
        goto error;
    }
    return meta;

    error:
    #ifdef BL_ERROR_VERBOSE
    print_strings(4, "could not create ", "signal: '", name, "'\n");
    #endif
    halt_or_return(NULL);
}

bool bl_pin_linkto_signal(bl_pin_meta_t const *pin, bl_signal_meta_t const *sig )
{
    bl_sig_data_t *sig_data_addr, **pin_ptr_addr;

    // check types
    if ( pin->data_type != sig->data_type ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(7, "cannot link ", "pin: '", pin->name, "' to ", "signal: '", sig->name, "'; type mismatch\n");
        #endif
        halt_or_return(false);
    }
    // convert indexes to addresses
    pin_ptr_addr = TO_RT_ADDR(pin->ptr_index);
    sig_data_addr = TO_RT_ADDR(sig->data_index);
    #ifndef BL_ENABLE_IMPLICIT_UNLINK
    bl_sig_data_t *dummy_addr = TO_RT_ADDR(pin->dummy_index);
    if ( *pin_ptr_addr != dummy_addr ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(7, "cannot link ",  "pin: '", pin->name, "' to ", "signal: '", sig->name, "'; already linked\n" );
        #endif
        halt_or_return(false);
    }
    #endif
    // make the link (this automatically undoes any previous linkage)
    *pin_ptr_addr = sig_data_addr;
    return true;

}

#ifdef BL_ENABLE_UNLINK
bool bl_pin_unlink(bl_pin_meta_t const *pin)
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
    return true;
}
#endif

bool bl_signal_set(bl_signal_meta_t const *sig, bl_sig_data_t const *value)
{
    bl_sig_data_t *sig_data;

    sig_data = TO_RT_ADDR(sig->data_index);
    *sig_data = *value;
    return true;
}

bool bl_pin_set(bl_pin_meta_t const *pin, bl_sig_data_t const *value)
{
    bl_sig_data_t **pin_ptr, *sig_data;

    pin_ptr = TO_RT_ADDR(pin->ptr_index);
    sig_data = *pin_ptr;
    *sig_data = *value;
    return true;
}

struct bl_thread_meta_s *bl_thread_new(char const *name, uint32_t period_ns, bl_nofp_t nofp)
{
    bl_thread_meta_t *meta;
    bl_thread_data_t *data;
    int ll_result;

    // allocate memory for metadata
    meta = alloc_from_meta_pool(sizeof(bl_thread_meta_t));
    // allocate memory for RT thread data
    data = alloc_from_rt_pool(sizeof(bl_thread_data_t));
    #ifndef BL_ERROR_HALT
    if ( ( meta == NULL ) || ( data == NULL ) ) {
        goto error;
    }
    #endif
    // initialize data fields
    data->period_ns = period_ns;
    data->start = NULL;
    // initialise metadata fields
    meta->data_index = TO_RT_INDEX(data);
    meta->nofp = nofp;
    meta->name = name;
    // add metadata to master thread list
    ll_result = ll_insert((void **)(&(thread_root)), (void *)meta, thread_meta_compare_names);
    if ( ll_result != 0 ) {
        #ifdef BL_ERROR_VERBOSE
        print_string("duplicate name\n");
        #endif
        goto error;
    }
    return meta;

    error:
    #ifdef BL_ERROR_VERBOSE
    print_strings(4, "could not create ", "thread: '", name, "'\n");
    #endif
    halt_or_return(NULL);
}

bool bl_function_linkto_thread(struct bl_function_meta_s *funct, struct bl_thread_meta_s const *thread)
{
    bl_function_rtdata_t *funct_data;
    bl_thread_data_t *thread_data;
    bl_function_rtdata_t *prev, **prev_ptr;

    // validate floating point
    if ( ( thread->nofp == BL_NO_FP) && ( funct->nofp == BL_HAS_FP ) ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(7, "cannot link ", "function: '", funct->name, "' to ", "thread: '", thread->name, "'; type mismatch\n");
        #endif
        halt_or_return(false);
    }
    if ( funct->thread_index != BL_META_MAX_INDEX ) {
        #ifdef BL_ENABLE_IMPLICIT_UNLINK
        bl_function_unlink(funct);
        #else
        #ifdef BL_ERROR_VERBOSE
        print_strings(7, "cannot link ",  "function: '", funct->name, "' to ", "thread: '", thread->name, "'; already linked\n" );
        #endif
        halt_or_return(false);
        #endif
    }
    // link function metadata back to the thread
    funct->thread_index = TO_META_INDEX(thread);
    // get pointers to realtime data
    funct_data = TO_RT_ADDR(funct->rtdata_index);
    thread_data = TO_RT_ADDR(thread->data_index);
    // find end of thread
    prev_ptr = &(thread_data->start);
    prev = *prev_ptr;
    while ( prev != NULL ) {
        prev_ptr = &(prev->next);
        prev = *prev_ptr;
    }
    // append function RT data to thread
    funct_data->next = NULL;
    *prev_ptr = funct_data;
    return true;
}

#ifdef  BL_ENABLE_UNLINK
bool bl_function_unlink(struct bl_function_meta_s *funct)
{
    bl_thread_meta_t *thread;
    bl_function_rtdata_t *funct_data;
    bl_thread_data_t *thread_data;
    bl_function_rtdata_t *prev, **prev_ptr;

    if ( funct->thread_index == BL_META_MAX_INDEX ) {
        // function is not in a thread; done
        return true;
    }
    thread = TO_META_ADDR(funct->thread_index);
    // get pointers to realtime data
    funct_data = TO_RT_ADDR(funct->rtdata_index);
    thread_data = TO_RT_ADDR(thread->data_index);
    // traverse thread list
    prev_ptr = &(thread_data->start);
    prev = *prev_ptr;
    while ( prev != NULL ) {
        if ( prev == funct_data ) {
            // found it, unlink
            *prev_ptr = funct_data->next;
            // reset metadata to 'unlinked'
            funct->thread_index = BL_META_MAX_INDEX;
            return true;
        }
        prev_ptr = &(prev->next);
        prev = *prev_ptr;
    }
    // not found in thread
    #ifdef BL_ERROR_VERBOSE
    print_string("data corruption\n");
    #endif
    halt();
}
#endif

void bl_thread_run(struct bl_thread_data_s const *thread, uint32_t period_ns)
{
    bl_function_rtdata_t *function;

    if ( period_ns == 0 ) {
        period_ns = thread->period_ns;
    }
    function = thread->start;
    while ( function != NULL ) {
        // call the function
        (*(function->funct))(function->instance_data, period_ns);
        function = function->next;
    }
}

struct bl_thread_data_s *bl_thread_get_data(struct bl_thread_meta_s *thread)
{
    return TO_RT_ADDR(thread->data_index);
}


/* linked list callback functions */
int bl_instance_meta_compare_name_key(void *node, void *key)
{
    bl_instance_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
}

int bl_sig_meta_compare_name_key(void *node, void *key)
{
    bl_signal_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
}

int bl_thread_meta_compare_name_key(void *node, void *key)
{
    bl_thread_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
}

int bl_pin_meta_compare_name_key(void *node, void *key)
{
    bl_pin_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
}

int bl_function_meta_compare_name_key(void *node, void *key)
{
    bl_function_meta_t *np = node;
    char *kp = key;
    return strcmp(np->name, kp);
}

struct bl_instance_meta_s *bl_instance_find(char const *name)
{
    bl_instance_meta_t *retval;

    if ( name != NULL ) {
        retval = ll_find((void **)(&(instance_root)), (void *)(name), bl_instance_meta_compare_name_key);
    } else {
        retval = NULL;
        #ifdef BL_ERROR_VERBOSE
        name = "<NULL>";
        #endif
    }
    if ( retval == NULL ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(4, "not found: ", "instance: '", name, "'\n");
        #endif
        halt_or_return(NULL);
    }
    return retval;
}

struct bl_signal_meta_s *bl_signal_find(char const *name)
{
    bl_signal_meta_t *retval;

    if ( name != NULL ) {
        retval = ll_find((void **)(&(signal_root)), (void *)(name), bl_sig_meta_compare_name_key);
    } else {
        retval = NULL;
        #ifdef BL_ERROR_VERBOSE
        name = "<NULL>";
        #endif
    }
    if ( retval == NULL ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(4, "not found: ", "signal: '", name, "'\n");
        #endif
        halt_or_return(NULL);
    }
    return retval;
}

struct bl_thread_meta_s *bl_thread_find(char const *name)
{
    bl_thread_meta_t *retval;

    if ( name != NULL ) {
        retval = ll_find((void **)(&(thread_root)), (void *)(name), bl_thread_meta_compare_name_key);
    } else {
        retval = NULL;
        #ifdef BL_ERROR_VERBOSE
        name = "<NULL>";
        #endif
    }
    if ( retval == NULL ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(4, "not found: ", "thread: '", name, "'\n");
        #endif
        halt_or_return(NULL);
    }
    return retval;
}

struct bl_pin_meta_s *bl_pin_find_in_instance(char const *name, struct bl_instance_meta_s *inst)
{
    bl_pin_meta_t *retval;
    #ifdef BL_ERROR_VERBOSE
    char const *instname;
    #endif

    if ( ( inst != NULL ) && ( name != NULL ) ) {
        retval = ll_find((void **)(&(inst->pin_list)), (void *)(name), bl_pin_meta_compare_name_key);
        #ifdef BL_ERROR_VERBOSE
        instname = inst->name;
        #endif
    } else {
        retval = NULL;
        #ifdef BL_ERROR_VERBOSE
        if ( inst == NULL ) {
            instname = "<NULL>";
        }
        if ( name == NULL ) {
            name = "<NULL>";
        }
        #endif
    }
    if ( retval == NULL ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(7, "not found: ", "pin: '", name, "' in ", "instance: '", instname, "'\n");
        #endif
        halt_or_return(NULL);
    }
    return retval;
}

struct bl_function_meta_s *bl_function_find_in_instance(char const *name, struct bl_instance_meta_s *inst)
{
    bl_function_meta_t *retval;
    #ifdef BL_ERROR_VERBOSE
    char const *instname;
    #endif

    if ( ( inst != NULL ) && ( name != NULL ) ) {
        retval = ll_find((void **)(&(inst->function_list)), (void *)(name), bl_function_meta_compare_name_key);
        #ifdef BL_ERROR_VERBOSE
        instname = inst->name;
        #endif
    } else {
        retval = NULL;
        #ifdef BL_ERROR_VERBOSE
        if ( inst == NULL ) {
            instname = "<NULL>";
        }
        if ( name == NULL ) {
            name = "<NULL>";
        }
        #endif
    }
    if ( retval == NULL ) {
        #ifdef BL_ERROR_VERBOSE
        print_strings(7, "not found: ", "function: '", name, "' in ", "instance: '", instname, "'\n");
        #endif
        halt_or_return(NULL);
    }
    return retval;
}

struct bl_instance_meta_s *bl_default_setup(char const *name, bl_comp_def_t const *comp_def)
{
    bl_instance_meta_t *meta;
    bool retval __attribute__ ((unused));

    meta = bl_instance_create(name, comp_def, 0);
    #ifndef BL_ERROR_HALT
    if ( meta == NULL ) {
        goto error;
    }
    #endif
    retval = bl_instance_add_pins(meta, comp_def);
    #ifndef BL_ERROR_HALT
    if ( ! retval ) {
        goto error;
    }
    #endif
    retval = bl_instance_add_functions(meta, comp_def);
    #ifndef BL_ERROR_HALT
    if ( ! retval ) {
        goto error;
    }
    #endif
    return meta;

    #ifndef BL_ERROR_HALT
    error:
    #ifdef BL_ERROR_VERBOSE
    print_strings(7, "could not set up ", "instance: '", name, "' of ", "component: '", comp_def->name, "'\n");
    #endif
    halt_or_return(NULL);
    #endif
}

struct bl_instance_meta_s *bl_instance_create(char const *name, bl_comp_def_t const *comp_def, uint32_t data_size)
{
    bl_instance_meta_t *meta;
    void *data;
    int ll_result;

    if ( data_size == 0 ) {
        data_size = comp_def->data_size;
    }
    if ( data_size >= BL_INSTANCE_DATA_MAX_SIZE ) {
        #ifdef BL_ERROR_VERBOSE
        print_string("instance data too large\n");
        #endif
        goto error;
    }
    // allocate memory for metadata
    meta = alloc_from_meta_pool(sizeof(bl_instance_meta_t));
    // allocate memory for realtime data
    data = alloc_from_rt_pool(data_size);
    #ifndef BL_ERROR_HALT
    if ( ( meta == NULL ) || ( data == NULL ) ) {
        goto error;
    }
    #endif
    // initialise metadata fields
    meta->comp_def = comp_def;
    meta->data_index = TO_RT_INDEX(data);
    meta->data_size = TO_INSTANCE_SIZE(data_size);
    meta->name = name;
    meta->pin_list = NULL;
    // add metadata to master instance list
    ll_result = ll_insert((void **)(&instance_root), (void *)meta, instance_meta_compare_names);
    if ( ll_result != 0 ) {
        #ifdef BL_ERROR_VERBOSE
        print_string("duplicate name\n");
        #endif
        goto error;
    }
    return meta;

    error:
    #ifdef BL_ERROR_VERBOSE
    print_strings(4, "could not create ", "instance: '", name, "'\n");
    #endif
    halt_or_return(NULL);
}

void *bl_instance_data_addr(struct bl_instance_meta_s *inst)
{
    return TO_RT_ADDR(inst->data_index);
}

bool bl_instance_add_pin(struct bl_instance_meta_s *inst, bl_pin_def_t const *def)
{
    bl_pin_meta_t *meta;
    bl_sig_data_t *data;
    bl_sig_data_t **ptr_addr;
    int ll_result;

    // allocate memory for metadata
    meta = alloc_from_meta_pool(sizeof(bl_pin_meta_t));
    // allocate memory for dummy signal
    data = alloc_from_rt_pool(sizeof(bl_sig_data_t));
    #ifndef BL_ERROR_HALT
    if ( ( meta == NULL ) || ( data == NULL ) ) {
        goto error;    
    }
    #endif
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
    ll_result = ll_insert((void **)(&(inst->pin_list)), (void *)meta, pin_meta_compare_names);
    if ( ll_result != 0 ) {
        #ifdef BL_ERROR_VERBOSE
        print_string("duplicate name\n");
        #endif
        goto error;
    }
    return true;

    error:
    #ifdef BL_ERROR_VERBOSE
    print_strings(6, "could not create ", "pin: '", inst->name, ".", def->name, "'\n");
    #endif
    halt_or_return(false);
}

bool bl_instance_add_pins(struct bl_instance_meta_s *inst, bl_comp_def_t const *def)
{
    bool retval;
    int errors = 0;

    for ( int i = 0 ; i < def->pin_count ; i++ ) {
        retval = bl_instance_add_pin(inst, &(def->pin_defs[i]));
        if ( ! retval ) {
            errors++;
        }
    }
    if ( errors > 0 ) {
        return false;
    } else {
        return true;
    }
}

bool bl_instance_add_function(struct bl_instance_meta_s *inst, bl_function_def_t const *def)
{
    bl_function_meta_t *meta;
    bl_function_rtdata_t *data;
    int ll_result;

    // allocate memory for metadata
    meta = alloc_from_meta_pool(sizeof(bl_function_meta_t));
    // allocate memory for realtime data
    data = alloc_from_rt_pool(sizeof(bl_function_rtdata_t));
    #ifndef BL_ERROR_HALT
    if ( ( meta == NULL ) || ( data == NULL ) ) {
        goto error;
    }
    #endif
    // initialize realtime data fields
    data->funct = def->fp;
    data->instance_data = TO_RT_ADDR(inst->data_index);
    data->next = NULL;
    // initialise metadata fields
    meta->rtdata_index = TO_RT_INDEX(data);
    meta->nofp = def->nofp;
    meta->name = def->name;
    meta->thread_index = BL_META_MAX_INDEX;  // MAX means not in a thread
    // add metadata to instances's function list
    ll_result = ll_insert((void **)(&(inst->function_list)), (void *)meta, function_meta_compare_names);
    if ( ll_result != 0 ) {
        #ifdef BL_ERROR_VERBOSE
        print_string("duplicate name\n");
        #endif
        goto error;
    }
    return true;

    error:
    #ifdef BL_ERROR_VERBOSE
    print_strings(6, "could not create ", "function: '", inst->name, ".", def->name, "'\n");
    #endif
    halt_or_return(false);
}

bool bl_instance_add_functions(struct bl_instance_meta_s *inst, bl_comp_def_t const *def)
{
    bool retval;
    int errors = 0;

    for ( int i = 0 ; i < def->function_count ; i++ ) {
        retval = bl_instance_add_function(inst, &(def->function_defs[i]));
        if ( ! retval ) {
            errors++;
        }
    }
    if ( errors > 0 ) {
        return false;
    } else {
        return true;
    }
}

#pragma GCC reset_options
