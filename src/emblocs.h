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

/* some basic assumptions */
_Static_assert(sizeof(int) == 4, "ints must be 32 bits");
_Static_assert(sizeof(void *) == 4, "pointers must be 32 bits");


/*************************************************************
 * Realtime data and object metadata are stored in separate
 * memory pools, the RT pool and the META pool.  Each pool is
 * an array of uint32_t, and in the metadata, pool addresses 
 * are stored as array indexes in bitfields.  As an example,
 * if a pool is 4K bytes, indexes range from 0 to 1023, and
 * they can be stored in a 10 bit field.
 * 
 * If a pool size is intended to be a power of two, simply 
 * define the number of index bits, and the pool size will
 * be computed at compile time.  If the pool size is not a
 * power of two, define both the number of index bits and
 * the pool size in bytes.
 */

/* default index sizes if not defined elsewhere */
#ifndef BL_RT_INDEX_BITS
#define BL_RT_INDEX_BITS  9
#endif

#ifndef BL_META_INDEX_BITS
#define BL_META_INDEX_BITS  9
#endif

/* default to power of two sizes if not defined elsewhere */
#ifndef BL_RT_POOL_SIZE
#define BL_RT_POOL_SIZE (4<<(BL_RT_INDEX_BITS))
#endif

#ifndef BL_META_POOL_SIZE
#define BL_META_POOL_SIZE  (4<<(BL_META_INDEX_BITS))
#endif

/* These asserts verify that the specified number of bits can 
   be used to address the specified pool size. */
_Static_assert((4<<(BL_RT_INDEX_BITS)) >= (BL_RT_POOL_SIZE), "not enough RT index bits");
_Static_assert((4<<(BL_META_INDEX_BITS)) >= (BL_META_POOL_SIZE), "not enough meta index bits");

/* A couple of other constants based on pool size */
#define BL_RT_INDEX_MASK ((1<<(BL_RT_INDEX_BITS))-1)
#define BL_META_INDEX_MASK ((1<<(BL_META_INDEX_BITS))-1)


/*************************************************************
 * Each instance of a component has "instance data" which is
 * in the RT memory pool.  The instance data size is specified
 * in bytes, and the size is stored in a bitfield.
 */

#ifndef BL_INST_DATA_SIZE_BITS
#define BL_INST_DATA_SIZE_BITS  10
#endif

#define BL_INST_DATA_MAX_SIZE (1<<(BL_INST_DATA_SIZE_BITS))
#define BL_INST_DATA_SIZE_MASK ((BL_INST_DATA_MAX_SIZE)-1)


/*************************************************************
 * Data types for pins and signals.  Stored in bitfields, so
 * we need to specify the bitfield length as well as the enum.
 */

typedef enum {
	BL_TYPE_FLOAT    = 0,
	BL_TYPE_BIT      = 1,
	BL_TYPE_S32      = 2,
	BL_TYPE_U32      = 3
} bl_type_t;

#define BL_TYPE_BITS 2


/*************************************************************
 * Data directions for pins.  Stored in bitfields, so we need
 * to specify the bitfield length as well as the enum.
 */

typedef enum {
	BL_DIR_IN        = 1,
	BL_DIR_OUT       = 2,
	BL_DIR_IO        = 3,
} bl_dir_t;

#define BL_DIR_BITS  2


/*************************************************************
 * Data structure that describes a component instance.
 * These structures live in the metadata pool, but point to
 * instance data in the realtime pool.
 */

typedef struct bl_inst_meta_s {
    struct bl_inst_meta_s *next;
    uint32_t data_index  : BL_RT_INDEX_BITS;
    uint32_t data_size   : BL_INST_DATA_SIZE_BITS;
    char const *name;
    struct bl_pin_meta_s *pin_list;
} bl_inst_meta_t;

/* Verify that bitfields fit in one uint32_t */
_Static_assert((BL_RT_INDEX_BITS+BL_INST_DATA_SIZE_BITS) <= 32, "instance bitfields too big");


/*************************************************************
 * Data structure that describes a pin.  Each instance has a
 * list of pins.  These structures live in the metadata pool,
 * but point to data in the realtime pool.
 */

typedef struct bl_pin_meta_s {
    struct bl_pin_meta_s *next;
    uint32_t ptr_index    : BL_RT_INDEX_BITS;
    uint32_t dummy_index  : BL_RT_INDEX_BITS;
    uint32_t data_type    : BL_TYPE_BITS;
    uint32_t pin_dir      : BL_DIR_BITS;
    char const *name;
} bl_pin_meta_t;

/* Verify that bitfields fit in one uint32_t */
_Static_assert((BL_RT_INDEX_BITS*2+BL_TYPE_BITS+BL_DIR_BITS) <= 32, "pin bitfields too big");


/*************************************************************
 * Data structure that defines a pin.  These are optional, but
 * an array of them in flash can be used to drive creation of
 * the actual bl_pin_meta_t structures in RAM.  The data offset
 * is in bytes from the beginning of the instance data.
 */

