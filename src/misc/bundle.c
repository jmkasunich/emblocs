/***************************************************************
 * 
 * bundle.c - library for bundling string and multiple binary
 *            packet channels onto a single stream
 * 
 * see bundle.h for API details
 * 
 * *************************************************************/

#include "bundle.h"
#ifdef __arm__
#include <cmsis_compiler.h> // __disable_irq(), __enable_irq()
#else
#include "test_stubs.h"
#endif
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
 * Public CRC computation functions
 * Caller may or may not choose to use these.
 **************************************************************/

// compute CRC-16-CCITT over a buffer, using bitwise loop
// slower but smaller
uint16_t bdl_crc16_bitwise(uint16_t seed, const uint8_t *data, uint8_t len)
{
    uint16_t crc = seed;
    uint8_t i, j;

    for ( i = 0 ; i < len ; i++ ) {
        crc ^= ((uint16_t)data[i] << 8);
        for ( j = 0 ; j < 8 ; j++ ) {
            if ( crc & 0x8000 ) {
                crc = (crc << 1) ^ 0x1021;
            } else {
                crc <<= 1;
            }
        }
    }
    return crc;
}

// compute CRC-16-CCITT over a buffer, using a lookup table
// fast but large - beware if MCU executes out of serial flash,
// data fetches from the lookup table may be slow

static const uint16_t crc_lookup[256] = {
    0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50A5, 0x60C6, 0x70E7,
    0x8108, 0x9129, 0xA14A, 0xB16B, 0xC18C, 0xD1AD, 0xE1CE, 0xF1EF,
    0x1231, 0x0210, 0x3273, 0x2252, 0x52B5, 0x4294, 0x72F7, 0x62D6,
    0x9339, 0x8318, 0xB37B, 0xA35A, 0xD3BD, 0xC39C, 0xF3FF, 0xE3DE,
    0x2462, 0x3443, 0x0420, 0x1401, 0x64E6, 0x74C7, 0x44A4, 0x5485,
    0xA56A, 0xB54B, 0x8528, 0x9509, 0xE5EE, 0xF5CF, 0xC5AC, 0xD58D,
    0x3653, 0x2672, 0x1611, 0x0630, 0x76D7, 0x66F6, 0x5695, 0x46B4,
    0xB75B, 0xA77A, 0x9719, 0x8738, 0xF7DF, 0xE7FE, 0xD79D, 0xC7BC,
    0x48C4, 0x58E5, 0x6886, 0x78A7, 0x0840, 0x1861, 0x2802, 0x3823,
    0xC9CC, 0xD9ED, 0xE98E, 0xF9AF, 0x8948, 0x9969, 0xA90A, 0xB92B,
    0x5AF5, 0x4AD4, 0x7AB7, 0x6A96, 0x1A71, 0x0A50, 0x3A33, 0x2A12,
    0xDBFD, 0xCBDC, 0xFBBF, 0xEB9E, 0x9B79, 0x8B58, 0xBB3B, 0xAB1A,
    0x6CA6, 0x7C87, 0x4CE4, 0x5CC5, 0x2C22, 0x3C03, 0x0C60, 0x1C41,
    0xEDAE, 0xFD8F, 0xCDEC, 0xDDCD, 0xAD2A, 0xBD0B, 0x8D68, 0x9D49,
    0x7E97, 0x6EB6, 0x5ED5, 0x4EF4, 0x3E13, 0x2E32, 0x1E51, 0x0E70,
    0xFF9F, 0xEFBE, 0xDFDD, 0xCFFC, 0xBF1B, 0xAF3A, 0x9F59, 0x8F78,
    0x9188, 0x81A9, 0xB1CA, 0xA1EB, 0xD10C, 0xC12D, 0xF14E, 0xE16F,
    0x1080, 0x00A1, 0x30C2, 0x20E3, 0x5004, 0x4025, 0x7046, 0x6067,
    0x83B9, 0x9398, 0xA3FB, 0xB3DA, 0xC33D, 0xD31C, 0xE37F, 0xF35E,
    0x02B1, 0x1290, 0x22F3, 0x32D2, 0x4235, 0x5214, 0x6277, 0x7256,
    0xB5EA, 0xA5CB, 0x95A8, 0x8589, 0xF56E, 0xE54F, 0xD52C, 0xC50D,
    0x34E2, 0x24C3, 0x14A0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
    0xA7DB, 0xB7FA, 0x8799, 0x97B8, 0xE75F, 0xF77E, 0xC71D, 0xD73C,
    0x26D3, 0x36F2, 0x0691, 0x16B0, 0x6657, 0x7676, 0x4615, 0x5634,
    0xD94C, 0xC96D, 0xF90E, 0xE92F, 0x99C8, 0x89E9, 0xB98A, 0xA9AB,
    0x5844, 0x4865, 0x7806, 0x6827, 0x18C0, 0x08E1, 0x3882, 0x28A3,
    0xCB7D, 0xDB5C, 0xEB3F, 0xFB1E, 0x8BF9, 0x9BD8, 0xABBB, 0xBB9A,
    0x4A75, 0x5A54, 0x6A37, 0x7A16, 0x0AF1, 0x1AD0, 0x2AB3, 0x3A92,
    0xFD2E, 0xED0F, 0xDD6C, 0xCD4D, 0xBDAA, 0xAD8B, 0x9DE8, 0x8DC9,
    0x7C26, 0x6C07, 0x5C64, 0x4C45, 0x3CA2, 0x2C83, 0x1CE0, 0x0CC1,
    0xEF1F, 0xFF3E, 0xCF5D, 0xDF7C, 0xAF9B, 0xBFBA, 0x8FD9, 0x9FF8,
    0x6E17, 0x7E36, 0x4E55, 0x5E74, 0x2E93, 0x3EB2, 0x0ED1, 0x1EF0,
};

