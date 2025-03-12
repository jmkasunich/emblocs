/***************************************************************
 * 
 * emblocs_api.h - header for EMBLOCS applications
 * 
 * Embedded Block-Oriented Control System
 * 
 * 
 * 
 **************************************************************/

#ifndef EMBLOCS_API_H
#define EMBLOCS_API_H

#include "emblocs_core.h"



/**************************************************************
 * A structure that defines a component.
 * The component creates the structure, an application merely
 * refers to it when creating an instance of the component.
 * Its internals are unimportant and not declared here.
 */
struct bl_comp_def_s;

/**************************************************************
 * A structure that defines a thread.
 * An application passes it to bl_thread_update() to execute
 * the thread.
 * Its internals are unimportant and not declared here.
 */
struct bl_thread_data_s;

/**************************************************************
 * Top-level EMBLOCS API functions used to build a system     *
 *                                                            *
 * These functions are implemented in emblocs_core.c          *
 *                                                            *
 **************************************************************/

/**************************************************************
 * Create an instance of a component, using a component 
 * definition (typically in flash) and an optional personality.
 */
bl_retval_t bl_instance_new(char const *name, struct bl_comp_def_s const *comp_def, void const *personality);

/**************************************************************
 * Create a signal of the specified name and type
 */
bl_retval_t bl_signal_new(char const *name, bl_type_t type);

/**************************************************************
 * Link the specified pin to the specified signal
 */
bl_retval_t bl_link_pin_to_signal_by_names(char const *inst_name, char const *pin_name, char const *sig_name );

/**************************************************************
 * Disconnect the specified pin from any signal
 */
bl_retval_t bl_unlink_pin_by_name(char const *inst_name, char const *pin_name);

/**************************************************************
 * Set the specified signal to a value
 */
bl_retval_t bl_set_sig_by_name(char const *sig_name, bl_sig_data_t const *value);

/**************************************************************
 * Set the specified pin to a value
 */
bl_retval_t bl_set_pin_by_name(char const *inst_name, char const *pin_name, bl_sig_data_t const *value);

/**************************************************************
 * Create a thread to which functions can be added.
 * 'period_ns' will be passed to functions in the thread.
 * This API does not directly control the period of the thread;
 * see 'run_thread()' below.
 */
bl_retval_t bl_thread_new(char const *name, uint32_t period_ns, bl_nofp_t nofp);

/**************************************************************
 * Add the specified function to the end of the specified thread
 */
bl_retval_t bl_add_funct_to_thread_by_names(char const *inst_name, char const *funct_name, char const *thread_name);

/**************************************************************
 * Runs a thread once by calling all of the functions that have
 * been added to the thread.  Typically bl_thread_run() will be
 * called from an ISR or an RTOS thread.  If 'period_ns' is 
 * non-zero, it will be passed to the thread functions; if zero,
 * the 'thread_ns' value from thread creation will be passed 
 * instead.
 */
void bl_thread_run(struct bl_thread_data_s const *thread, uint32_t period_ns);

/**************************************************************
 * Helper function to get the address of thread data; this is
 * passed to bl_thread_run() to run the thread
 */  
struct bl_thread_data_s *bl_find_thread_data_by_name(char const *name);

/**************************************************************
 * Helper functions for viewing things in the metadata        *
 *                                                            *
 * These functions are defined in emblocs_show.c              *
 *                                                            *
 **************************************************************/

void bl_show_memory_status(void);
void bl_show_all_instances(void);
void bl_show_all_signals(void);
void bl_show_all_threads(void);
void bl_show_instance_by_name(char const *name);
void bl_show_signal_by_name(char const *name);
void bl_show_thread_by_name(char const *name);

/**************************************************************
 * For convenience, a system can be built by using compact    *
 * representations of multiple EMBLOCS commands.  These       *
 * structures and functions support that.                     *
 *                                                            *
 * They functions are defined in emblocs_init.c               *
 *                                                            *
 **************************************************************/

/**************************************************************
 * A NULL terminated array of "instance definitions" (usually
 * in FLASH) can be passed to bl_init_instances() to create
 * all of the component instances needed for a system.
 */

typedef struct inst_def_s {
    char const *name;
    struct bl_comp_def_s const *comp_def;
    void const *personality;
} bl_inst_def_t;

bl_retval_t bl_init_instances(bl_inst_def_t const instances[]);

/**************************************************************
 * A NULL terminated array of strings can be passed to 
 * bl_init_nets() to create all of the signals needed for a
 * system, and connect the signals to the appropriate pins.
 * The array starts with one of the type strings "FLOAT",
 * "BIT", "S32" or "U32", then a net name, followed by zero
 * or more instance name/pin name pairs.  Each pin name is
 * followed by either another instance/pin name (to add to 
 * the same net), or by a type string (to start a new net),
 * or by NULL to end the array.
 */

bl_retval_t bl_init_nets(char const * const nets[]);

/**************************************************************
 * A NULL terminated array of "setsig definitions" (usually
 * in FLASH) can be passed to bl_init_setsigs() to set the
 * values of all non-zero signals in a system.
 */

typedef struct bl_setsig_def_s {
    char const *name;
    bl_sig_data_t value;
} bl_setsig_def_t;

bl_retval_t bl_init_setsigs(bl_setsig_def_t const setsigs[]);

/**************************************************************
 * A NULL terminated array of "setpin definitions" (usually
 * in FLASH) can be passed to bl_init_setpins() to set the
 * values of all non-zero unconnected pins in a system.
 */

typedef struct bl_setpin_def_s {
    char const *inst_name;
    char const *pin_name;
    bl_sig_data_t value;
} bl_setpin_def_t;

bl_retval_t bl_init_setpins(bl_setpin_def_t const setpins[]);

/**************************************************************
 * A NULL terminated array of strings can be passed to 
 * bl_init_threads() to create all of the threads needed for
 * a system.  The array starts with either "HAS_FP" or "NO_FP"
 * to mark the beginning of a thread and determine whether that
 * thread should allow functions that need floating point.
 * The next string is a number (in ASCII) that is period_ns
 * for the new thread, followed by the name of the thread.
 * After the thread name, there must be one or more "instance
 * name" / "function name" pairs to define the functions called
 * by the thread, in calling order.  An instance name of either
 * "HAS_FP" or "NO_FP" begins another thread, while NULL ends
 * the array.
 */

bl_retval_t bl_init_threads(char const * const threads[]);


#endif // EMBLOCS_API_H
