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

#pragma GCC diagnostic ignored "-Wsign-conversion"
#include "stm32g4xx.h"
#pragma GCC diagnostic pop
#include "platform.h"

/* some of the functions declared in platform.h are implemented here as macros */

#define cons_tx_ready()             ((USART2)->ISR & (USART_ISR_TXE_Msk))
#define cons_tx(c)                  ((USART2)->TDR = (c))
#define cons_tx_idle()              ((USART2)->ISR & (USART_ISR_TC_Msk))
#define cons_rx_ready()             ((USART2)->ISR & (USART_ISR_RXNE_Msk))
#define cons_rx()                   ((char)((USART2)->RDR))

#define tsc_read()                  ((TIM2)->CNT)

#endif // PLATFORM_G431_H