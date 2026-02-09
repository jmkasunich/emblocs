/***************************************************************
 * 
 * serial.h - serial port functions
 * 
 * This library provides common code for some serial port
 * functionality; it does not have hardware specific code.
 * 
 * It supports an ASCII channel as well as a binary packet 
 * channel, which can coexist on the same port.  ASCII data
 * is sent character-by-character.  Binary packets are higher
 * priority, and can be injected into the serial stream.
 *
 * The protocol allows the two streams to be separated at the
 * receiving node.
 * 
 * This code assumeds an interrupt driver UART, and has 
 * buffers for the ASCII channel as well as for binary packets
 *
 * The protocol works by prefixing binary packets with
 * the ASCII SOH character (0x01).  The binary packets are
 * encoded using COBS (consistent overhead byte stuffing),
 * which ensures that the packet does not contain any zero
 * bytes.  The end of the packet is marked by a zero byte.
 * 
 * The ASCII stream may not contain zero or SOH bytes, so 
 * the detection of either of those bytes clearly establishes
 * framing and the type of data to follow.
 *
 **************************************************************/

#ifndef SERIAL_H
#define SERIAL_H

#include <stdint.h>
#include <stdbool.h>
#include <string.h>  // memcpy
#ifndef uint
#define uint unsigned int
#endif
#ifndef byte
#define byte unsigned char
#endif

/* ring buffers
 *
 */

struct ringbuf_s {
    byte *buf;
    volatile uint in;
    volatile uint out;
    uint len;
};

/* intializes a ringbuffer.
 * buf must point to len bytes of free space
 */
inline void rb_init(struct ringbuf_s *rb, byte *buf, uint len)
{
    rb->buf = buf;
    rb->in = rb->out = 0;
    rb->len = len;
}

/* non-blocking put
 * adds byte to buffer and returns 1, unless buffer is
 * full, in which case discards byte and returns 0
 */
inline int rb_put_nb(struct ringbuf_s *rb, byte b)
{
    uint in = rb->in;
    rb->buf[in++] = b;
    if ( in >= rb->len ) in = 0;
    if ( in != rb->out ) {
        rb->in = in;
        return 1;
    } else {
        return 0;
    }
}

/* blocking put
 * adds byte to buffer, blocking if buffer is full
 */
inline void rb_put_bl(struct ringbuf_s *rb, byte b)
{
    uint in = rb->in;
    rb->buf[in++] = b;
    if ( in >= rb->len ) in = 0;
    while ( in == rb->out );
    rb->in = in;
}

/* test for full
 * returns non-zero if buffer is not full, else returns 0
 */
inline int rb_can_put(struct ringbuf_s *rb)
{
    // increment 'in' with wrap
    uint in = rb->in + 1;
    if ( in >= rb->len ) in = 0;
    return ( in != rb->out );
}

/* non-blocking get
 * if byte is available, returns it, else returns -1
 */
inline int rb_get_nb(struct ringbuf_s *rb)
{
    uint out = rb->out;
    if ( out == rb->in ) {
        return -1;
    } else {
        byte b = rb->buf[out++];
        if ( out >= rb->len ) out = 0;
        rb->out = out;
        return b;
    }
}

/* blocking get
 * returns byte from buffer, blocking if buffer is empty
 */
byte rb_get_bl(struct ringbuf_s *rb)
{
    uint out = rb->out;
    while ( out == rb->in );
    byte b = rb->buf[out++];
    if ( out >= rb->len ) out = 0;
    rb->out = out;
    return b;
}

/* test for empty
 * returns non-zero if buffer is not empty, else returns 0
 */
int rb_can_get_nb(struct ringbuf_s *rb)
{
    return ( rb->in != rb->out );
}


/* binary packets
 *
 */

#define MAX_BINARY_PACKET_PAYLOAD 50

_Static_assert((MAX_BINARY_PACKET_PAYLOAD <= 250), "binary packet too large");

struct binary_packet_s {
    byte *buf;
    volatile uint in;
    volatile uint out;
    uint payload_len;
};


/* clears a binary packet
 */
