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

#include "emblocs_common.h"

/**************************************************************
 * Top-level EMBLOCS API functions used to build a system     *
 *                                                            *
 * These functions are implemented in emblocs_core.c          *
 *                                                            *
 **************************************************************/

/**************************************************************
 * A structure that defines a component.
 * The component creates the structure, an application merely
 * refers to it when creating a block (instance of component).
 * Its internals are unimportant and not declared here.
 */
struct bl_comp_def_s;

/**************************************************************
 * Create a block (a component instance), using a component
 * definition (typically in flash) and an optional personality.
 */
struct bl_block_meta_s *bl_block_new(char const *name, struct bl_comp_def_s const *comp_def, void const *personality);

/**************************************************************
 * Create a signal of the specified name and type
 */
struct bl_signal_meta_s *bl_signal_new(char const *name, bl_type_t type);

/**************************************************************
 * Create a thread to which functions can be added.
 * 'period_ns' will be passed to functions in the thread.
 * This API does not directly control the period of the thread;
 * see 'run_thread()' below.
 */
struct bl_thread_meta_s *bl_thread_new(char const *name, uint32_t period_ns, bl_nofp_t nofp);

/**************************************************************
 * Functions to find object metadata by name
 */
struct bl_block_meta_s *bl_block_find(char const *name);
struct bl_signal_meta_s *bl_signal_find(char const *name);
struct bl_thread_meta_s *bl_thread_find(char const *name);
struct bl_pin_meta_s *bl_pin_find_in_block(char const *name, struct bl_block_meta_s *blk);
struct bl_function_meta_s *bl_function_find_in_block(char const *name, struct bl_block_meta_s *blk);

/**************************************************************
 * Link the specified pin to the specified signal
 */
bool bl_pin_linkto_signal(struct bl_pin_meta_s const *pin, struct bl_signal_meta_s const *sig);

#ifdef BL_ENABLE_UNLINK
/**************************************************************
 * Disconnect the specified pin from any signal
 */
bool bl_pin_unlink(struct bl_pin_meta_s const *pin);
#endif

/**************************************************************
 * Set the specified signal to a value
 */
bool bl_signal_set(struct bl_signal_meta_s const *sig, bl_sig_data_t const *value);

/**************************************************************
 * Set the specified pin to a value
 */
bool bl_pin_set(struct bl_pin_meta_s const *pin, bl_sig_data_t const *value);

/**************************************************************
 * Add the specified function to the end of the specified thread
 */
bool bl_function_linkto_thread(struct bl_function_meta_s *funct, struct bl_thread_meta_s const *thread);

#ifdef BL_ENABLE_UNLINK
/**************************************************************
 * Disconnect the specified function from any thread
 */
bool bl_function_unlink(struct bl_function_meta_s *funct);
#endif

/**************************************************************
 * A structure that carries the realtime data for a thread.
 * An application passes it to bl_thread_run() to execute
 * the thread.
 * Its internals are unimportant and not declared here.
 */
struct bl_thread_data_s;

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
struct bl_thread_data_s *bl_thread_get_data(struct bl_thread_meta_s *thread);

/**************************************************************
 * Helper functions for viewing things in the metadata        *
 *                                                            *
 * These functions are defined in emblocs_show.c              *
 *                                                            *
 **************************************************************/

void bl_show_memory_status(void);
void bl_show_all_blocks(void);
void bl_show_all_signals(void);
void bl_show_all_threads(void);
void bl_show_block(struct bl_block_meta_s const *blk);
void bl_show_pin(struct bl_pin_meta_s const *pin);
void bl_show_function(struct bl_function_meta_s const *funct);
void bl_show_signal(struct bl_signal_meta_s const *sig);
void bl_show_thread(struct bl_thread_meta_s const *thread);

/**************************************************************
 * For convenience and code size reduction, a system can be   *
 * built by parsing compact representations of one or more    *
 * EMBLOCS commands.  Commands are represented by an array    *
 * of (mostly) string tokens, which can be stored in flash,   *
 * or generated by splitting up a command line.               *
 *                                                            *
 * These function are defined in emblocs_parse.c              *
 *                                                            *
 **************************************************************/
bool bl_parse_token(char const * const token);
bool bl_parse_array(char const * const tokens[], uint32_t count);
bool bl_parse_string(char const * const string);

/**************************************************************
 * Components must be linked into the flash image before they
 * can be used.  The application determines what components
 * to link by creating a NULL terminated constant array of
 * pointers to comp_def_s structures and initializing it with
 * the desired component definitions.  Only components in this
 * array can be instantiated by the 'block' command.
 */
extern struct bl_comp_def_s * const bl_comp_defs[];

#endif // EMBLOCS_API_H
