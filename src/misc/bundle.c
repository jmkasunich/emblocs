/***************************************************************
 * 
 * bundle.c - library for bundling string and multiple binary
 *            packet channels onto a single stream
 * 
 * see bundle.h for API details
 * 
 * *************************************************************/

#include "bundle.h"
#include <cmsis_compiler.h> // __disable_irq(), __enable_irq()
#include <assert.h>

#ifndef uint
#define uint unsigned int
#endif

 /* macro for incrementing circular buffer indexes
 *
 * returns 'index' + 1 modulo 'size' without using a modulo operation
 * can evaluate 'index' more than once; 'index' should not be an
 * expression with side effects.
 *
 */
#define NEXT(index, size) (((index)+1) < (size) ? (index)+1 : 0)

/***************************************************************
 * private helpers
 **************************************************************/

// update a running CRC-16-CCITT with one byte
static uint16_t crc16_update(uint16_t crc, uint8_t byte) {
    uint8_t i;
    crc ^= ((uint16_t)byte << 8);
    for ( i = 0 ; i < 8 ; i++ ) {
        if ( crc & 0x8000 ) {
            crc = (crc << 1) ^ 0x1021;
        } else {
            crc <<= 1;
        }
    }
    return crc;
}

// compute CRC-16-CCITT over a buffer
static uint16_t crc16_compute(const uint8_t *data, uint8_t len) {
    uint16_t crc = 0xFFFF;
    uint8_t i;
    for ( i = 0 ; i < len ; i++ ) {
        crc = crc16_update(crc, data[i]);
    }
    return crc;
}

// add CRC to a packet
static void bdl_packet_crc_encode(bdl_packet_t *p) {
    uint16_t crc;
    uint8_t len;
    // programming error if payload is too long to append CRC
    assert(p->data_len <= 252);
    len = p->data_len;
    crc = crc16_compute(p->data, len);
    // append CRC little-endian
    p->data[len]     = (uint8_t)(crc & 0xFF);
    p->data[len + 1] = (uint8_t)(crc >> 8);
    p->data_len += 2;
}

// check CRC on a packet
static bool bdl_packet_crc_decode(bdl_packet_t *p) {
    uint16_t crc_calc, crc_recv;
    uint8_t len;
    // too short to contain a valid CRC
    if ( p->data_len < 2 ) {
        return false;
    }
    len = p->data_len - 2;
    crc_calc = crc16_compute(p->data, len);
    // read received CRC little-endian
    crc_recv = (uint16_t)p->data[len] | ((uint16_t)p->data[len + 1] << 8);
    if ( crc_calc != crc_recv ) {
        return false;
    }
    // CRC matches - remove CRC bytes from visible payload
    p->data_len -= 2;
    return true;
}

/***************************************************************
 *
 * Packet Struct Functions
 *
 * *************************************************************/

void bdl_packet_init_buf(bdl_packet_t *p, uint8_t *buf, uint8_t len)
{
    assert(len <= 254);
    p->data = buf;
    p->max_len = len;
    p->data_len = 0;
    p->header = 0;
    p->state = BP_IDLE;
    p->cobs_byte = 0;
    p->prev = p;
    p->next = p;
}

void bdl_packet_set_chan(bdl_packet_t *p, uint8_t chan)
{
    assert(chan <= 0x7F );
    p->header = chan | 0x80;
}

void bdl_packet_set_len(bdl_packet_t *p, uint8_t len)
{
    assert(len <= p->max_len);
    p->data_len = len;
}

/***************************************************************
 *
 * Receive API Functions
 *
 * *************************************************************/

void bdl_init_rx(bdl_rx_t *bdl, const bdl_rx_config_t *cfg)
{
    bdl->rx_state = BDL_RX_STRING_MODE;
    bdl->error_count = 0;
    bdl->string_buf = cfg->string_buf;
    bdl->string_buf_size = cfg->string_buf_size;
    bdl->string_in = 0;
    bdl->string_out = 0;
    bdl->pkt_current = NULL;
    bdl->pkt_byte_count = 0;
    bdl->pkt_root.state = BP_IDLE;
    bdl->pkt_root.max_len = 0;
    bdl->pkt_root.data_len = 0;
    bdl->pkt_root.header = 0;
    bdl->pkt_root.cobs_byte = 0;
    bdl->pkt_root.data = NULL;
    bdl->pkt_root.prev = &(bdl->pkt_root);
    bdl->pkt_root.next = &(bdl->pkt_root);
}

char bdl_string_get_nb(bdl_rx_t *bdl)
{
    char c;

    if ( (c = bdl->string_buf[bdl->string_out]) != 0 ) {
        bdl->string_buf[bdl->string_out] = 0;
        bdl->string_out = NEXT(bdl->string_out, bdl->string_buf_size);
    }
    return c;
}

