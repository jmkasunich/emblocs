/***************************************************************
 *
 * bl_monitor.c - EMBLOCS runtime monitor implementation
 *
 * see bl_monitor.h for API details
 *
 **************************************************************/

#include "bl_monitor.h"
#include "serial.h"
#include "ser_crc.h"
#include <stdint.h>
#include <stddef.h>
#include <assert.h>

/***************************************************************
 * Protocol constants
 * Packet address for all EMBLOCS infrastructure traffic.
 * Request and response type bytes occupy the first payload byte.
 **************************************************************/

#define BL_MONITOR_PKT_ADDR     0x7F

// request packet type bytes (monitor -> target)
#define RQ_VERSION              0x41    // 'A' - request protocol version
#define RQ_NAME                 0x42    // 'B' - request design name
#define RQ_BS_NAME              0x43    // 'C' - request next blockspec name and hash
#define RQ_BS_META              0x44    // 'D' - request blockspec metadata packet

// reply packet type bytes (target -> monitor)
#define RP_VERSION              0x41    // 'A' - protocol version response
#define RP_NAME                 0x42    // 'B' - design name response
#define RP_BS_NAME              0x43    // 'C' - blockspec name and hash response
#define RP_BS_META              0x44    // 'D' - blockspec metadata packet (more follows)
#define RP_BS_META_END          0x45    // 'E' - blockspec metadata last packet


#define BL_RQ_FIRST    RQ_VERSION      // 0x41 - lowest valid request type
#define BL_RQ_LAST     RQ_BS_META      // 0x44 - highest valid request type

/***************************************************************
 * bl_replies[] dispatch table
 * Defined in generated system_meta.c.
 * Indexed by (response_type - RS_FIRST).
 * Non-NULL entries are complete single-packet constant replies.
 * NULL entries require special handling in handle_complex_request().
 **************************************************************/
extern const char * const bl_replies[];

/***************************************************************
 * Packet buffers
 * One receive buffer, one transmit buffer.
 * Base packet size is based on serial.c limit
 * Payload size allows for 2-byte CRC + 1 byte packet type
 **************************************************************/

#define BL_PKT_BUF_SIZE     254
#define BL_PKT_PAYLOAD_SIZE (BL_PKT_BUF_SIZE-3)

static ser_packet_t rx_pkt;
static uint8_t      rx_buf[BL_PKT_BUF_SIZE];
static ser_packet_t tx_pkt;
static uint8_t      tx_buf[BL_PKT_BUF_SIZE];

/***************************************************************
 * private helpers
 **************************************************************/

// send a constant string reply; str must be null-terminated
// and already start with the reply type
static void send_const_reply( const char *str )
{
    uint8_t len = 0;
    // if transmit buffer is not idle, drop the reply
    if ( ser_packet_get_state(&tx_pkt) != SP_IDLE ) {
        return;
    }
    // copy string contents (without null terminator)
    while ( *str != '\0' ) {
        assert(len < 250);
        tx_buf[len++] = (uint8_t)(*str++);
    }
    ser_packet_set_len(&tx_pkt, len);
    ser_packet_crc_encode(&tx_pkt);
    ser_packet_put(&tx_pkt);
}

// handle requests that cannot be served from bl_replies[]
static void handle_complex_request( uint8_t req_type, ser_packet_t *pkt )
{
    // TODO: multi-packet responses (blockspec metadata chunks etc.)
    (void)req_type;
    (void)pkt;
}

