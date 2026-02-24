/***************************************************************
 * 
 * serial_g431.c - serial port driver for STM32G431
 * 
 * 
 * *************************************************************/

#ifndef STM32G431xx
#define STM32G431xx
#endif

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wsign-conversion"
#include "stm32g4xx.h"
#pragma GCC diagnostic pop

#include "serial.h"

// inline hardware access macros
#define uart_rx_char_avail()    ((USART2)->ISR & (USART_ISR_RXNE_RXFNE_Msk))
#define uart_rx_get_char()      ((char)((USART2)->RDR))
#define uart_tx_ready()         ((USART2)->ISR & (USART_ISR_TXE_TXFNF_Msk))
#define uart_tx_idle()          ((USART2)->ISR & (USART_ISR_TC_Msk))
#define uart_tx_send_char(c)    ((USART2)->TDR) = (c)
#define uart_tx_int_ena()       (USART2)->CR3 |= (USART_CR3_TXFTIE)
#define uart_tx_int_dis()       (USART2)->CR3 &= ~(USART_CR3_TXFTIE)

// FIXME - should initialization code be here?


void USART2_IRQHandler(void)
{
    char c;

    // check for UART received data
    while ( uart_rx_char_avail() ) {
        c = uart_rx_get_char();
        ser_put_rx_byte(c);
    }
    // check for UART ready to send data
    while ( uart_tx_ready() ) {
        c = ser_get_tx_byte();
        if ( c <= 0xFF ) {
            uart_tx_send_char(c);
        } else {
            uart_tx_int_dis();
        }
    }
}

void ser_start_tx(void)
{
    uart_tx_int_ena();
}

