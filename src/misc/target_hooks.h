/********************************************************************
 *
 * target_hooks.h
 *
 * This file contains target and/or toolchain specific hooks for
 * generic needs like entering and exiting critical regions and
 * marking certain functions or data as speed critical.
 *
 * A real project must supply its own target_hooks.h, located
 * earlier in the include search path than this template, so that
 * it replaces this template with target specific code.
 *
 * While the macros in this file are not unique to the EMBLOCS
 * project, they use the EBL_ prefix to avoid possible collisions.
 *
 * The target-specific file must provide correct implementations
 * of every macro below.
 *
 * This template file serves two purposes:
 *   1)  List the macros that must be provided by a
 *       target-specific file.
 *   2)  Provide something to keep editors, code-completion, etc.,
 *       happy when not working on a specific target.
 *
 * This file can be used as a template for a real, target-specific
 * file.  Copy it to the project directory, replace these comments
 * with target-specific documentation, add the implementation code,
 * and remove the TARGET_BUILD guard below.
 *
 *******************************************************************/

#ifndef TARGET_HOOKS_H
#define TARGET_HOOKS_H

// prevent this template file from being used in a real build
#ifdef TARGET_BUILD
#error "Template version of 'target_hooks.h' is not suitable for a real build."
#endif

/********************************************************************
 *
 * Critical region protection
 *
 * MUST be a correct implementation in any real target header.
 * This stub is a no-op; would cause very nasty and non-reproducable
 * bugs if used in a real build.
 *
 * note that these macros are intended to wrap a block of code,
 * hence the { and } in their definitions.
 *
 */

#define EBL_CRITICAL_ENTER()  {
#define EBL_CRITICAL_EXIT()   }

/* Sample critical region macros
 *
 * The samples below show how these macros might be implemented on
 * a Cortex-M MCU that follows the CMSIS standard.  Note the { and }
 * brackets in each macro.  This implementation saves the current
 * interrupt state, then disables interrupts during the critical
 * region and restores the saved state after the critical region.
 * NOTE: this is not multi-core safe!
 *
 *      #include <stdint.h>
 *      #include <cmsis_compiler.h>
 *
 *      #define EBL_CRITICAL_ENTER()                \
 *          {                                       \
 *              uint32_t _irq = __get_PRIMASK();    \
 *              __disable_irq();
 *
 *      #define EBL_CRITICAL_EXIT()                 \
 *              __set_PRIMASK(_irq);                \
 *          }
 *
 * end of sample macros
 */


/********************************************************************
 *
 * Function/Data tags
 *
 * The following tags are used to tag functions or data objects
 * as either time critical or one-time init only use.
 *
 * On platforms where for example speed-critical code should be
 * placed in linker sections that will be copied to RAM, speed
 * critical data should be in closely-coupled memory (CCM), or
 * data/functions used only during init can run from slower
 * memory or perhaps be reclaimed after use, these tags are
 * used by the emblocs library to mark such items.
 *
 * Note that such tags must be applied to C names only; if you
 * want to tag an array of objects or a pointer to an object,
 * the array and/or pointer notation should be outside of the
 * tag macro:
 *
 * const uint32_t EBL_TAG_CONST_FAST(my_array)[3] = { 1, 2, 3 };
 * uint8_t * EBL_TAG_DATA_INIT(init_buf);
 *
 * The default definitions below are no-ops; they simply drop
 * the marking and return the basic name.  It is never necessary
 * to replace them, but on some targets, doing so will allow
 * for better optimization.
 *
 */

#define EBL_TAG_FUNCT_FAST(name)    name
#define EBL_TAG_FUNCT_INIT(name)    name

#define EBL_TAG_DATA_FAST(name)     name
#define EBL_TAG_DATA_INIT(name)     name

#define EBL_TAG_CONST_FAST(name)    name
#define EBL_TAG_CONST_INIT(name)    name

#endif // TARGET_HOOKS_H
