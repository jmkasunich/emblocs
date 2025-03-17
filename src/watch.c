// EMBLOCS component - 'watch' for watching signals
//

#include "emblocs_comp.h"
#include "watch.h"
#include "printing.h"


#define WATCH_MAX_PINS 14
#define WATCH_PIN_COUNT_BITS   4
#define WATCH_PIN_TYPES_BITS  (WATCH_MAX_PINS*BL_TYPE_BITS)

#define WATCH_PIN_COUNT_MASK ((1<<(WATCH_PIN_COUNT_BITS))-1)
#define WATCH_PIN_TYPES_MASK ((1<<(WATCH_PIN_TYPES_BITS))-1)


_Static_assert(((WATCH_PIN_COUNT_BITS+WATCH_PIN_TYPES_BITS) <= 32), "watch bitfields too big");

// instance data structure - one copy per instance in RAM
// multiple watch_pin_rt_data_t structs are appended to this
// based on the personality
typedef struct bl_watch_instance_s {
    uint32_t pin_count          : WATCH_PIN_COUNT_BITS;
    uint32_t pin_types          : WATCH_PIN_TYPES_BITS;
} bl_watch_instance_t;

// pin data structure
typedef struct bl_watch_pin_s {
    bl_pin_t pin;
    char const *format;
} bl_watch_pin_rt_data_t;

#define WATCH_MAX_INSTANCE_SIZE (sizeof(bl_watch_instance_t)+WATCH_MAX_PINS*sizeof(bl_watch_pin_rt_data_t))

_Static_assert((WATCH_MAX_PINS < BL_PIN_COUNT_MAX), "too many pins");
_Static_assert((WATCH_MAX_INSTANCE_SIZE < BL_INSTANCE_DATA_MAX_SIZE), "instance structure too large");


static void bl_watch_update_function(void *ptr, uint32_t period_ns);

// array of function definitions - one copy in FLASH
static bl_function_def_t const bl_watch_functions[] = {
    { "update", BL_HAS_FP, &bl_watch_update_function }
};


/* component-specific setup function */
struct bl_instance_meta_s *watch_setup(char const *instance_name, struct bl_comp_def_s const *comp_def, void const *personality);


// component definition - one copy in FLASH
bl_comp_def_t const bl_watch_def = {
    "watch",
    watch_setup,
    sizeof(bl_watch_instance_t),
    0,
    _countof(bl_watch_functions),
    NULL,
    bl_watch_functions
};

/* component-specific setup function */
struct bl_instance_meta_s *watch_setup(char const *instance_name, struct bl_comp_def_s const *comp_def, void const *personality)
{
    watch_pin_config_t *pin_info;
    bl_watch_pin_rt_data_t *pin_data;
    uint32_t pins, types;
    struct bl_instance_meta_s *meta;
    bl_watch_instance_t *data;
    bl_pin_def_t pindef;

    // count pins in personality
    pin_info = (watch_pin_config_t *)personality;
    pins = 0;
    types = 0;
    while ( pin_info->name != NULL ) {
        types |= pin_info->type << (pins * BL_TYPE_BITS);
        pins++;
        pin_info++;
    }
    if ( pins > WATCH_MAX_PINS ) {
        #ifdef BL_ERROR_VERBOSE
        print_string("too many pins in personality\n");
        #endif
        return NULL;
    }
    // now the emblocs setup - create an instance of the proper size to include all the pin data
    meta = bl_instance_create(instance_name, comp_def, comp_def->data_size + (pins * sizeof(bl_watch_pin_rt_data_t)));
    data = bl_instance_data_addr(meta);
    // fill in instance data fields
    data->pin_count = pins & WATCH_PIN_COUNT_MASK;
    data->pin_types = types & WATCH_PIN_TYPES_MASK;
    // prepare for pin creation
    pin_info = (watch_pin_config_t *)personality;
    // dynamic pins follow the main instance data structure
    pin_data = (bl_watch_pin_rt_data_t *)(data+1);
    while ( pins > 0 ) {
        // fill in pin definition
        pindef.name = pin_info->name;
        pindef.data_type = pin_info->type;
        pindef.pin_dir = BL_DIR_IN;
        pindef.data_offset = TO_INSTANCE_SIZE((uint32_t)((char *)&(pin_data->pin) - (char *)data));
        // create the pin
        bl_instance_add_pin(meta, &pindef);
        // save the format string
        pin_data->format = pin_info->format;
        // next pin
        pin_data++;
        pin_info++;
        pins--;
    }
    return meta;
}


// realtime code - one copy in FLASH
static void bl_watch_update_function(void *ptr, uint32_t period_ns)
{
    (void)period_ns;  // not used
    bl_watch_instance_t *p = (bl_watch_instance_t *)ptr;
    int pins;
    uint32_t types;
    bl_type_t type;
    bl_watch_pin_rt_data_t *watch_pin;

    pins = p->pin_count;
    types = p->pin_types;
    // pin data immediately follows the instance structure
    watch_pin = (bl_watch_pin_rt_data_t *)(p+1);
    while ( pins > 0 ) {
        type = types & ((1<<(BL_TYPE_BITS))-1);
        switch(type) {
        case BL_TYPE_BIT:
            printf(watch_pin->format, watch_pin->pin->b);
            break;
        case BL_TYPE_FLOAT:
            printf(watch_pin->format, watch_pin->pin->f);
            break;
        case BL_TYPE_S32:
            printf(watch_pin->format, watch_pin->pin->s);
            break;
        case BL_TYPE_U32:
            printf(watch_pin->format, watch_pin->pin->u);
            break;
        default:
            break;
        }
        types >>= BL_TYPE_BITS;
        watch_pin++;
        pins--;
    }
}