uint16_t bdl_crc16_lookup(uint16_t seed, const uint8_t *data, uint8_t len)
{
    uint16_t crc = seed;
    uint8_t i;
    for ( i = 0 ; i < len ; i++ ) {
        crc = (crc << 8) ^ crc_lookup[((crc >> 8) ^ data[i]) & 0xFF];
    }
    return crc;
}

// Compute the per-channel CRC seed.  Must match bundle.py's seed
// formula exactly for interoperability.  Note that we use
// 'header' which is chan | 0x80, because the packet struct contains
// header but not chan
#define _crc_seed(header) (((header) << 8) | ((~(header)) & 0xFF))

/***************************************************************
 *
 * Packet Struct Functions
 *
 * *************************************************************/

void bdl_packet_init_buf(bdl_packet_t *p, uint8_t *buf, uint8_t len)
{
    assert(len <= 254);
    assert(len >= 2);
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
    assert(len <= (p->max_len - 2));  // allow room for CRC
    p->data_len = len;
}

/***************************************************************
 *
 * Receive API Functions
 *
 * *************************************************************/

void bdl_init_rx(bdl_rx_t *bdl, const bdl_rx_config_t *cfg)
{
    assert(cfg->string_buf != NULL);
    assert(cfg->string_buf_size >= 2);
    assert(cfg->crc16 != NULL);
    bdl->rx_state = BDL_RX_STRING_MODE;
    bdl->error_count = 0;
    bdl->string_buf = cfg->string_buf;
    bdl->string_buf_size = cfg->string_buf_size;
    bdl->string_in = 0;
    bdl->string_out = 0;
    bdl->crc16 = cfg->crc16;
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
    // this makes less frequently used buffers drift towards the tail
    // so frequently used ones are found faster
    // this is a critical region
    __disable_irq();
    p->prev = &(bdl->pkt_root);
    p->next = bdl->pkt_root.next;
    p->next->prev = p;
    bdl->pkt_root.next = p;
    __enable_irq();
}

bool bdl_packet_get(bdl_rx_t *bdl, bdl_packet_t *p)
{
    uint16_t crc_calc, crc_recv;
    uint8_t len;

    assert(p->state == BP_RX_DONE);
    assert(p->data != NULL);
    assert(p->data_len <= p->max_len);
    assert(bdl->crc16 != NULL);
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
    // check CRC
    if ( p->data_len < 2 ) {
        // too short to contain a valid CRC
        bdl->error_count++;
        return false;
    }
    len = p->data_len - 2;
    crc_calc = bdl->crc16(_crc_seed(p->header), p->data, len);
    // read received CRC little-endian
    crc_recv = (uint16_t)p->data[len] | ((uint16_t)p->data[len + 1] << 8);
    if ( crc_calc != crc_recv ) {
        // CRC doesn't match
        bdl->error_count++;
        return false;
    }
    // CRC matches - remove CRC bytes from visible payload
    p->data_len = len;
    return true;
}

uint32_t bdl_get_error_count(bdl_rx_t *bdl)
{
    return bdl->error_count;
}

void bdl_reset_error_count(bdl_rx_t *bdl)
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
    assert(cfg->string_buf != NULL);
    assert(cfg->string_buf_size >= 2);
    assert(cfg->crc16 != NULL);
    assert(cfg->start_tx != NULL);
    bdl->tx_state = BDL_TX_STRING_MODE;
    bdl->string_buf = cfg->string_buf;
    bdl->string_buf_size = cfg->string_buf_size;
    bdl->string_in = 0;
    bdl->string_out = 0;
    bdl->start_tx = cfg->start_tx;
    bdl->crc16 = cfg->crc16;
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

void bdl_packet_put(bdl_tx_t *bdl, bdl_packet_t *p)
{
    uint16_t crc;
    uint8_t len;

    assert(p->state == BP_IDLE);
    assert(p->data != NULL);
    assert(p->data_len <= (p->max_len-2)); // need room for CRC
    assert(p->header >= 128);
    assert(bdl->crc16 != NULL);
    p->state = BP_TX_WAIT;
    // compute and append CRC
    len = p->data_len;
    crc = bdl->crc16(_crc_seed(p->header), p->data, len);
    p->data[len]     = (uint8_t)(crc & 0xFF);
    p->data[len + 1] = (uint8_t)(crc >> 8);
    p->data_len += 2;
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


// for automated testing only
#ifdef BDL_BUILD_TESTS
size_t bdl_test_sizeof_packet(void) { return sizeof(bdl_packet_t); }
size_t bdl_test_sizeof_rx(void)     { return sizeof(bdl_rx_t); }
size_t bdl_test_sizeof_tx(void)     { return sizeof(bdl_tx_t); }
#endif