char bdl_string_get_bl(bdl_rx_t *bdl)
{
    char c;

    while ( (c = bdl->string_buf[bdl->string_out]) == 0 );
    bdl->string_buf[bdl->string_out] = 0;
    bdl->string_out = NEXT(bdl->string_out, bdl->string_buf_size);
    return c;
}

bool bdl_string_can_get(bdl_rx_t *bdl)
{
    return ( bdl->string_buf[bdl->string_out] != 0 );
}

void bdl_packet_listen(bdl_rx_t *bdl, bdl_packet_t *p)
{
    assert(p->state == BP_IDLE);
    assert(p->data != NULL);
    assert(p->header >= 128);
    p->data_len = 0;
    p->state = BP_RX_WAIT;
    // insert at head of list
    // this is a critical region
    __disable_irq();
    p->prev = &(bdl->pkt_root);
    p->next = bdl->pkt_root.next;
    p->next->prev = p;
    bdl->pkt_root.next = p;
    __enable_irq();
}

bool bdl_packet_get(bdl_rx_t *bdl, bdl_packet_t *p, bool use_crc)
{
    assert(p->state == BP_RX_DONE);
    assert(p->data != NULL);
    assert(p->data_len <= p->max_len);
    // COBS decoding
    uint8_t *bp = p->data + p->cobs_byte - 1;
    uint8_t * const end = p->data + p->data_len;
    while (bp < end) {
        uint8_t code = *bp;
        *bp = 0;
        bp += code;
    }
    // decoding complete
    p->state = BP_IDLE;
    if (( use_crc ) && ( !bdl_packet_crc_decode(p) )) {
        bdl->error_count++;
        return false;
    } else {
        return true;
    }
}

uint32_t bdl_packet_rx_error_count(bdl_rx_t *bdl)
{
    return bdl->error_count;
}

void bdl_packet_rx_error_reset(bdl_rx_t *bdl)
{
    bdl->error_count = 0;
}


void bdl_put_rx_byte(bdl_rx_t *bdl, uint8_t data)
{
    bdl_packet_t *p;

    switch (bdl->rx_state) {
        case BDL_RX_STRING_MODE:
            if ( data & 0x80 ) {
                // start of packet character
                // search listen list for matching buffer
                p = bdl->pkt_root.next;
                while ( ( p->header != 0 ) && ( p->header != data ) ) {
                    p = p->next;
                }
                if ( p->header == data ) {
                    // match found, set up buffer for receive
                    p->data_len = 0;
                    p->state = BP_RX_BUSY;
                    bdl->pkt_current = p;
                    bdl->rx_state = BDL_RX_GET_COBS_BYTE;
                } else {
                    // no match
                    bdl->error_count++;
                    bdl->pkt_byte_count = 0;  // no data received yet
                    bdl->rx_state = BDL_RX_DISCARD_PACKET;
                }
            } else {
                // ordinary ASCII character
                if ( bdl->string_buf[bdl->string_in] == 0 ) {
                    bdl->string_buf[bdl->string_in] = data;
                    bdl->string_in = NEXT(bdl->string_in, bdl->string_buf_size);
                }
            }
            break;
        case BDL_RX_DISCARD_PACKET:
            if ( data == '\0' ) {
                bdl->rx_state = BDL_RX_STRING_MODE;
            } else {
                bdl->pkt_byte_count++;
                if ( bdl->pkt_byte_count >= 255 ) {
                    bdl->rx_state = BDL_RX_STRING_MODE;
                }
            }
            break;
        case BDL_RX_GET_COBS_BYTE:
            p = bdl->pkt_current;
            if ( data == '\0' ) {
                // packet ended early
                bdl->error_count++;
                p->state = BP_RX_WAIT;
                bdl->rx_state = BDL_RX_STRING_MODE;
            } else {
                p->cobs_byte = data;
                bdl->rx_state = BDL_RX_GET_DATA_BYTE;
            }
            break;
        case BDL_RX_GET_DATA_BYTE:
            p = bdl->pkt_current;
            if ( data == '\0' ) {
                // packet finished, unlink buffer from list
                // this is a critical region, but we're already in an ISR
                p->prev->next = p->next;
                p->next->prev = p->prev;
                p->prev = p->next = p;
                // critical region end
                p->state = BP_RX_DONE;
                bdl->rx_state = BDL_RX_STRING_MODE;
            } else if ( p->data_len >= p->max_len ) {
                // packet too long for buffer - discard remainder
                p->state = BP_RX_WAIT;
                bdl->error_count++;
                bdl->pkt_byte_count = p->data_len + 1;
                bdl->rx_state = BDL_RX_DISCARD_PACKET;
            } else {
                p->data[p->data_len++] = data;
            }
            break;
        default:
            assert(0);  // invalid rx_state - should never happen
            bdl->rx_state = BDL_RX_STRING_MODE;
            break;
    }
}

