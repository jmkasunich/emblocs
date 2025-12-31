// EMBLOCS component - 'watch' for watching signals
//

#include "emblocs_comp.h"
#include "watch.h"
#include "printing.h"


#define WATCH_MAX_PINS 9
#define WATCH_PIN_COUNT_BITS   4
#define WATCH_PIN_TYPES_BITS  (WATCH_MAX_PINS*BL_TYPE_BITS)

#define WATCH_PIN_COUNT_MASK ((1<<(WATCH_PIN_COUNT_BITS))-1)
#define WATCH_PIN_TYPES_MASK ((1<<(WATCH_PIN_TYPES_BITS))-1)


_Static_assert(((WATCH_PIN_COUNT_BITS+WATCH_PIN_TYPES_BITS) <= 32), "watch bitfields too big");

// block data structure - one copy per block in RAM
// multiple watch_pin_rt_data_t structs are appended to this
// based on the personality
typedef struct bl_watch_block_s {
    uint32_t pin_count          : WATCH_PIN_COUNT_BITS;
    uint32_t pin_types          : WATCH_PIN_TYPES_BITS;
} bl_watch_block_t;

// pin data structure
typedef struct bl_watch_pin_s {
    bl_pin_t pin;
    char const *format;
} bl_watch_pin_rt_data_t;

#define WATCH_MAX_BLOCK_SIZE (sizeof(bl_watch_block_t)+WATCH_MAX_PINS*sizeof(bl_watch_pin_rt_data_t))

_Static_assert((WATCH_MAX_PINS < BL_PIN_COUNT_MAX), "too many pins");
_Static_assert((WATCH_MAX_BLOCK_SIZE < BL_BLOCK_DATA_MAX_SIZE), "block structure too large");


static void bl_watch_update_function(void *ptr, uint32_t period_ns);

// array of function definitions - one copy in FLASH
static bl_function_def_t const bl_watch_functions[] = {
    { "update", BL_HAS_FP, &bl_watch_update_function }
};


/* component-specific setup function */
struct bl_block_meta_s *watch_setup(char const *block_name, struct bl_comp_def_s const *comp_def, void const *personality);


// component definition - one copy in FLASH
bl_comp_def_t const bl_watch_def = {
    "watch",
    watch_setup,
    sizeof(bl_watch_block_t),
    BL_NEEDS_PERSONALITY,
    0,
    _countof(bl_watch_functions),
    NULL,
    bl_watch_functions
};

/* component-specific setup function */
#pragma GCC optimize ("no-strict-aliasing")
struct bl_block_meta_s *watch_setup(char const *block_name, struct bl_comp_def_s const *comp_def, void const *personality)
{
    watch_pin_config_t *pin_info;
    bl_watch_pin_rt_data_t *pin_data;
    uint32_t pins, types;
    struct bl_block_meta_s *meta;
    bl_watch_block_t *data;
    bl_pin_def_t pindef;
    bool result;

    CHECK_NULL(comp_def);
    CHECK_NULL(personality);
    // count pins in personality
    pin_info = (watch_pin_config_t *)personality;
    pins = 0;
    types = 0;
    while ( pin_info->name != NULL ) {
        // FIXME - someday support watching raw pins?
        if ( pin_info->type >= BL_TYPE_RAW ) {
            ERROR_RETURN(BL_ERR_TYPE_MISMATCH);
        }
        types |= pin_info->type << (pins * BL_TYPE_BITS);
        pins++;
        pin_info++;
    }
    if ( pins > WATCH_MAX_PINS ) {
        ERROR_RETURN(BL_ERR_RANGE);
    }
    // now the emblocs setup - create a block of the proper size to include all the pin data
    meta = bl_block_create(block_name, comp_def, comp_def->data_size + (pins * sizeof(bl_watch_pin_rt_data_t)));
    CHECK_RETURN(meta);
    data = bl_block_data_addr(meta);
    CHECK_RETURN(data);
    // fill in block data fields
    data->pin_count = pins & WATCH_PIN_COUNT_MASK;
    data->pin_types = types & WATCH_PIN_TYPES_MASK;
    // prepare for pin creation
    pin_info = (watch_pin_config_t *)personality;
    // dynamic pins follow the main block data structure
    pin_data = (bl_watch_pin_rt_data_t *)(data+1);
    while ( pins > 0 ) {
        // fill in pin definition
        pindef.name = pin_info->name;
        pindef.data_type = pin_info->type;
        pindef.pin_dir = BL_DIR_IN;
        pindef.data_offset = TO_BLOCK_SIZE((uint32_t)((char *)&(pin_data->pin) - (char *)data));
        // create the pin
        result = bl_block_add_pin(meta, &pindef);
        CHECK_RETURN(result);
        // save the format string
        pin_data->format = pin_info->format;
        // next pin
        pin_data++;
        pin_info++;
        pins--;
    }
    // finally, create the functions; nothing custom here
    result = bl_block_add_functions(meta, comp_def);
    CHECK_RETURN(result);
    return meta;
}
#pragma GCC reset_options


// realtime code - one copy in FLASH
#pragma GCC optimize ("no-strict-aliasing")
static void bl_watch_update_function(void *ptr, uint32_t period_ns)
{
    (void)period_ns;  // not used
    bl_watch_block_t *p = (bl_watch_block_t *)ptr;
    int pins;
    uint32_t types;
    bl_type_t type;
    bl_watch_pin_rt_data_t *watch_pin;

    pins = p->pin_count;
    types = p->pin_types;
    // pin data immediately follows the block structure
    watch_pin = (bl_watch_pin_rt_data_t *)(p+1);
    while ( pins > 0 ) {
        type = types & ((1<<(BL_TYPE_BITS))-1);
        switch(type) {
        case BL_TYPE_BIT:
            printf(watch_pin->format, watch_pin->pin->b);
            break;
        case BL_TYPE_FLOAT:
            printf(watch_pin->format, (double)watch_pin->pin->f);
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
#pragma GCC reset_options

