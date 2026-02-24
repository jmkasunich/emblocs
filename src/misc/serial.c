/***************************************************************
 * 
 * serial.c - serial port functions
 * 
 * see serial.h for API details
 * 
 * *************************************************************/

#include "serial.h"

#ifndef uint
#define uint unsigned int
#endif

 /* macros for incrementing circular buffer indexes
 *
 * both of these return 'index' + 1 modulo 'size'
 * the _C version is better if size is constant at compile time
 * the _V version is better if size is variable at compile time
 *
 * neither version uses a modulo operation
 * the _C version uses bitwise AND if 'size' is a power of 2
 * either version can evaluate 'index' more than once; 'index' should
 * not be an expression with side effects.  The _C version evaluates
 * 'size' multiple times, but 'size' is supposed to be a constant
 * expression which can't have side effects.
 *
 */
#define NEXT_C(index, size) (!((size)&((size)-1)) ? (((index)+1)&((size)-1)) : (((index)+1) < (size) ? (index)+1 : 0))
#define NEXT_V(index, size) (((index)+1) < (size) ? (index)+1 : 0)


void ser_packet_init(ser_packet_t *p, uint8_t *b, uint8_t len, uint8_t addr)
{
    assert(len < 254);
    assert(addr < 128);
    p->data = b;
    p->max_len = len;
    p->data_len = 0;
    p->addr = addr;
    p->state = SP_IDLE;
    p->cobs_byte = 0;
    p->prev = p;
    p->next = p;
}


static enum {
    RX_CHAR_MODE,
    RX_DISCARD_PACKET,
    RX_GET_COBS_BYTE,
    RX_GET_DATA_BYTE
} rx_state = RX_CHAR_MODE;
static volatile char rx_buf[SER_ASCII_RX_BUF_SIZE];
static uint rx_in = 0;
static uint rx_out = 0;
static ser_packet_t rx_root = { .state = SP_IDLE,
                                .max_len = 0,
                                .data_len = 0,
                                .addr = 0x80,
                                .cobs_byte = 0,
                                .data = NULL,
                                .prev = &rx_root,
                                .next = &rx_root };
static ser_packet_t *rx_packet = &rx_root;

char ser_ascii_get_nb(void)
{
    char c;

    if ( (c = rx_buf[rx_out]) != 0 ) {
        rx_buf[rx_out] = 0;
        rx_out = NEXT_C(rx_out, SER_ASCII_RX_BUF_SIZE);
    }
    return c;
}

char ser_ascii_get_bl(void)
{
    char c;

    while ( (c = rx_buf[rx_out]) == 0 );
    rx_buf[rx_out] = 0;
    rx_out = NEXT_C(rx_out, SER_ASCII_RX_BUF_SIZE);
    return c;
}

bool ser_ascii_can_get(void)
{
    return ( rx_buf[rx_out] != 0 );
}

void ser_packet_listen(ser_packet_t *p)
{
    assert(p->state == SP_IDLE);
    assert(p->data != NULL);
    assert(p->addr < 128);
    p->data_len = 0;
    p->state = SP_RX_WAIT;
    // insert at end of list
    // this should be a critical region
    p->next = &rx_root;
    p->prev = rx_root.prev;
    p->prev->next = p;
    rx_root.prev = p;
    // critical region end
}

void ser_packet_get(ser_packet_t *p)
{
    assert(p->state == SP_RX_DONE);
    assert(p->data != NULL);
    assert(p->data_len <= p->max_len);
    // COBS decode here
    p->state = SP_IDLE;
}

