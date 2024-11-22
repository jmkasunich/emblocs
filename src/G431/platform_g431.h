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

#include "stm32g4xx.h"
#include "platform.h"

/* some of the functions declared in platform.h are implemented here as macros */

#define cons_tx_ready()             ((USART2)->ISR & (USART_ISR_TXE_Msk))
#define cons_tx(c)                  ((USART2)->TDR = (c))

#define tsc_read()                  ((TIM2)->CNT)

#endif // PLATFORM_G431_H