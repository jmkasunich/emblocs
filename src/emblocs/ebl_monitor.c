/***************************************************************
 *
 * ebl_monitor.c - EMBLOCS runtime monitor implementation
 *
 * see bl_monitor.h for API details
 *
 **************************************************************/

#include "ebl_monitor.h"
#include <stdint.h>
#include <stddef.h>
#include <assert.h>

/***************************************************************
 * Protocol constants
 * Packet address for all EMBLOCS infrastructure traffic.
 * Request and response type bytes occupy the first payload byte.
 **************************************************************/

#define EBL_MONITOR_PKT_ADDR     0x7F

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
 * ebl_replies[] dispatch table
 * Defined in generated system_meta.c.
 * Indexed by (response_type - RS_FIRST).
 * Non-NULL entries are complete single-packet constant replies.
 * NULL entries require special handling in handle_complex_request().
 **************************************************************/
extern const char * const ebl_replies[];

/***************************************************************
 * bundle objects used by monitor
 * set by ebl_monitor_init()
 **************************************************************/
static bdl_tx_t *monitor_tx = NULL;
static bdl_rx_t *monitor_rx = NULL;


/***************************************************************
 * Packet buffers
 * One receive buffer, one transmit buffer.
 * Base packet size is based on bundle.c limit
 * Payload size allows for 2-byte CRC + 1 byte packet type
 **************************************************************/

#define EBL_PKT_BUF_SIZE     254
#define EBL_PKT_PAYLOAD_SIZE (EBL_PKT_BUF_SIZE-3)

static bdl_packet_t rx_pkt;
static uint8_t      rx_buf[EBL_PKT_BUF_SIZE];
static bdl_packet_t tx_pkt;
static uint8_t      tx_buf[EBL_PKT_BUF_SIZE];

/***************************************************************
 * private helpers
 **************************************************************/

// send a constant string reply; str must be null-terminated
// and already start with the reply type
static void send_const_reply( const char *str )
{
    uint8_t len = 0;
    // if transmit buffer is not idle, drop the reply
    if ( bdl_packet_get_state(&tx_pkt) != BP_IDLE ) {
        return;
    }
    // copy string contents (without null terminator)
    while ( *str != '\0' ) {
        assert(len < 250);
        tx_buf[len++] = (uint8_t)(*str++);
    }
    bdl_packet_set_len(&tx_pkt, len);
    bdl_packet_put(monitor_tx, &tx_pkt, NULL);
}

// handle requests that cannot be served from ebl_replies[]
static void handle_complex_request( uint8_t req_type, bdl_packet_t *pkt )
{
    // TODO: multi-packet responses (blockspec metadata chunks etc.)
    (void)req_type;
    (void)pkt;
}

// handle strings that don't fit in one packet
static void send_long_str( uint8_t rep_type, uint8_t pkt_num, char *str)
{
    int pkt_start = pkt_num * EBL_PKT_PAYLOAD_SIZE;
    int i = 0;
    while ( i < pkt_start ) {
        if ( str[i++] == '\0' ) {
            // string ends before requested packet
            // send "end" reply with no data
            tx_buf[0] = rep_type;
            bdl_packet_set_len(&tx_pkt, 1);
            bdl_packet_put(monitor_tx, &tx_pkt, NULL);
            return;
        }
    }
    int j = 0;
    while ( j < EBL_PKT_PAYLOAD_SIZE ) {
        if ( str[i] == '\0' ) {
            // string ends within requested packet
            // send "end" reply with data
            tx_buf[0] = rep_type;
            bdl_packet_set_len(&tx_pkt, (uint8_t)(j+1));
            bdl_packet_put(monitor_tx, &tx_pkt, NULL);
            return;
        }
        // copy to buffer
        tx_buf[j++] = str[i++];
    }
    // string ends beyond requested packet
    // send "more" reply with data
    tx_buf[0] = rep_type + 1;
    bdl_packet_set_len(&tx_pkt, (uint8_t)(j+1));
    bdl_packet_put(monitor_tx, &tx_pkt, NULL);
    return;
}

#define INTS_PER_PACKET (EBL_PKT_PAYLOAD_SIZE/4)
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
    bdl_packet_set_len(&tx_pkt, (uint8_t)(j*4+1));
    bdl_packet_put(monitor_tx, &tx_pkt, NULL);
    return;
}


/***************************************************************
 * API
 **************************************************************/

void ebl_monitor_init(bdl_rx_t *rx, bdl_tx_t *tx)
{
    // save bundle objects
    monitor_rx = rx;
    monitor_tx = tx;
    // initialize packet buffers
    bdl_packet_init_buf(&rx_pkt, rx_buf, EBL_PKT_BUF_SIZE);
    bdl_packet_init_buf(&tx_pkt, tx_buf, EBL_PKT_BUF_SIZE);
    bdl_packet_set_chan(&rx_pkt, EBL_MONITOR_PKT_ADDR);
    bdl_packet_set_chan(&tx_pkt, EBL_MONITOR_PKT_ADDR);
    // begin listening for incoming infrastructure packets
    bdl_packet_listen(monitor_rx, &rx_pkt, NULL);
}

void ebl_monitor_poll(void)
{
    uint8_t req_type, reply_idx;
    const char *reply;
    // check if a packet has been received
    if ( bdl_packet_get_state(&rx_pkt) != BP_RX_DONE ) {
        return;
    }
    // decode and verify CRC
    if ( ! bdl_packet_get(monitor_rx, &rx_pkt) ) {
        // bad CRC - discard and listen for next packet
        bdl_packet_listen(monitor_rx, &rx_pkt, NULL);
        return;
    }
    // must have at least a type byte
    if ( bdl_packet_get_len(&rx_pkt) < 1 ) {
        bdl_packet_listen(monitor_rx, &rx_pkt, NULL);
        return;
    }
    req_type = rx_buf[0];
    // check for legal packet type
    if ( ( req_type < BL_RQ_FIRST ) || ( req_type > BL_RQ_LAST ) ) {
        bdl_packet_listen(monitor_rx, &rx_pkt, NULL);
        return;
    }
    // look up in dispatch table
    reply_idx = req_type - BL_RQ_FIRST;
    reply = ebl_replies[reply_idx];
    if ( reply != NULL ) {
        // simple constant reply - send it
        send_const_reply(reply);
    } else {
        // complex reply - handle separately
        handle_complex_request(req_type, &rx_pkt);
    }
    // re-arm receiver for next packet
    bdl_packet_listen(monitor_rx, &rx_pkt, NULL);
}
