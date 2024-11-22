/***************************************************************
 * 
 * platform.h - generic headers for platform specific code
 * 
 * This file contains headers for platform specific code
 *
 * You will want to create a C file "platform-foo.c" that
 * implements the functions below for your platform, then 
 * include this file in your application and link against
 * your C file.
 * You may also want to create a header file "platform-foo.h"
 * that contains inline or macro versions of some of these
 * functions, and that includes any device specific headers
 * as well as including this file.
 * 
 * 
 * *************************************************************/

#ifndef PLATFORM_H
#define PLATFORM_H

#include <stdint.h>
#include <stddef.h>

/* platform_init() performs core initialization
 *
 *    initializes clock subsystem, sets all clocks to full speed
 *    initializes console serial port
 *    initializes time-stamp counter
 */

void platform_init(void);

/* console serial port
 *
 * The 'console' is just a UART, but on an MCU with multiple UARTs, it is the 
 * one that is used for debugging, etc.  Other UART functions likely require 
 * passing a handle or something to identify which UART; the console functions
 * hard-code the UART handle for convenience and speed.
 */

/* returns non-zero if transmitter can accept a character */
int cons_tx_ready(void);

/* transmits a character without waiting; data can be lost if transmitter is not ready */
void cons_tx(char c);

/* waits until transmitter is ready, then transmits character */
void cons_tx_wait(char c);

/* returns non-zero if transmitter is idle (all characters sent) */
int cons_tx_idle(void);

/* returns non-zero if reciever has a character available */
int cons_rx_ready(void);

/* gets a character without waiting, may return garbage if reciever is not ready */
int cons_rx(void);

/* waits until receiver is ready, then gets character */
int cons_rx_wait(void);

/* time stamp counter
 *
 * used for high-resolution time measurements
 * counts at the MCU clock rate, or as close as possible
 * 
 */

/* tsc_read() captures the time stamp counter value */
uint32_t tsc_read(void);

/* tsc_to_usec() converts time stamp counts to microseconds */
uint32_t tsc_to_usec(uint32_t tsc_counts);

#endif // PLATFORM_H
