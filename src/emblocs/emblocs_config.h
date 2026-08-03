/***************************************************************
 *
 * emblocs_config.h
 *
 * This file contains #defines that are used to configure the
 * emblocs system for a particular project.
 *
 * A real project must supply its own emblocs_config.h, located
 * earlier in the include search path than this template, so that
 * it replaces this template with target specific code.
 *
 * The target-specific file must address every configuration
 * macro listed below.
 *
 * This template file serves two purposes:
 *   1)  List the macros that must be provided by a
 *       target-specific file.
 *   2)  Provide something to keep editors, code-completion, etc.,
 *       happy when not working on a specific target.
 *
 * This file can be used as a template for a real, target-specific
 * file.  Copy it to the project directory, replace these comments
 * with target-specific documentation, adjust the config values
 * to suit the project, and remove the TARGET_BUILD guard below.
 *
 **************************************************************/

#ifndef EMBLOCS_CONFIG_H
#define EMBLOCS_CONFIG_H

// prevent this template file from being used in a real build
#ifdef TARGET_BUILD
#error "Template version of 'emblocs_config.h' is not suitable for a real build."
#endif


/********************************************************
 * CONFIGURATION STARTS HERE
 */

/* Uncomment this define to print messages on errors.
 * Printing adds non-trivial code size.
 */
#define EBL_PRINT_ERRORS

/* Uncomment this define to halt on errors.
 * This can save code size since calling functions
 * don't need to check return values.
 */
//#define EBL_ERROR_HALT

/* Uncomment this define to enable checks for NULL
 * pointers passed into API functions.  Leaving
 * it commented will save code space.
 */
#define EBL_NULL_POINTER_CHECKS

#endif // EMBLOCS_CONFIG_H
