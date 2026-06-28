/***************************************************************
 * 
 * bundle.h - library for bundling string and multiple binary
 *            packet channels onto a single stream
 * 
 * 
 **************************************************************/

#ifndef BUNDLE_H
#define BUNDLE_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

/*****************************************************************
 * Program Interface
 *
 * This module supports an string channel as well as up to 128
 * binary packet channels which can coexist on the same port.
 * String data is limited to the 7-bit ASCII character set and
 * is sent character-by-character.  Binary packets are
 * higher priority, and are transparently injected into the
 * serial stream at any time.  The protocol allows the two
 * streams to be separated at the receiving node.
 *
 * The module provides independent buffers for the string
 * channel and for binary packets.  Binary packets have a
 * channel number from 0 to 127, and packets with unique
 * channel numbers have separate buffers which can be
 * read from or written by different threads.
 *
 * The protocol works by limiting the string channel to values
 * between 0x01 and 0x7F.  Values of 0x80 and higher are used
 * to indicate the start of a binary packet as well as the
 * packet address.  Binary packets use COBS (constant overhead
 * byte stuffing) to avoid including zeros in the packet, at
 * the expense of one extra byte per packet.  A value of zero
 * indicates the end of a binary packet, and can be followed
 * by either string data or another binary packet.
 *
 * Transmitting can be referred to as "bundling" since it
 * bundles multiple channels into a single stream.  Receiving
 * can be referred to as "unbundling" since it takes a single
 * stream and splits it into multiple channels.
 * 
 * The transmit and receive functions are completely decoupled.
 * Transmitting is done by a bdl_tx_t object, while receiving
 * is done by a bdl_rx_t object.  Each stands alone, although
 * they are often used in pairs.
 *
 * The module provides separate APIs for string data and binary
 * packets, as described below.
 */

 typedef enum {
    BDL_TX_CHAR_MODE = 0,
    BDL_TX_SEND_COBS_BYTE,
    BDL_TX_SEND_DATA_BYTE
} bdl_tx_state_t;

typedef struct bdl_tx_s {
    // all fields are private; use bdl_* functions to access
    // string channel transmit buffer (caller-supplied via bdl_string_set_tx_buffer())
    volatile char      *string_buf;
    uint32_t            string_buf_size;
    uint32_t            string_in;
    uint32_t            string_out;
    // packet transmit list; pkt_root is the sentinel node
    bdl_packet_t        pkt_root;
    bdl_packet_t       *pkt_current;    // packet currently being transmitted
    uint8_t             pkt_data_index; // byte index into current packet's data
    // tx state machine
    bdl_tx_state_t      tx_state;
    // hardware callback - set via bdl_set_start_tx_callback()
    void              (*start_tx)(void);
} bdl_tx_t;


typedef enum {
    BDL_RX_STRING_MODE = 0,
    BDL_RX_DISCARD_PACKET,
    BDL_RX_GET_COBS_BYTE,
    BDL_RX_GET_DATA_BYTE
} bdl_rx_state_t;

typedef struct bdl_rx_s {
    // all fields are private; use bdl_* functions to access
    // string channel receive buffer (caller-supplied via bdl_string_set_rx_buffer())
    volatile char      *string_buf;
    uint32_t            string_buf_size;
    uint32_t            string_in;
    uint32_t            string_out;
    // packet receive list; pkt_root is the sentinel node
    bdl_packet_t        pkt_root;
    bdl_packet_t       *pkt_current;    // packet currently being received
    uint8_t             pkt_byte_count; // bytes received so far in current packet
    // rx state machine
    bdl_rx_state_t      rx_state;
    // error counter - read via bdl_packet_rx_error_count()
    uint32_t            error_count;
} bdl_rx_t;


/*****************************************************************
 * Setup
 *
 * Both transmit and receive objects need setup before they
 * can be used.  Both require string buffers, the location
 * and size of which are determined by the user; details are
 * in the String Interface section below.  The transmit
 * object also requires a 'start_tx' callback as part of the
 * hardware interace; see the Hardware Interface section below
 * for details.
 * 
 * To initialize each object, declare instances of the structs
 * below, set their values, and call the init functions.
 * 
 * Example:
 *
 *   static char tx_buf[256];
 *   static bdl_tx_t my_tx;
 *
 *   const bdl_tx_config_t my_tx_cfg = {
 *       .string_buf      = tx_buf,
 *       .string_buf_size = sizeof(tx_buf),
 *       .start_tx        = my_uart_start_tx,
 *   };
 *   bdl_init_tx(&my_tx, &my_tx_cfg);
 * 
 */


