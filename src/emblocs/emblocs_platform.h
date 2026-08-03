/********************************************************************
 *
 * emblocs_platform.h
 *
 * This file contains target and/or toolchain specific code for
 * emblocs specific needs like the monitor UART port.
 *
 * A real project must supply its own emblocs_platform.h, located
 * earlier in the include search path than this template, so that
 * it replaces this template with target specific code.
 *
 * The target-specific file must provide correct implementations
 * of every macro and/or function prototype below.
 *
 * This template file serves two purposes:
 *   1)  List the macros and functions that must be provided
 *       by a target-specific file.
 *   2)  Provide something to keep editors, code-completion, etc.,
 *       happy when not working on a specific target.
 *
 * This file can be used as a template for a real, target-specific
 * file.  Copy it to the project directory, replace these comments
 * with target-specific documentation, add the implementation code,
 * and remove the TARGET_BUILD guard below.
 *
 **************************************************************/

#ifndef EMBLOCS_PLATFORM_H
#define EMBLOCS_PLATFORM_H

// prevent this template file from being used in a real build
#ifdef TARGET_BUILD
#error "Template version of 'emblocs_platform.h' is not suitable for a real build."
#endif


#endif // EMBLOCS_PLATFORM_H