void ser_put_rx_byte(uint8_t data)
{
    switch (rx_state) {
        case RX_CHAR_MODE:
            if ( data & 0x80 ) {
                // start of packet character
                // search listen list for matching buffer
                data &= 0x7f;
                rx_packet = rx_root.next;
                while ( ( rx_packet != &rx_root ) && ( rx_packet->addr != data ) ) {
                    rx_packet = rx_packet->next;
                }
                if ( rx_packet->addr == data ) {
                    // match found, set up buffer for receive
                    rx_packet->data_len = 0;
                    rx_packet->state = SP_RX_BUSY;
                    rx_state = RX_GET_COBS_BYTE;
                } else {
                    // no match
                    rx_state = RX_DISCARD_PACKET;
                }
            } else {
                // ordinary ASCII character
                if ( rx_buf[rx_in] == 0 ) {
                    rx_buf[rx_in] = data;
                    rx_in = NEXT_C(rx_in, SER_ASCII_TX_BUF_SIZE);
                }
            }
            break;
        case RX_DISCARD_PACKET:
            if ( data == '\0' ) {
                rx_state = RX_CHAR_MODE;
            }
            break;
        case RX_GET_COBS_BYTE:
            if ( data == '\0' ) {
                // packet ended early
                rx_packet->state = SP_RX_WAIT;
                rx_state = RX_CHAR_MODE;
            } else {
                rx_packet->cobs_byte = data;
                rx_state = RX_GET_DATA_BYTE;
            }
            break;
        case RX_GET_DATA_BYTE:
            if ( data == '\0' ) {
                // packet finished, unlink buffer from list
                rx_packet->prev->next = rx_packet->next;
                rx_packet->next->prev = rx_packet->prev;
                rx_packet->prev = rx_packet->next = rx_packet;
                rx_packet->state = SP_RX_DONE;
                rx_state = RX_CHAR_MODE;
            } else if ( rx_packet->data_len >= rx_packet->max_len ) {
                // packet too long
                rx_packet->state = SP_RX_WAIT;
                rx_state = RX_DISCARD_PACKET;
            } else {
                rx_packet->data[rx_packet->data_len++] = data;
            }
            break;
        default:
            break;
    }
}


static enum {
    TX_CHAR_MODE,
    TX_SEND_COBS_BYTE,
    TX_SEND_DATA_BYTE
} tx_state = TX_CHAR_MODE;
static volatile char tx_buf[SER_ASCII_TX_BUF_SIZE];
static uint tx_in = 0;
static uint tx_out = 0;
static ser_packet_t tx_root = { .state = SP_IDLE,
                                .max_len = 0,
                                .data_len = 0,
                                .addr = 0x80,
                                .cobs_byte = 0,
                                .data = NULL,
                                .prev = &tx_root,
                                .next = &tx_root };
static ser_packet_t *tx_packet = &tx_root;
static uint tx_data_index = 0;

bool ser_ascii_put_nb(char c)
{
    c &= 0x7F;
    if ( tx_buf[tx_in] == 0 ) {
        tx_buf[tx_in] = c;
        tx_in = NEXT_C(tx_in, SER_ASCII_TX_BUF_SIZE);
        ser_start_tx();
        return true;
    }
    return false;
}

void ser_ascii_put_bl(char c)
{
    c &= 0x7F;
    while ( tx_buf[tx_in] != 0 );
    tx_buf[tx_in] = c;
    tx_in = NEXT_C(tx_in, SER_ASCII_TX_BUF_SIZE);
    ser_start_tx();
}

bool ser_ascii_can_put(void)
{
    return ( tx_buf[tx_in] == 0 );
}

void ser_packet_put(ser_packet_t *p)
{
    assert(p->state == SP_IDLE);
    assert(p->data != NULL);
    assert(p->data_len <= p->max_len);
    assert(p->addr < 128);
    p->state = SP_TX_WAIT;
    // do COBS encoding here
    // insert at end of list
    // this should be a critical region
    p->next = &rx_root;
    p->prev = rx_root.prev;
    p->prev->next = p;
    rx_root.prev = p;
    // critical region end
    ser_start_tx();
}

uint32_t ser_get_tx_byte(void)
{
    uint8_t data;

    switch (tx_state) {
        case TX_CHAR_MODE:
            // binary packets take precedence over text, check if there is one
            tx_packet = tx_root.next;
            if ( tx_packet != &tx_root ) {
                // there is a packet to send; unlink it from list
                tx_packet->prev->next = tx_packet->next;
                tx_packet->next->prev = tx_packet->prev;
                tx_packet->prev = tx_packet->next = tx_packet;
                // set up for packet transmit
                tx_packet->state = SP_TX_BUSY;
                tx_state = TX_SEND_COBS_BYTE;
                // send the start of packet byte
                return (tx_packet->addr | 0x80 );
            } else if ( (data = tx_buf[tx_out]) != 0 ) {
                // send a character
                tx_out = NEXT_C(tx_out, SER_ASCII_TX_BUF_SIZE);
                return data;
            } else {
                // nothing to send
                return 0x100;
            }
            break;
        case TX_SEND_COBS_BYTE:
            tx_state = TX_SEND_DATA_BYTE;
            tx_data_index = 0;
            return tx_packet->cobs_byte;
            break;
        case TX_SEND_DATA_BYTE:
            if ( tx_data_index < tx_packet->data_len ) {
                // send data byte
                return tx_packet->data[tx_data_index++];
            } else {
                // end of packet, send terminator byte
                tx_packet->state = SP_IDLE;
                tx_state = TX_CHAR_MODE;
                return 0;
            }
            break;
        default:
            break;
    }
}

