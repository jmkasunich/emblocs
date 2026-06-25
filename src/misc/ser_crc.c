/***************************************************************
 *
 * ser_crc.c - CRC16 protection for serial packets
 *
 * See ser_crc.h for API details
 *
 * Implements CRC-16-CCITT (polynomial 0x1021, initial value
 * 0xFFFF, no reflection).  This matches the result of Python's
 * binascii.crc_hqx(data, 0xFFFF) on the PC side.
 *
 * All multi-byte values are little-endian.
 *
 **************************************************************/

#include "ser_crc.h"
#include <assert.h>

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

/***************************************************************
 * API
 **************************************************************/

void ser_packet_crc_encode(ser_packet_t *p) {
    uint16_t crc;
    uint8_t len;
    // programming error if payload is too long to append CRC
    assert(p->data_len <= 252);
    len = p->data_len;
    crc = crc16_compute(p->data, len);
    // append CRC little-endian
    p->data[len]     = (uint8_t)(crc & 0xFF);
    p->data[len + 1] = (uint8_t)(crc >> 8);
    ser_packet_set_len(p, len + 2);
}

bool ser_packet_crc_decode(ser_packet_t *p) {
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
    ser_packet_set_len(p, len);
    return true;
}
