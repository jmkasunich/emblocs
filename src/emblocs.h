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


/****************************************************************
 * sorted list data structures & functions
 */

typedef struct bl_list_entry_s {
    char const * name;
    struct bl_list_entry_s *next;
} bl_list_entry_t;

bl_list_entry_t *find_name_in_list(char const *name, bl_list_entry_t *list);
bl_list_entry_t **find_insertion_point(char const *name, bl_list_entry_t **list);

/****************************************************************
 * the four pin/signal types
 */

typedef float bl_float_t;
typedef bool bl_bit_t;
typedef int32_t bl_s32_t;
typedef uint32_t bl_u32_t;

/* a union that can hold any of the four */
typedef union bl_sig_data_u {
    bl_bit_t b;
    bl_float_t f;
    bl_s32_t s;
    bl_u32_t u;
} bl_sig_data_t;

typedef enum bl_type_e {
	BL_TYPE_FLOAT    = 0x00,
	BL_TYPE_BIT      = 0x01,
	BL_TYPE_S32      = 0x02,
	BL_TYPE_U32      = 0x03
} bl_type_t;

#define BL_TYPE_MASK (0x03)

typedef enum bl_dir_e {
	BL_DIR_IN        = 0x04,
	BL_DIR_OUT       = 0x08,
	BL_DIR_IO        = 0x0C,
} bl_dir_t;

#define BL_DIR_MASK (0x0C)

/****************************************************************
 * named signal data structures & functions
 */

/* dpwt = data pointer with type
 * type takes two bits, data pointers are always 4-byte aligned
 * so use the low 2 bits of the pointer to store the type and
 * the rest to store the pointer; with macros to manage the fields
 */

_Static_assert(sizeof(uint32_t) == sizeof(void *));

typedef uint32_t bl_dpwt_t;
#define GET_TYPE(dpwt)          ((dpwt) & BL_TYPE_MASK)
#define GET_DPTR(dpwt)          ((void *)((dpwt) & ~BL_TYPE_MASK))
#define MAKE_DPWT(ptr,type)     ((uint32_t)(ptr) | ((type) & BL_TYPE_MASK))

/* structure to hold signal metadata */
typedef struct bl_sig_meta_s {
    bl_list_entry_t header;
    bl_dpwt_t dpwt;
} bl_sig_meta_t;

/* system building functions */

/*   create a signal */
bl_sig_meta_t *bl_newsig(bl_type_t type, char const * sig_name);

/*   link a pin to a signal */
void bl_linksp(char const *sig_name, char const *inst_name, char const *pin_name);

/* helpers for system building functions */

/*   find a signal by name */

/* listing/observation functions */

/*   list all signals */
void list_all_signals(void);

/*   list pins connected to a signal */



/****************************************************************
 * component and instance structures and functions
 */

#define ARRAYCOUNT(foo)  (sizeof(foo)/sizeof((foo)[0]))
#define BL_OFFSET(type, member)  ((bl_offset_t)(offsetof(type,member)))
typedef uint16_t bl_offset_t;

/***********************************************
 * pin data structures
 */

typedef struct bl_pin_bit_s {
    bl_bit_t *pin;
    bl_bit_t dummy;
} bl_pin_bit_t;

typedef struct bl_pin_float_s {
    bl_float_t *pin;
    bl_float_t dummy;
} bl_pin_float_t;

typedef struct bl_pin_s32_s {
    bl_s32_t *pin;
    bl_s32_t dummy;
} bl_pin_s32_t;

typedef struct bl_pin_u32_s {
    bl_u32_t *pin;
    bl_u32_t dummy;
} bl_pin_u32_t;

typedef struct bl_inst_meta_s {
    bl_list_entry_t header;
    struct bl_comp_def_s *comp_def;
    void *inst_data;
} bl_inst_meta_t;

typedef struct bl_pin_def_s {
    char const * const name;
    bl_type_t const type;
    bl_dir_t const dir;
    bl_offset_t const offset;
} bl_pin_def_t;

typedef struct bl_funct_def_s {
    char const * const name;
    void (*fp) (void *);
} bl_funct_def_t;

typedef struct bl_comp_def_s {
    char const * const name;
    uint8_t const pin_count;
    uint8_t const funct_count;
    uint16_t const inst_data_size;
    bl_pin_def_t const *pin_defs;
    bl_funct_def_t const *funct_defs;
} bl_comp_def_t;

/* system building functions */

/*   create an instance of a component */
bl_inst_meta_t *bl_newinst(bl_comp_def_t *comp_def, char const *inst_name);

/* helpers for system building functions */

/*   find an instance by name */

/*   find a pin by name */

/* listing/observation functions */

/*   list all instances */
void list_all_instances(void);

/*   list all pins in an instance */
void list_all_pins_in_instance(bl_inst_meta_t *inst);


#endif // EMBLOCS_H