typedef struct bl_pin_def_s {
    char const *name;
    uint32_t data_type    : BL_TYPE_BITS;
    uint32_t pin_dir      : BL_DIR_BITS;
    uint32_t data_offset  : BL_INST_DATA_SIZE_BITS;
} bl_pin_def_t;

/* Verify that bitfields fit in one uint32_t */
_Static_assert((BL_INST_DATA_SIZE_BITS+BL_TYPE_BITS+BL_DIR_BITS) <= 32, "pin_def bitfields too big");


/*************************************************************
 * Data structure that describes a signal.  There is one list
 * of signals which lives in the metadata pool, but point to
 * data in the realtime pool.
 */

typedef struct bl_sig_meta_s {
    struct bl_sig_meta_s *next;
    uint32_t data_index   : BL_RT_INDEX_BITS;
    uint32_t data_type    : BL_TYPE_BITS;
    char const *sig_name;
} bl_sig_meta_t;

/* Verify that bitfields fit in one uint32_t */
_Static_assert((BL_RT_INDEX_BITS+BL_TYPE_BITS) <= 32, "sig bitfields too big");


/****************************************************************
 * the four pin/signal types
 */

typedef float bl_float_t;
typedef bool bl_bit_t;
typedef int32_t bl_s32_t;
typedef uint32_t bl_u32_t;

/* pins are pointers to their respective data types */

typedef bl_bit_t *bl_pin_bit_t;
typedef bl_float_t *bl_pin_float_t;
typedef bl_s32_t *bl_pin_s32_t;
typedef bl_u32_t *bl_pin_u32_t;

/* "generic" data and pins; implemented as a union of the four types */
typedef union bl_sig_data_u {
    bl_bit_t b;
    bl_float_t f;
    bl_s32_t s;
    bl_u32_t u;
} bl_sig_data_t;

typedef union bl_pin_u {
    bl_pin_bit_t b;
    bl_pin_float_t f;
    bl_pin_s32_t s;
    bl_pin_u32_t u;
} bl_pin_t;



/**********************************************************************************
 * allocates a new bl_inst_meta_t struct in meta RAM
 * allocates 'data_size' bytes in RT ram
 * fills in all fields in the meta struct
 * adds the meta struct to the global instance list
 */
bl_inst_meta_t *bl_inst_new(char const *name, uint32_t data_size);

/**********************************************************************************
 * allocates a new bl_pin_meta_t struct in meta RAM 
 * allocates a dummy signal in RT ram
 * fills in all fields in the meta struct
 * links the pin to the dummy signal
 * adds the meta struct to 'inst' pin list
 */
bl_pin_meta_t *bl_pin_new(bl_inst_meta_t *inst, char const *name, bl_type_t type, bl_dir_t dir, uint32_t data_offset);

/**********************************************************************************
 * calls bl_pin_new() using info from pin_def structure
 */
bl_pin_meta_t *bl_pin_new_from_def(bl_inst_meta_t *inst, bl_pin_def_t *def);

/**********************************************************************************
 * allocates a new sig_meta_t struct in meta RAM
 * allocates signal data in RT ram
 * fills in all fields in the meta struct
 * adds the meta struct to the signal list
 */
bl_sig_meta_t *bl_sig_new(char const *name, bl_type_t type);




int bl_link_pin_sig(char const *inst_name, char const *pin_name, char const *sig_name );
int bl_unlink_pin(char const *inst_name, char const *pin_name);

void show_all_instances(void);  // also shows pins and linkages
void show_all_signals(void);

//void bl_inst_new_from_comp_def(bl_comp_def_t *comp, char const *name);




#if 0

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

#endif



#if 0  // OLD STUFF

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
    struct bl_sig_meta_s *next;
    char const *name;
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
void list_signal_pins(bl_sig_meta_t *sig);

/****************************************************************
 * pin data structures & functions
 */

/*   create a pin */
bl_pin_meta_t *bl_newpin(bl_type_t type, bl_dir_t dir, char const * inst_name, char const * pin_name);






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

typedef union bl_pin_u {
    bl_pin_bit_t b;
    bl_pin_float_t f;
    bl_pin_s32_t s;
    bl_pin_u32_t u;
} bl_pin_t;

typedef struct bl_pin_meta_s {
    struct bl_pin_meta_s *next;
    bl_pin_t *pin;
    char *pin_name;
    char *inst_name;
} bl_pin_meta_t;




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

/*   list the signal connected to a pin */
void list_pin_signal(void *sig_addr);



/* arrays that the application must supply to define the system */

typedef struct inst_def_s {
    char *name;
    bl_comp_def_t *comp_def;
} bl_inst_def_t;

typedef struct link_def_s {
    char *sig_name;
    char *inst_name;
    char *pin_name;
} bl_link_def_t;

extern bl_inst_def_t bl_instances[];

extern char *bl_signals_float[];
extern char *bl_signals_bit[];
extern char *bl_signals_s32[];
extern char *bl_signals_u32[];

extern bl_link_def_t bl_links[];

/* function that reads the above and builds the system */
void emblocs_init(void);

#endif  // OLD STUFF


#endif // EMBLOCS_H