/***************************************************************
 * 
 * emblocs.h - headers for EMBLOCS
 * 
 * Embedded Block-Oriented Control System
 * 
 * 
 * 
 * *************************************************************/

#ifndef EMBLOCS_H
#define EMBLOCS_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>


#define ARRAYCOUNT(foo)  (sizeof(foo)/sizeof((foo)[0]))
#define BL_OFFSET(type, member)  ((bl_offset_t)(offsetof(type,member)))

typedef uint16_t bl_offset_t;

typedef enum bl_pintype_e {
	BL_PINTYPE_FLOAT    = 0x00,
	BL_PINTYPE_BIT      = 0x01,
	BL_PINTYPE_SINT     = 0x02,
	BL_PINTYPE_UINT     = 0x03
} bl_pintype_t;

#define BL_PINTYPE_MASK (0x03)

typedef enum bl_pindir_e {
	BL_PINDIR_IN        = 0x04,
	BL_PINDIR_OUT       = 0x08,
	BL_PINDIR_IO        = 0x0C,
} bl_pindir_t;

#define BL_PINDIR_MASK (0x0C)

typedef float bl_float_t;
typedef bool bl_bit_t;
typedef int32_t bl_s32_t;
typedef uint32_t bl_u32_t;

typedef union bl_sigdata_u {
	bl_float_t f;
	bl_bit_t b;
	bl_s32_t s;
	bl_u32_t u;
    union bl_sigdata_u *next_free;
} bl_sigdata_t;

typedef struct bl_inst_header_s {
    char const *inst_name;
    struct bl_inst_header_s *next_inst;
    struct bl_comp_def_s *definition;
} bl_inst_header_t;

typedef struct bl_pin_def_s {
    char const * const name;
    bl_pintype_t const type;
    bl_pindir_t const dir;
    bl_offset_t const offset;
} bl_pin_def_t;

typedef struct bl_funct_def_s {
    char const * const name;
    void (*fp) (bl_inst_header_t *);
} bl_funct_def_t;

typedef struct bl_comp_def_s {
    char const * const name;
    uint8_t const pin_count;
    uint8_t const funct_count;
    uint16_t const inst_data_size;
    bl_pin_def_t const *pin_defs;
    bl_funct_def_t const *funct_defs;
} bl_comp_def_t;


// returns pointer to matching node, or NULL if no match
// list does not have to be sorted
bl_inst_header_t *find_instance_by_name(char const *name);

// returns pointer to insertion point to maintain sorted list, 
// or NULL if there is already a node with the specified name
bl_inst_header_t **find_instance_insertion_point(char const *name);

// creates new instance of a component
bl_inst_header_t *bl_newinst(bl_comp_def_t *comp_def, char const *inst_name);

void list_all_instances(void);
void list_all_pins_in_instance(bl_inst_header_t *inst);

// component definition


// component instance


// pin definition


// pin instance w/metadata


// pin instance (functional only)


// signal 


/***********************************************************/

// functions




#endif // EMBLOCS_H