/***************************************************************
 *
 * Transmit API Functions
 *
 * *************************************************************/

void bdl_init_tx(bdl_tx_t *bdl, const bdl_tx_config_t *cfg)
{
    bdl->tx_state = BDL_TX_STRING_MODE;
    bdl->string_buf = cfg->string_buf;
    bdl->string_buf_size = cfg->string_buf_size;
    bdl->start_tx = cfg->start_tx;
    bdl->string_in = 0;
    bdl->string_out = 0;
    bdl->pkt_current = NULL;
    bdl->pkt_data_index = 0;
    bdl->pkt_root.state = BP_IDLE;
    bdl->pkt_root.max_len = 0;
    bdl->pkt_root.data_len = 0;
    bdl->pkt_root.header = 0;
    bdl->pkt_root.cobs_byte = 0;
    bdl->pkt_root.data = NULL;
    bdl->pkt_root.prev = &(bdl->pkt_root);
    bdl->pkt_root.next = &(bdl->pkt_root);
}

bool bdl_string_put_nb(bdl_tx_t *bdl, char c)
{
    if ( bdl->string_buf[bdl->string_in] == 0 ) {
        bdl->string_buf[bdl->string_in] = c & 0x7F;
        bdl->string_in = NEXT(bdl->string_in, bdl->string_buf_size);
        bdl->start_tx();
        return true;
    }
    return false;
}

void bdl_string_put_bl(bdl_tx_t *bdl, char c)
{
    while ( bdl->string_buf[bdl->string_in] != 0 );
    bdl->string_buf[bdl->string_in] = c & 0x7F;
    bdl->string_in = NEXT(bdl->string_in, bdl->string_buf_size);
    bdl->start_tx();
}

bool bdl_string_can_put(bdl_tx_t *bdl)
{
    return ( bdl->string_buf[bdl->string_in] == 0 );
}

void bdl_packet_put(bdl_tx_t *bdl, bdl_packet_t *p, bool use_crc)
{
    assert(p->state == BP_IDLE);
    assert(p->data != NULL);
    assert(p->data_len <= p->max_len);
    assert(p->header >= 128);
    p->state = BP_TX_WAIT;
    if ( use_crc ) {
        bdl_packet_crc_encode(p);
    }
    // COBS encoding
    uint8_t *bp = p->data;
    uint8_t * const end = bp + p->data_len;
    uint8_t code = 1;
    uint8_t *cp = &p->cobs_byte;
    while (bp < end) {
        if (*bp == 0u) {
            *cp = code;
            cp = bp;
            code = 1;
        } else {
            code++;
        }
        bp++;
    }
    *cp = code;
    // encoding complete
    // insert at end of list
    // this is a critical region
    __disable_irq();
    p->next = &(bdl->pkt_root);
    p->prev = bdl->pkt_root.prev;
    p->prev->next = p;
    bdl->pkt_root.prev = p;
    __enable_irq();
    bdl->start_tx();
}

uint32_t bdl_get_tx_byte(bdl_tx_t *bdl)
{
    uint8_t data;
    bdl_packet_t *p;

    switch (bdl->tx_state) {
        case BDL_TX_STRING_MODE:
            // binary packets take precedence over text, check if there is one
            p = bdl->pkt_root.next;
            if ( p != &(bdl->pkt_root) ) {
                // there is a packet to send; unlink it from list
                // this is a critical region, but we are already in an ISR
                p->prev->next = p->next;
                p->next->prev = p->prev;
                p->prev = p->next = p;
                // critical region end
                // set up for packet transmit
                p->state = BP_TX_BUSY;
                bdl->pkt_current = p;
                bdl->tx_state = BDL_TX_SEND_COBS_BYTE;
                // send the start of packet byte
                return p->header;
            } else if ( (data = bdl->string_buf[bdl->string_out]) != 0 ) {
                // send a character
                bdl->string_buf[bdl->string_out] = 0;
                bdl->string_out = NEXT(bdl->string_out, bdl->string_buf_size);
                return data;
            } else {
                // nothing to send
                return 0x100;
            }
            break;
        case BDL_TX_SEND_COBS_BYTE:
            bdl->tx_state = BDL_TX_SEND_DATA_BYTE;
            bdl->pkt_data_index = 0;
            return bdl->pkt_current->cobs_byte;
            break;
        case BDL_TX_SEND_DATA_BYTE:
            if ( bdl->pkt_data_index < bdl->pkt_current->data_len ) {
                // send data byte
                return bdl->pkt_current->data[bdl->pkt_data_index++];
            } else {
                // end of packet, send terminator byte
                bdl->pkt_current->state = BP_IDLE;
                bdl->tx_state = BDL_TX_STRING_MODE;
                return 0;
            }
            break;
        default:
            assert(0);  // invalid tx_state - should never happen
            bdl->tx_state = BDL_TX_STRING_MODE;
            return 0;
            break;
    }
}

