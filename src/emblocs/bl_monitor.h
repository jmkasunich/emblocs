/***************************************************************
 *
 * bl_monitor.h - EMBLOCS runtime monitor API
 *
 * Provides bl_monitor_init() and bl_monitor_poll() for
 * integrating the EMBLOCS runtime monitor into a target
 * application.  The application calls bl_monitor_init()
 * once at startup and bl_monitor_poll() periodically from
 * background (non-interrupt) context.
 *
 * The monitor communicates with the PC-side tool over the
 * binary packet channel provided by serial.h, using packet
 * address BL_MONITOR_PKT_ADDR.  ASCII traffic on the same
 * UART is unaffected and may be used freely for debugging.
 *
 **************************************************************/

#ifndef BL_MONITOR_H
#define BL_MONITOR_H

/***************************************************************
 * bl_monitor_init()
 *
 * Initializes the monitor.  Must be called once at startup,
 * before the first call to bl_monitor_poll().
 *
 **************************************************************/
void bl_monitor_init(void);

/***************************************************************
 * bl_monitor_poll()
 *
 * Checks for a received infrastructure packet and processes
 * it if one is available.  Must be called from background
 * (non-interrupt) context.  Returns immediately if no packet
 * is waiting.  Intended to be called from the application's
 * main loop between real-time thread invocations.
 *
 **************************************************************/
void bl_monitor_poll(void);

#endif // BL_MONITOR_H
