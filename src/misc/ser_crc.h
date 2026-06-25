/***************************************************************
 *
 * ser_crc.h - CRC16 protection for serial packets
 *
 * Provides CRC16 encode and decode operations on ser_packet_t
 * objects.  Callers that need reliable delivery (e.g. metadata
 * exchange) use these functions; callers that do not need it
 * (e.g. oscilloscope streaming) use ser_packet_t directly.
 *
 **************************************************************/

#ifndef SER_CRC_H
#define SER_CRC_H

#include <stdint.h>
#include <stdbool.h>
#include "serial.h"

/*****************************************************************
 * CRC16 Packet Interface
 *
 * These functions add and verify a 2-byte CRC16 appended to the
 * payload of a ser_packet_t.  The maximum usable payload is
 * therefore 252 bytes (254 - 2).
 *
 * ser_packet_crc_encode() computes a CRC16 over the current
 * payload (p->data[0] through p->data[p->data_len - 1]), appends
 * it as 2 bytes in little-endian order, and increments p->data_len
 * by 2.  The caller must have already set p->data_len to the
 * payload length before calling.  Asserts that p->data_len <= 252
 * before appending; a longer payload is a programming error.
 *
 * ser_packet_crc_decode() verifies the CRC16 appended to the
 * packet payload.  If p->data_len < 2, or if the CRC does not
 * match, returns false and leaves the packet unchanged.  On
 * success, decrements p->data_len by 2 (removing the CRC bytes
 * from the visible payload) and returns true.
 *
 * Typical usage:
 *
 *   // sending
 *   memcpy(pkt.data, payload, payload_len);
 *   ser_packet_set_len(&pkt, payload_len);
 *   ser_packet_crc_encode(&pkt);
 *   ser_packet_put(&pkt);
 *
 *   // receiving (after ser_packet_get())
 *   if (!ser_packet_crc_decode(&pkt)) {
 *       // handle corrupt packet
 *   }
 *   // pkt.data_len now reflects payload only, without CRC bytes
 *
 *****************************************************************/

void ser_packet_crc_encode(ser_packet_t *p);
bool ser_packet_crc_decode(ser_packet_t *p);

#endif // SER_CRC_H
