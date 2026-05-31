/*********************************************
 *
 * Signal watching component:
 *
 * This component exports pins which can be connected to
 * signals that you want to observe.  When its update()
 * function runs, the value of each pin is output to the
 * console, using a printf format string that is part of
 * the personality.
 *
 * The personality is an array of watch_pin_config_t
 * structures.  The end of the array is marked by an
 * entry with NULL in the 'name' and 'format' fields.
 *
 * A single 'watch' block is limited to 9 pins,
 * but you can have as many blocks as you want.
 *
 */

#ifndef WATCH_H
#define WATCH_H

typedef struct watch_pin_config_s {
    bl_type_t type;
    char const *name;
    char const *format;
} watch_pin_config_t;

#endif // WATCH_H