typedef struct {
    char    *string_buf;
    size_t   string_buf_size;
    void   (*start_tx)(void);
} bdl_tx_config_t;

void bdl_init_tx(bdl_tx_t *bdl, const bdl_tx_config_t *cfg);


typedef struct {
    char    *string_buf;
    size_t   string_buf_size;
} bdl_rx_config_t;

void bdl_init_rx(bdl_rx_t *bdl, const bdl_rx_config_t *cfg);


/*****************************************************************
 * String Interface:
 *
 * The module uses separate receive and transmit buffers.
 * The buffers are provided by the user during setup; call
 * bdl_string_set_XX_buffer() to pass a buffer to the object.
 *
 * The receive buffer is designed to feed a single consumer,
 * and the transmit buffer is designed to be fed by a single
 * source.  The following functions are not neccessarily
 * re-entrant or thread-safe:
 *
 * 'bdl_string_get_nb()' is a non-blocking read of the receive
 * buffer; it returns '\0' if there is no data available.
 * 'bdl_string_get_bl()' is a blocking read of the receive
 * buffer; it busy-waits if no data is available.
 * 'bdl_string_can_get()' is non-blocking and returns true if
 * there is data in the receive buffer.
 *
 * 'bdl_string_put_nb()' is a non-blocking write to the transmit
 * buffer; if the buffer is full it returns false and discards
 * the data.
 * 'bdl_string_put_bl()' is a blocking write to the transmit
 * buffer; it busy-waits if the buffer is full.
 * 'bdl_string_can_put()' is non-blocking and returns true if
 * there is space in the transmit buffer.
 *
 */

char bdl_string_get_nb(bdl_rx_t *bdl);
char bdl_string_get_bl(bdl_rx_t *bdl);
bool bdl_string_can_get(bdl_rx_t *bdl);

bool bdl_string_put_nb(bdl_tx_t *bdl, char c);
void bdl_string_put_bl(bdl_tx_t *bdl, char c);
bool bdl_string_can_put(bdl_tx_t *bdl);

/*****************************************************************
 * Binary Packet Interface - Packet structures:
 *
 * Binary packets are buffered using bdl_packet_t structures.
 * These structures and their associated buffers can be
 * statically declared or dynamically allocated.  The application
 * should declare or allocate a bdl_packet_t struct and a buffer,
 * then call bdl_packet_init_buf() once to associate the buffer
 * with the struct.
 *
 * The caller owns both the bdl_packet_t struct and its associated
 * data buffer for the lifetime of the application.  The bundle
 * machinery temporarily takes ownership during transmit or receive
 * (while state != BP_IDLE) and returns it when the operation
 * completes.  The caller may access the data buffer directly at
 * any time when state == BP_IDLE.
 * 
 * 'bdl_packet_init_buf(*p, *buf, len)' initializes packet 'p'
 * to use buffer 'buf' which must be of length 'len' (1 to 254
 * bytes).
 *
 * The application should never directly access the packet struct;
 * getters and setters are provided for members that the API might
 * need to access.
 *
 * The application must never access a packet or its data buffer
 * unless 'bdl_packet_get_state()' returns BP_IDLE.
 *
 */

 typedef enum {
    BP_IDLE = 0,
    BP_RX_WAIT, BP_RX_BUSY, BP_RX_DONE,
    BP_TX_WAIT, BP_TX_BUSY
} bdl_packet_state_t;

typedef struct bdl_packet_s {
    uint8_t cobs_byte;          // overhead byte generated by COBS encode
    uint8_t data_len;           // actual data length (not counting COBS byte)
    uint8_t max_len;            // size of the buffer at *data
    uint8_t header;             // packet channel num OR'ed with 0x80 - private
    bdl_packet_state_t state;   // packet buffer state - private
    uint8_t *data;              // pointer to the actual data
    struct bdl_packet_s *next;  // used for buffer list management - private
    struct bdl_packet_s *prev;  // used for buffer list management - private
} bdl_packet_t;

void bdl_packet_init_buf(bdl_packet_t *p, uint8_t *buf, uint8_t len);

static inline bdl_packet_state_t bdl_packet_get_state(bdl_packet_t *p)
{
    return p->state;
}

