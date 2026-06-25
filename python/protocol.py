# protocol.py
# EMBLOCS Runtime Monitor - protocol constants and wire format definitions

from enum import Enum, auto

# All multi-byte values on the wire are little-endian

PROTOCOL_VERSION = "0.1"

# Packet type assignments for infrastructure packets
PKT_METADATA     = 0x7F    # hello and metadata exchange
PKT_MEMACCESS    = 0x7D    # arbitrary memory read/write

class RequestPacketType(Enum):
    RQ_VERSION          = 0x41 # hello and request protocol version
    RQ_NAME             = 0x42 # design name
    RQ_BS_NAME          = 0x43 # blockspec name and hash
    RQ_BS_META          = 0x44 # blockspec metadata packet (w/packet num)

class ResponsePacketType(Enum):
    RS_VERSION          = 0x41 # hello response with protocol version
    RS_NAME             = 0x42 # design name
    RS_BS_NAME          = 0x43 # blockspec name and hash
    RS_BS_META          = 0x44 # blockspec metadata packet (not last packet)
    RS_BS_META_END      = 0x45 # blockspec metadata last packet

