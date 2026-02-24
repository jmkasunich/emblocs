/***************************************************************
 * 
 * serial.h - serial port functions
 * 
 * This library provides common code for some serial port
 * functionality; it does not have hardware specific code.
 * 
 **************************************************************/

#ifndef SERIAL_H
#define SERIAL_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>>

/*****************************************************************
 * Program Interface
 *
 * This module supports an ASCII channel as well as a binary
 * packet channel, which can coexist on the same port.  ASCII
 * data is sent character-by-character.  Binary packets are
 * higher priority, and are transparently injected into the
 * serial stream at any time.  The protocol allows the two
 * streams to be separated at the receiving node.
 *
 * The module provides independent buffers for the ASCII
 * stream and for binary packets.  Binary packets have a
 * destination address from 0 to 127, and packets with
 * unique addresses have separate buffers which can be
 * read from or written by different threads.
 *
 * The protocol works by limiting the ASCII channel to values
 * between 0x01 and 0x7F.  Values of 0x80 and higher are used
 * to indicate the start of a binary packet as well as the
 * packet address.  Binary packets use COBS (constant overhead
 * byte stuffing) to avoid including zeros in the packet, at
 * the expense of one extra byte per packet.  A value of zero
 * indicates the end of a binary packet, and can be followed
 * by either more ASCII or another binary packet.
 *
 * The module provides separate APIs for ASCII and binary
 * packets, as described below.
 */


/*****************************************************************
 * ASCII Interface:
 *
 * The module provides separate receive and transmit buffers.
 * The receive buffer is designed to feed a single consumer,
 * and the transmit buffer is designed to be fed by a single
 * source.  The following functions are not neccessarily
 * re-entrant or thread-safe:
 *
 * 'ser_ascii_get_nb()' is a non-blocking read of the receive
 * buffer; it returns '\0' if there is no data available.
 * 'ser_ascii_get_bl()' is a blocking read of the receive
 * buffer; it busy-waits if no data is available.
 * 'ser_ascii_can_get()' is non-blocking and returns true if
 * there is data in the receive buffer.
 *
 * 'ser_ascii_put_nb()' is a non-blocking write to the transmit
 * buffer; if the buffer is full it returns false and discards
 * the data.
 * 'ser_ascii_put_bl()' is a blocking write to the transmit
 * buffer; it busy-waits if the buffer is full.
 * 'set_ascii_can_put()' is non-blocking and returns true if
 * there is space in the transmit buffer.
 *
 */

// buffer sizes are arbitrary,
// but powers of 2 are slightly more efficient

#ifndef SER_ASCII_RX_BUF_SIZE
#define SER_ASCII_RX_BUF_SIZE 128
#endif

char ser_ascii_get_nb(void);
char ser_ascii_get_bl(void);
bool ser_ascii_can_get(void);

#ifndef SER_ASCII_TX_BUF_SIZE
#define SER_ASCII_TX_BUF_SIZE 256
#endif

bool ser_ascii_put_nb(char c);
void ser_ascii_put_bl(char c);
bool ser_ascii_can_put(void);

/*****************************************************************
 * Binary Packet Interface:
 *
 * Binary packets are buffered using ser_packet_t structures.
 * These structures and their associated buffers can be
 * statically declared or dynamically allocated.  The application
 * should declare or allocate a ser_packet_t struct and a buffer,
 * then call ser_packet_init() once for each struct/buffer pair.
 *
 * 'ser_packet_init(*p, *b, len, addr)' initializes packet 'p'
 * to use buffer 'b' which must be of length 'len' (1 to 254
 * bytes).  'addr' will be used as the packet address, which
 * must be between 0 and 127.
 *
 * The application must never access a packet unless its state
 * is SP_IDLE.  The application may only modify the 'data_len'
 * or 'addr' fields of the packet structure; all other fields
 * are internal data.
 *
 * To send a packet, write data into the buffer at *data, set
 * the 'data_len' field to the length of the data, set the 'addr'
 * field, then call 'ser_packet_put()'.
 *
 * 'ser_packet_put()' will queue the packet for transmission,
 * set the state to 'SP_TX_WAIT' and return.  The packet state
 * will later cycle through 'SP_TX_BUSY' and eventually become
 * 'SP_IDLE' at which point the packet has been transmitted
 * and the structure and buffer may be reused.  The transmit
 * process will not change 'data_len' or 'addr'.
 *
 * To recieve a packet, set the 'addr' field, then call
 * 'ser_packet_listen()'.
 *
 * 'ser_packet_listen()' adds the packet to the receiver
 * queues, zeros 'data_len', sets the state to 'SP_RX_WAIT',
 * then returns.  If/when a matching packet arrives, the
 * state will cycle through 'SP_RX_BUSY' and eventually
 * become 'SP_RX_DONE'.
 *
 * Once the state is 'SP_RX_DONE', call 'ser_packet_get()'
 * to decode the data and set the state to 'SP_IDLE', at
 * which point *data contains 'data_len' bytes and the
 * structure and buffer can be read and/or reused.  The
 * receive process will not change 'addr'.
 *
 */

typedef struct ser_packet_s {
    enum {
        SP_IDLE = 0,
        SP_RX_WAIT,
        SP_RX_BUSY,
        SP_RX_DONE,
        SP_TX_WAIT,
        SP_TX_BUSY
    } state;
    uint8_t addr;
    uint8_t data_len;
    uint8_t max_len;
    uint8_t cobs_byte;
    uint8_t *data;
    struct ser_packet_s *next;
    struct ser_packet_s *prev;
} ser_packet_t;

void ser_packet_init(ser_packet_t *p, uint8_t *b, uint8_t len, uint8_t addr);
void ser_packet_put(ser_packet_t *p);
void ser_packet_listen(ser_packet_t *p);
void ser_packet_get(ser_packet_t *p);


/*****************************************************************
 * Hardware Interface
 *
 * This module is hardware agnostic, but it designed to support
 * an interrupt driven USRT.  It provides the following two
 * functions:
 *
 * 'ser_put_rx_byte()' should be called by the hardware driver
 * when a byte is received; typically from a "receive data
 * available" interrupt handler.  This function can run in
 * interrupt context and places the received byte into the
 * appropriate incoming data buffer.
 *
 * 'ser_get_tx_byte()' should be called by the hardware driver,
 * typically from a "transmit buffer empty" interrupt handler.
 * This function can run in interrupt context and will either
 * return 0-255 as the byte to send, or >255 if there is no
 * data in any outgoing buffer.
 *
 * When ser_get_tx_byte() returns >255, the hardware driver
 * will typically disable the transmit interrupt.
 *
 * The driver must provide a function called 'ser_start_tx()'.
 * This module will call ser_start_tx() in thread context when
 * there is data to be sent.  ser_start_tx() should re-enable
 * the 'transmit buffer empty" interrupt, at which point the
 * transmit interrupt handler will call ser_get_tx_byte()
 * repeatedly until it again returns a value > 255.
 */

void ser_put_rx_byte(uint8_t data);
uint32_t ser_get_tx_byte(void);
extern void ser_start_tx(void);

#endif // SERIAL_H