static inline uint8_t bdl_packet_get_chan(bdl_packet_t *p)
{
    return p->header & 0x7F;
}

static inline uint8_t bdl_packet_get_len(bdl_packet_t *p)
{
    return p->data_len;
}

void bdl_packet_set_chan(bdl_packet_t *p, uint8_t chan);
void bdl_packet_set_len(bdl_packet_t *p, uint8_t len);


 /*****************************************************************
 * Binary Packet Interface - Sending and Receiving:
 *
 * To send a packet, write data into the buffer, call the setter
 * functions for data length and channel number (if needed), then
 * call 'bdl_packet_put()'.
 *
 * 'bdl_packet_put()' will queue the packet for transmission,
 * set the state to 'BP_TX_WAIT' and return.  The packet state
 * will later cycle through 'BP_TX_BUSY' and eventually become
 * 'BP_IDLE' at which point the packet has been transmitted
 * and the structure and buffer may be reused.  If 'use_crc'
 * is true, a 16-bit CRC will be calculated and added to the
 * packet.
 *
 * The transmit process will not change data length or channel
 * number, so to send repeat packets of the same length to the
 * same channel the application can just call 'bdl_packet_put()'
 * each time.
 *
 * To recieve a packet, call the channel number setter function
 * (if needed), then call 'bdl_packet_listen()'.
 *
 * 'bdl_packet_listen()' adds the packet to the receiver queues,
 * zeros 'data_len', sets the state to 'BP_RX_WAIT', then returns.
 * If/when a matching packet arrives, the state will cycle through
 * 'BP_RX_BUSY' and eventually become 'BP_RX_DONE'.
 *
 * Once the state is 'BP_RX_DONE', call 'bdl_packet_get()' to
 * decode the data and set the state to 'BP_IDLE'.  If 'use_crc'
 * is true, the CRC will be checked and removed.  If a CRC error
 * occurs, 'bdl_packet_get()' will return FALSE; if it returns
 * TRUE, the structure and buffer contain valid data that can be
 * read.  Call the data length getter to determine how many bytes
 * are available in the buffer.
 * 
 * Regardless of the 'bdl_packet_get()' return value, the packet
 * state will become BP_IDLE, and it can be re-used for transmit
 * or receive.  The receive process will not change the channel,
 * so to repeatedly listen for packets on the same channel the
 * application can just call 'bdl_packet_listen()' each time.
 *
 */

void bdl_packet_put(bdl_tx_t *bdl, bdl_packet_t *p, bool use_crc);

void bdl_packet_listen(bdl_rx_t *bdl, bdl_packet_t *p);
bool bdl_packet_get(bdl_rx_t *bdl, bdl_packet_t *p, bool use_crc);
uint32_t bdl_packet_rx_error_count(bdl_rx_t *bdl);
void bdl_packet_rx_error_reset(bdl_rx_t *bdl);


/*****************************************************************
 * Hardware Interface
 *
 * This module is hardware agnostic, but it designed to support
 * an interrupt driven UART.  It provides the following two
 * functions:
 *
 * 'bdl_put_rx_byte()' should be called by the hardware driver
 * when a byte is received; typically from a "receive data
 * available" interrupt handler.  This function can run in
 * interrupt context and places the received byte into the
 * appropriate incoming data buffer.
 *
 * 'bdl_get_tx_byte()' should be called by the hardware driver,
 * typically from a "transmit buffer empty" interrupt handler.
 * This function can run in interrupt context and will either
 * return 0-255 as the byte to send, or >255 if there is no
 * data in any outgoing buffer.
 *
 * When bdl_get_tx_byte() returns >255, the hardware driver
 * will typically disable the transmit interrupt.
 *
 * The driver must provide a function to start transmission,
 * perhaps by enabling a transmit interrupt or similar.
 * Call bdl_set_start_tx_callback() during setup to register
 * this callback.
 * 
 * This module will call the callback in thread context when
 * there is data to be sent.  The callback should re-enable
 * the 'transmit buffer empty" interrupt, at which point the
 * transmit interrupt handler will call bdl_get_tx_byte()
 * repeatedly until it again returns a value > 255.
 */

void bdl_put_rx_byte(bdl_rx_t *bdl, uint8_t data);

uint32_t bdl_get_tx_byte(bdl_tx_t *bdl);

#endif // BUNDLE_H
