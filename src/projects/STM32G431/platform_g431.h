/***************************************************************
 * 
 * platform-g431.h - platform specific code for STM32G431
 * 
 * 
 * 
 * *************************************************************/

#ifndef PLATFORM_G431_H
#define PLATFORM_G431_H

#ifndef STM32G431xx
#define STM32G431xx
#endif

#include <stdint.h>
#ifndef uint
#define uint unsigned int
#endif

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wsign-conversion"
#include "stm32g4xx.h"
#pragma GCC diagnostic pop
#include "platform.h"

// uncomment to avoid using interrupts for console I/O
//#define CONSOLE_POLLED

// GPIO macros

#define PB6_OUT(v)   (GPIOB->BSRR = v ? (1<<6)  : (1<<(6+16)));
#define PB7_OUT(v)   (GPIOB->BSRR = v ? (1<<7)  : (1<<(7+16)));
#define PB8_OUT(v)   (GPIOB->BSRR = v ? (1<<8)  : (1<<(8+16)));
#define PA15_OUT(v)  (GPIOA->BSRR = v ? (1<<15) : (1<<(15+16)));

/* some of the functions declared in platform.h are implemented here as macros */

#define tsc_read()                  ((TIM2)->CNT)

#endif // PLATFORM_G431_H