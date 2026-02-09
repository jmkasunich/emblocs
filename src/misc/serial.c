/***************************************************************
 * 
 * serial.c - serial port functions
 * 
 * see serial.h for API details
 * 
 * *************************************************************/

// FIXME - need a better way to include target-specific stuff
#ifndef STM32G431xx
#define STM32G431xx
#endif

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wsign-conversion"
#include "stm32g4xx.h"
#pragma GCC diagnostic pop

#include "serial.h"

#define SERIAL_ASCII_TX_BUF_LEN  1000
#define SERIAL_ASCII_RX_BUF_LEN  100

/*  buffer notes
 *
 * 'in' always points to an empty location
 * 'out' points to a filled location, unless 'out' == 'in',
 * in which case the whole buffer is empty.  So empty is
 * easy to detect, full is a bit more complicated.
 * Full is when (in+1) == out  (must do wrap on in+1)
 *           or in == (out-1)  (must to wrap on out-1)
 *
 * This buffer implementation does not disable interrupts
 * and is thread-safe for concurrent reading and writing.
 * But the individual read and write functions are not
 * re-entrant.  Should have only one reader and only one
 * writer.
*/

static volatile char ascii_tx_buf[SERIAL_ASCII_TX_BUF_LEN];
static volatile uint ascii_tx_index_in = 0;
static volatile uint ascii_tx_index_out = 0;

static volatile char ascii_rx_buf[SERIAL_ASCII_RX_BUF_LEN];
static volatile uint ascii_rx_index_in = 0;
static volatile uint ascii_rx_index_out = 0;

static enum {
    RX_MODE_ASCII,
    RX_MODE_PACKET
} rx_mode = RX_MODE_ASCII;


void USART2_IRQHandler(void)
{
    uint in, out;
    char c;

    // check for UART received data
    if ( uart_rx_char_avail() ) {
        in = ascii_rx_index_in;
        out = ascii_rx_index_out;
        // buffer full if in == (out-1)
        // decrement 'out' with wrap
        out = ( out != 0 ) ? (out-1) : (SERIAL_ASCII_RX_BUF_LEN-1);
        do {
            // get the data
            c = uart_rx_get_char();
            if ( in != out ) {
                // space available in buffer, store the character
                ascii_rx_buf[in] = c;
                // increment 'in' with wrap
                in = ( in < (SERIAL_ASCII_RX_BUF_LEN-1) ) ? (in+1) : 0;
            }
        } while ( uart_rx_char_avail() );
        ascii_rx_index_in = in;
    }
    // check for UART ready to send data
    if ( uart_tx_ready() ) {
        in = ascii_tx_index_in;
        out = ascii_tx_index_out;
        do {
            if ( in == out ) {
                // no data in buffer, nothing else to do
                // disable TX FIFO threshold interrupt
                uart_tx_int_dis();
                // exit do {} while (); loop
                break;
            }
            // data in buffer, send to UART
            c = ascii_tx_buf[out];
            uart_tx_send_char(c);
            // increment 'out' with wrap
            out = ( out < (SERIAL_ASCII_TX_BUF_LEN-1) ) ? (out+1) : 0;
        } while ( uart_tx_ready() );
        ascii_tx_index_out = out;
    }
}


/* returns non-zero if transmitter can accept a character */
int cons_tx_ready(void)
{
    uint in = ascii_tx_index_in;
    // increment 'in' with wrap
    in = ( in < (SERIAL_ASCII_TX_BUF_LEN-1) ) ? (in+1) : 0;
    return ( in != ascii_tx_index_out );
}

/* transmits a character without waiting; data can be lost if transmitter is not ready */
void cons_tx(char c)
{
    uint in = ascii_tx_index_in;
    ascii_tx_buf[in] = c;
    // increment 'in' with wrap
    in = ( in < (SERIAL_ASCII_TX_BUF_LEN-1) ) ? (in+1) : 0;
    if ( in != ascii_tx_index_out ) {
        // buffer not full, update index to queue data
        ascii_tx_index_in = in;
    }
    // enable TX FIFO threshold interrupt to kick things off
    uart_tx_int_ena();
}

/* waits until transmitter is ready, then transmits character */
void cons_tx_wait(char c)
{
    uint in = ascii_tx_index_in;
    ascii_tx_buf[in] = c;
    // increment 'in' with wrap
    in = ( in < (SERIAL_ASCII_TX_BUF_LEN-1) ) ? (in+1) : 0;
    while ( in == ascii_tx_index_out ); // wait if buffer full
    // update index to queue data
    ascii_tx_index_in = in;
    // enable TX FIFO threshold interrupt to kick things off
    uart_tx_int_ena();
}

/* returns non-zero if transmitter is idle (all characters sent) */
int cons_tx_idle(void)
{
    return uart_tx_idle();
}

/* returns non-zero if reciever has a character available */
int cons_rx_ready(void)
{
    return ( ascii_rx_index_in != ascii_rx_index_out );
}

/* gets a character without waiting, may return garbage if reciever is not ready */
char cons_rx(void)
{
    char c = 0;
    uint out = ascii_rx_index_out;
    if ( out != ascii_rx_index_in) {
        // there is something, get it
        c = ascii_rx_buf[out];
        // increment 'out' with wrap
        out = ( out < (SERIAL_ASCII_RX_BUF_LEN-1) ) ? (out+1) : 0;
        ascii_rx_index_out = out;
    }
    return c;
}

/* waits until receiver is ready, then gets character */
char cons_rx_wait(void)
{
    uint out = ascii_rx_index_out;
    while ( out == ascii_rx_index_in); // wait for data available
    char c = ascii_rx_buf[out];
    // increment 'out' with wrap
    out = ( out < (SERIAL_ASCII_RX_BUF_LEN-1) ) ? (out+1) : 0;
    ascii_rx_index_out = out;
    return c;
}
