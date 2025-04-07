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

/* Uncomment this define to print error messages */
#define BL_PRINT_ERRORS

/* Uncomment this define to halt on errors.
 * This can save code size since calling functions 
 * don't need to check return values.
 */
//#define BL_ERROR_HALT

/* Uncomment this define to make 'show' commands print
 * more details such as memory addresses, indexes, etc.
 */
//#define BL_SHOW_VERBOSE

/* Uncomment this define to enable pin and function
 * 'unlink' commands.
 * Most systems don't need 'unlink', they should
 * just configure things correctly in the first
 * place.  Leaving this commented will save code
 * space.
 */
#define BL_ENABLE_UNLINK

/* Uncomment this define to enable pin and function
 * 'linkto' commands to unlink previously linked
 * objects.  This also defines BL_ENABLE_UNLINK.
 * Most systems don't need this, they should just
 * configure things correctly in the first place.
 * Leaving this commented will save a little bit
 * of code space.
 */
#define BL_ENABLE_IMPLICIT_UNLINK

/* Uncomment this define to enable checks for NULL
 * pointers passed into API functions.  Leaving
 * it commented will save code space.
 */
#define BL_NULL_POINTER_CHECKS

/* size of the memory pool for realtime data */
#define BL_RT_POOL_SIZE     (2048)

/* size of the memory pool for object metadata */
#define BL_META_POOL_SIZE   (4096)

/* maximum length of object names */
#define BL_MAX_NAME_LEN     (40)

#endif // EMBLOCS_CONFIG_H
