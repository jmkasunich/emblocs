/*********************************************
 *
 * RGB merge/split components:
 *
 * This module provides two components that can be
 * used to pack and unpack the red, green, and blue
 * components of an LED color into a single u32.
 *
 * The packed format always uses 11 bits for green,
 * 11 bits for blue, and 10 bits for red.  Unpacked
 * bit depths are configurable as part of the component
 * personality.
 * 
 * The personality consists of a rgb_config_t structure.
 * One element defines the bit depth of the individual
 * color components, and a second defines the number
 * of channels (up to 32) that are processed in parallel.
 * (Having one component instance process multiple 
 * signals allows for a shorter function list and less
 * overhead.)
 * 
 */

#ifndef BL_RGB_H
#define BL_RGB_H

typedef struct bl_rgb_config_s {
    uint8_t color_bits;
    uint8_t num_chan;
} bl_rgb_config_t;

#endif // BL_RGB_H