// handle strings that don't fit in one packet
static void send_long_str( uint8_t rep_type, uint8_t pkt_num, char *str)
{
    int pkt_start = pkt_num * BL_PKT_PAYLOAD_SIZE;
    int i = 0;
    while ( i < pkt_start ) {
        if ( str[i++] == '\0' ) {
            // string ends before requested packet
            // send "end" reply with no data
            tx_buf[0] = rep_type;
            ser_packet_set_len(&tx_pkt, 1);
            ser_packet_crc_encode(&tx_pkt);
            ser_packet_put(&tx_pkt);
            return;
        }
    }
    int j = 0;
    while ( j < BL_PKT_PAYLOAD_SIZE ) {
        if ( str[i] == '\0' ) {
            // string ends within requested packet
            // send "end" reply with data
            tx_buf[0] = rep_type;
            ser_packet_set_len(&tx_pkt, j+1);
            ser_packet_crc_encode(&tx_pkt);
            ser_packet_put(&tx_pkt);
            return;
        }
        // copy to buffer
        tx_buf[j++] = str[i++];
    }
    // string ends beyond requested packet
    // send "more" reply with data
    tx_buf[0] = rep_type + 1;
    ser_packet_set_len(&tx_pkt, j+1);
    ser_packet_crc_encode(&tx_pkt);
    ser_packet_put(&tx_pkt);
    return;
}

#define INTS_PER_PACKET (BL_PKT_PAYLOAD_SIZE/4)
// handle arrays of 32-bit values that don't fit in one packet
// this was going to be used to send all params in a lump, but might take a different
// approach where each blockdef pulls its own params from the big lump and sends them
static void send_multiple_uints( uint8_t rep_type, uint8_t pkt_num, uint32_t *data, uint16_t data_count)
{
    int i = pkt_num * INTS_PER_PACKET;;
    int j = 0;
    while ( ( i < data_count ) && ( j < INTS_PER_PACKET ) ) {
        for ( int b = 0 ; b < 4 ; b++ ) {
            tx_buf[j*4+b] = (data[j] >> b) & 0xFF;
        }
        j++;
        i++;
    }
    if ( i < data_count ) {
        // more data follows, send "more" reply with data
        tx_buf[0] = rep_type + 1;
    } else {
        // no more data, send "end" reply with data
        tx_buf[0] = rep_type;
    }
    ser_packet_set_len(&tx_pkt, j*4+1);
    ser_packet_crc_encode(&tx_pkt);
    ser_packet_put(&tx_pkt);
    return;
}


/***************************************************************
 * API
 **************************************************************/

void bl_monitor_init( void )
{
    // initialize packet buffers
    ser_packet_init_buf(&rx_pkt, rx_buf, BL_PKT_BUF_SIZE);
    ser_packet_init_buf(&tx_pkt, tx_buf, BL_PKT_BUF_SIZE);
    ser_packet_set_addr(&rx_pkt, BL_MONITOR_PKT_ADDR);
    ser_packet_set_addr(&tx_pkt, BL_MONITOR_PKT_ADDR);
    // begin listening for incoming infrastructure packets
    ser_packet_listen(&rx_pkt);
}

void bl_monitor_poll( void )
{
    uint8_t req_type, reply_idx;
    const char *reply;
    // check if a packet has been received
    if ( ser_packet_get_state(&rx_pkt) != SP_RX_DONE ) {
        return;
    }
    // decode and verify CRC
    ser_packet_get(&rx_pkt);
    if ( !ser_packet_crc_decode(&rx_pkt) ) {
        // bad CRC - discard and listen for next packet
        ser_packet_listen(&rx_pkt);
        return;
    }
    // must have at least a type byte
    if ( ser_packet_get_len(&rx_pkt) < 1 ) {
        ser_packet_listen(&rx_pkt);
        return;
    }
    req_type = rx_buf[0];
    // check for legal packet type
    if ( ( req_type < BL_RQ_FIRST ) || ( req_type > BL_RQ_LAST ) ) {
        ser_packet_listen(&rx_pkt);
        return;
    }
    // look up in dispatch table
    reply_idx = req_type - BL_RQ_FIRST;
    reply = bl_replies[reply_idx];
    if ( reply != NULL ) {
        // simple constant reply - send it
        send_const_reply(reply);
    } else {
        // complex reply - handle separately
        handle_complex_request(req_type, &rx_pkt);
    }
    // re-arm receiver for next packet
    ser_packet_listen(&rx_pkt);
}