inline void bp_init(struct binary_packet_s *bp)
{
    bp->in = 0;
    bp->out = 0;
    bp->payload_len = 0;
}

inline bool bp_append8(struct binary_packet_s *bp, uint8_t *src)
{
    if ( bp->payload_len < ( MAX_BINARY_PACKET_PAYLOAD - 1)) {
        bp->buf[bp->payload_len] = *src;
        bp->payload_len += 1;
        return true;
    } else {
        return false;
    }
}

inline bool bp_append16(struct binary_packet_s *bp, uint16_t *src)
{
    if ( bp->payload_len < ( MAX_BINARY_PACKET_PAYLOAD - 2)) {
        //bp->buf[bp->payload_len] = *src;
        memcpy(&(bp->buf[bp->payload_len]), src, 2);
        bp->payload_len += 2;
        return true;
    } else {
        return false;
    }
}

inline bool bp_append32(struct binary_packet_s *bp, uint32_t *src)
{
    if ( bp->payload_len < ( MAX_BINARY_PACKET_PAYLOAD - 4)) {
        //bp->buf[bp->payload_len] = *src;
        memcpy(&(bp->buf[bp->payload_len]), src, 4);
        bp->payload_len += 4;
        return true;
    } else {
        return false;
    }
}


/* non-blocking ASCII send 
 * if the ASCII buffer is full the character will be discarded
 * and the function will return zero, else returns 1
 */
int serial_char_put_nb(char c);

/* blocking ASCII send
 * if the ASCII buffer is full, the function will block until 
 * there is space.
 */
void serial_char_put_bl(char c);

/* non-blocking ASCII get 
 * if no character is available, returns -1
 * else returns character
 */
int serial_char_get_nb(void);

/* blocking ASCII get
 * if no character is available, the function will block until 
 * there is one
 */
int serial_char_get_bl(void);

/* ASCII receive status test
 * if no character is available, returns zero, else returns 1
 */
int serial_char_can_get_nb(void);



/* non-blocking binary packet send
 * if the packet buffer is full the packet will be discarded
 * and the function will return zero, else returns 1
 * maximum packet length is 250 bytes
 */
int serial_packet_put_nb(unsigned char *buf, unsigned int len);

/* blocking binary packet send
 * if the packet buffer is full the function will block until
 * there is space
 * maximum packet length is 250 bytes
 */
void serial_packet_put_bl(unsigned char *buf, unsigned int len);

/* non-blocking binary packet get
 * if no packet is available the function will return zero,
 * else returns 1 and sets '*len' to packet length
 * maximum packet length is 250 bytes
 */
int serial_packet_get_nb(unsigned char *buf, unsigned int *len);

/* blocking binary packet send
 * if no packet is available the function will block until
 * there is one
 * sets '*len' to packet length
 * maximum packet length is 250 bytes
 */
void serial_packet_get_bl(unsigned char *buf, unsigned int *len);

/* packet receive status test
 * if no packet is available, returns zero, else returns 1
 */
int serial_packet_avail_nb(void);

/***************************************************************
 * The implementation must provide the following functions,
 *
 * bool uart_rx_char_avail();
 * char uart_rx_get_char();
 * bool uart_tx_ready();
 * bool uart_tx_idle();
 * void uart_tx_send_char(char c);
 * void uart_tx_int_ena();
 * void uart_tx_int_dis();
 *
 */

// these are specific to the STM32G431 platform, need to decide how a more portable version will work

#define uart_rx_char_avail()    ((USART2)->ISR & (USART_ISR_RXNE_RXFNE_Msk))
#define uart_rx_get_char()      ((char)((USART2)->RDR))
#define uart_tx_ready()         ((USART2)->ISR & (USART_ISR_TXE_TXFNF_Msk))
#define uart_tx_idle()          ((USART2)->ISR & (USART_ISR_TC_Msk ))
#define uart_tx_send_char(c)    ((USART2)->TDR) = (c)
#define uart_tx_int_ena()       (USART2)->CR3 |= (USART_CR3_TXFTIE)
#define uart_tx_int_dis()       (USART2)->CR3 &= ~(USART_CR3_TXFTIE)



#endif // SERIAL_H