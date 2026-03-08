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
#include <stddef.h>

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
 * then call ser_packet_init_buf() once to associate the buffer
 * with the struct.
 *
 * 'ser_packet_init_BUF(*p, *buf, len)' initializes packet 'p'
 * to use buffer 'buf' which must be of length 'len' (1 to 254
 * bytes).
 *
 * The application should never directly access the packet struct;
 * getters and setters are provided for members that the API might
 * need to access.
 *
 * The application must never access a packet or its data buffer
 * unless 'ser_packet_get_state()' returns SP_IDLE.
 *
 * To send a packet, write data into the buffer, call the setter
 * functions for data length and packet address (if needed), then
 * call 'ser_packet_put()'.
 *
 * 'ser_packet_put()' will queue the packet for transmission,
 * set the state to 'SP_TX_WAIT' and return.  The packet state
 * will later cycle through 'SP_TX_BUSY' and eventually become
 * 'SP_IDLE' at which point the packet has been transmitted
 * and the structure and buffer may be reused.
 *
 * The transmit process will not change data length or packet
 * address, so to send repeat packets of the same length to the
 * same address the application can just call 'ser_packet_put()'
 * each time.
 *
 * To recieve a packet, call the address setter function (if
 * needed), then call 'ser_packet_listen()'.
 *
 * 'ser_packet_listen()' adds the packet to the receiver queues,
 * zeros 'data_len', sets the state to 'SP_RX_WAIT', then returns.
 * If/when a matching packet arrives, the state will cycle through
 * 'SP_RX_BUSY' and eventually become 'SP_RX_DONE'.
 *
 * Once the state is 'SP_RX_DONE', call 'ser_packet_get()' to
 * decode the data and set the state to 'SP_IDLE'.  At that point,
 * the structure and buffer can be read and/or reused.  Call the
 * data length getter to determine how many bytes are available
 * in the buffer.  The receive process will not change the address,
 * so to repeatedly listen for packets at the same address the
 * application can just call 'ser_packet_listen()' each time.
 *
 */

typedef enum {
    SP_IDLE = 0,
    SP_RX_WAIT, SP_RX_BUSY, SP_RX_DONE,
    SP_TX_WAIT, SP_TX_BUSY
} ser_packet_state_t;

typedef struct ser_packet_s {
    uint8_t cobs_byte;          // overhead byte generated by COBS encode
    uint8_t data_len;           // actual data length (not counting COBS byte)
    uint8_t max_len;            // size of the buffer at *data
    uint8_t header;             // packet address OR'ed with 0x80 - private
    ser_packet_state_t state;   // packet buffer state - private
    uint8_t *data;              // pointer to the actual data
    struct ser_packet_s *next;  // used for buffer list management - private
    struct ser_packet_s *prev;  // used for buffer list management - private
} ser_packet_t;

void ser_packet_init_buf(ser_packet_t *p, uint8_t *buf, uint8_t len);

static inline ser_packet_state_t ser_packet_get_state(ser_packet_t *p)
{
    return p->state;
}
static inline uint8_t ser_packet_get_addr(ser_packet_t *p)
{
    return p->header & 0x7F;
}

static inline uint8_t ser_packet_get_len(ser_packet_t *p)
{
    return p->data_len;
}

void ser_packet_set_addr(ser_packet_t *p, uint8_t addr);
void ser_packet_set_len(ser_packet_t *p, uint8_t len);

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
