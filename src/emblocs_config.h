/***************************************************************
 *
 * emblocs_config.h - header for EMBLOCS configuration
 *
 * Embedded Block-Oriented Control System
 *
 *
 *
 **************************************************************/

#ifndef EMBLOCS_CONFIG_H
#define EMBLOCS_CONFIG_H

/* uncomment this define to print error messages */
#define BL_ERROR_VERBOSE

/* uncomment this define to halt on errors */
//#define BL_ERROR_HALT

/* uncomment this define to make 'show' commands print more
 * details such as memory addresses, indexes, etc. */
//#define BL_SHOW_VERBOSE

/* uncomment this define to enable pin and function
 * 'unlink' commands */
#define BL_ENABLE_UNLINK

/* uncomment this define to enable pin and function
 * 'linkto' commands to unlink previously linked
 * objects; this also defines BL_ENABLE_UNLINK */
#define BL_ENABLE_IMPLICIT_UNLINK

#ifdef BL_ENABLE_IMPLICIT_UNLINK
#ifndef BL_ENABLE_UNLINK
#define BL_ENABLE_UNLINK
#endif
#endif

/* size of the memory pool for realtime data */
#define BL_RT_POOL_SIZE     (2048)

/* size of the memory pool for object metadata */
#define BL_META_POOL_SIZE   (4096)

#endif // EMBLOCS_CONFIG_H
