// EMBLOCS component - 'rgb' for merging/unmerging color components

#include "emblocs_comp.h"
#include "bl_rgb.h"
#include <stdlib.h>
#include "pico/stdlib.h"
#include <string.h>

#define RGB_MAX_CHANS 32

#define RGB_RED_BITS 10
#define RGB_GRN_BITS 11
#define RGB_BLU_BITS 11

#define RGB_RED_MASK ((1<<RGB_RED_BITS)-1)
#define RGB_GRN_MASK ((1<<RGB_GRN_BITS)-1)
#define RGB_BLU_MASK ((1<<RGB_BLU_BITS)-1)

//_Static_assert(((WATCH_PIN_COUNT_BITS+WATCH_PIN_TYPES_BITS) <= 32), "watch bitfields too big");

// block data structure - one copy per block in RAM
// multiple rgb_chan_rt_data_t structs are appended to this
// based on the personality
typedef struct bl_rgb_block_s {
    bl_rgb_config_t config;
    uint16_t padding;
} bl_rgb_block_t;

_Static_assert( (sizeof(bl_rgb_block_t) % 4) == 0);

typedef struct bl_rgb_chan_rt_data_s {
    bl_pin_u32_t merged;
    bl_pin_u32_t red;
    bl_pin_u32_t grn;
    bl_pin_u32_t blu;
} rgb_chan_rt_data_t;

#define RGB_MAX_PINS (RGB_MAX_CHANS*4)
#define RGB_MAX_BLOCK_SIZE (sizeof(bl_rgb_block_t)+RGB_MAX_CHANS*sizeof(rgb_chan_rt_data_t))

_Static_assert((RGB_MAX_PINS < BL_PIN_COUNT_MAX), "too many pins");
_Static_assert((RGB_MAX_BLOCK_SIZE < BL_BLOCK_DATA_MAX_SIZE), "block structure too large");


static void bl_rgb_merge_function(void *ptr, uint32_t period_ns);
static void bl_rgb_split_function(void *ptr, uint32_t period_ns);

// array of function definitions - one copy in FLASH
static bl_function_def_t const bl_rgb_merge_functions[] = {
    { "update", BL_HAS_FP, &bl_rgb_merge_function }
};

static bl_function_def_t const bl_rgb_split_functions[] = {
    { "update", BL_HAS_FP, &bl_rgb_split_function }
};


/* component-specific setup function */
struct bl_block_meta_s *rgb_setup(char const *block_name, struct bl_comp_def_s const *comp_def, void const *personality);

// component definitions - one copy in FLASH
bl_comp_def_t const bl_rgb_merge_def = {
    "rgb_merge",
    rgb_setup,
    sizeof(bl_rgb_block_t),
    BL_NEEDS_PERSONALITY,
    0,
    _countof(bl_rgb_merge_functions),
    NULL,
    bl_rgb_merge_functions
};

bl_comp_def_t const bl_rgb_split_def = {
    "rgb_split",
    rgb_setup,
    sizeof(bl_rgb_block_t),
    BL_NEEDS_PERSONALITY,
    0,
    _countof(bl_rgb_split_functions),
    NULL,
    bl_rgb_split_functions
};

/* component-specific setup function */
#pragma GCC optimize ("no-strict-aliasing")
struct bl_block_meta_s *rgb_setup(char const *block_name, struct bl_comp_def_s const *comp_def, void const *personality)
{
    bl_rgb_config_t *cfg_info;
    bool is_merge;
    rgb_chan_rt_data_t *chan_data;
    struct bl_block_meta_s *meta;
    bl_rgb_block_t *data;
    bl_pin_def_t pindef;
    bool result;
    char *name, *basename;

    CHECK_NULL(comp_def);
    CHECK_NULL(personality);
    if ( comp_def->name[4] == 'm' ) {
        is_merge = true;
    } else if ( comp_def->name[4] == 's' ) {
        is_merge = false;
    } else {
        ERROR_RETURN(BL_ERR_RANGE);
    }
    // validate personality
    cfg_info = (bl_rgb_config_t *)personality;
    if ( ( cfg_info->color_bits < 8 ) || ( cfg_info->color_bits > 32 ) ) {
        ERROR_RETURN(BL_ERR_RANGE);
    }
    if ( ( cfg_info->num_chan < 1 ) || ( cfg_info->num_chan > RGB_MAX_CHANS) ) {
        ERROR_RETURN(BL_ERR_RANGE);
    }
    // now the emblocs setup - create a block of the proper size to include all the channel data
    meta = bl_block_create(block_name, comp_def, comp_def->data_size + (cfg_info->num_chan * sizeof(rgb_chan_rt_data_t)));
    CHECK_RETURN(meta);
    data = bl_block_data_addr(meta);
    CHECK_RETURN(data);
    // fill in block data fields
    data->config.color_bits = cfg_info->color_bits;
    data->config.num_chan = cfg_info->num_chan;
    // prepare for pin creation
    // dynamic pins follow the main block data structure
    chan_data = (rgb_chan_rt_data_t *)(data+1);
    for ( int n = 0 ; n < cfg_info->num_chan ; n++ ) {
        // generate base pin name: "rgbxx" where xx is channel number
        name = malloc(6);
        name[0] = 'r';
        name[1] = 'g';
        name[2] = 'b';
        name[3] = (char)('0' + (n/10));
        name[4] = (char)('0' + (n%10));
        name[5] = '\0';
        basename = name;
        // fill in pin definition
        pindef.name = name;
        pindef.data_type = BL_TYPE_U32;
        pindef.pin_dir = is_merge ? BL_DIR_OUT : BL_DIR_IN;
        pindef.data_offset = TO_BLOCK_SIZE((uint32_t)((char *)&(chan_data->merged) - (char *)data));
        // create the pin
        result = bl_block_add_pin(meta, &pindef);
        CHECK_RETURN(result);
        // next pin
        name = malloc(10);
        strcpy(name, basename);
        strcat(name, "_red");
        pindef.name = name;
        pindef.pin_dir = is_merge ? BL_DIR_IN : BL_DIR_OUT;
        pindef.data_offset = TO_BLOCK_SIZE((uint32_t)((char *)&(chan_data->red) - (char *)data));
        result = bl_block_add_pin(meta, &pindef);
        CHECK_RETURN(result);
        // next pin
        name = malloc(10);
        strcpy(name, basename);
        strcat(name, "_grn");
        pindef.name = name;
        pindef.data_offset = TO_BLOCK_SIZE((uint32_t)((char *)&(chan_data->grn) - (char *)data));
        result = bl_block_add_pin(meta, &pindef);
        CHECK_RETURN(result);
        // next pin
        name = malloc(10);
        strcpy(name, basename);
        strcat(name, "_blu");
        pindef.name = name;
        pindef.data_offset = TO_BLOCK_SIZE((uint32_t)((char *)&(chan_data->blu) - (char *)data));
        result = bl_block_add_pin(meta, &pindef);
        CHECK_RETURN(result);
        // next channel
        chan_data++;
    }
    // finally, create the functions; nothing custom here
    result = bl_block_add_functions(meta, comp_def);
    CHECK_RETURN(result);
    return meta;
}
#pragma GCC reset_options


// realtime code - one copy in FLASH
#pragma GCC optimize ("no-strict-aliasing")
static void __time_critical_func(bl_rgb_merge_function)(void *ptr, uint32_t period_ns)
{
    (void)period_ns;  // not used
    bl_rgb_block_t *p = (bl_rgb_block_t *)ptr;
    rgb_chan_rt_data_t *chan_data;
    uint32_t mask = (1u<<p->config.color_bits)-1u;
    uint32_t merge, comp;
    int shiftr, shiftg, shiftb;

    shiftr = p->config.color_bits - RGB_RED_BITS;
    shiftg = p->config.color_bits - RGB_GRN_BITS;
    shiftb = p->config.color_bits - RGB_BLU_BITS;
    // pin data immediately follows the block structure
    chan_data = (rgb_chan_rt_data_t *)(p+1);
    for ( int n = 0 ; n < p->config.num_chan ; n++ ) {
        merge = 0;
        comp = *(chan_data->red) & mask;
        if ( shiftr > 0 ) {
            comp >>= shiftr;
        } else if ( shiftr < 0 ) {
            comp <<= -shiftr;
        }
        merge = comp;
        comp = *(chan_data->grn) & mask;
        if ( shiftg > 0 ) {
            comp >>= shiftg;
        } else if ( shiftg < 0 ) {
            comp <<= -shiftg;
        }
        merge |= (comp << RGB_RED_BITS);
        comp = *(chan_data->blu) & mask;
        if ( shiftb > 0 ) {
            comp >>= shiftb;
        } else if ( shiftb < 0 ) {
            comp <<= -shiftb;
        }
        merge |= (comp << (RGB_RED_BITS+RGB_GRN_BITS));
        *(chan_data->merged) = merge;
        chan_data++;
    }
}
#pragma GCC reset_options

#pragma GCC optimize ("no-strict-aliasing")
static void __time_critical_func(bl_rgb_split_function)(void *ptr, uint32_t period_ns)
{
    (void)period_ns;  // not used
    bl_rgb_block_t *p = (bl_rgb_block_t *)ptr;
    rgb_chan_rt_data_t *chan_data;
    uint32_t merge, comp;
    int shiftr, shiftg, shiftb;

    shiftr = p->config.color_bits - RGB_RED_BITS;
    shiftg = p->config.color_bits - RGB_GRN_BITS;
    shiftb = p->config.color_bits - RGB_BLU_BITS;
    // pin data immediately follows the block structure
    chan_data = (rgb_chan_rt_data_t *)(p+1);
    for ( int n = 0 ; n < p->config.num_chan ; n++ ) {
        merge = *(chan_data->merged);
        comp = merge & RGB_RED_MASK;
        if ( shiftr > 0 ) {
            comp <<= shiftr;
        } else if ( shiftr < 0 ) {
            comp >>= -shiftr;
        }
        *(chan_data->red) = comp;
        merge >>= RGB_RED_BITS;
        comp = merge & RGB_GRN_MASK;
        if ( shiftg > 0 ) {
            comp <<= shiftg;
        } else if ( shiftg < 0 ) {
            comp >>= -shiftg;
        }
        *(chan_data->grn) = comp;
        merge >>= RGB_GRN_BITS;
        comp = merge & RGB_BLU_MASK;
        if ( shiftb > 0 ) {
            comp <<= shiftb;
        } else if ( shiftb < 0 ) {
            comp >>= -shiftb;
        }
        *(chan_data->blu) = comp;
        chan_data++;
    }
}
#pragma GCC reset_options

