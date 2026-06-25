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
    RQ_BS_NAME          = 0x43 # blockspec name and hash (w/spec #)
    RQ_BS_META          = 0x44 # blockspec metadata packet (w/spec # & packet #)
    RQ_BD_NAME          = 0x46 # blockdef name (w/def #)
    RQ_BD_PARAMS        = 0x47 # blockdef parameter values (w/def #)
    RQ_BI_NAME          = 0x48 # blockinstance name (w/def #)

class ReplyPacketType(Enum):
    RP_VERSION          = 0x41 # hello response with protocol version
    RP_NAME             = 0x42 # design name and object counts
    RP_BS_NAME          = 0x43 # blockspec name and hash, 8-bit param count
    RP_BS_META          = 0x44 # blockspec metadata last packet
    RP_BS_META_MORE     = 0x45 # blockspec metadata packet (not last packet)
    RP_BD_NAME          = 0x46 # blockdef name, 8-bit blockspec number
    RP_BD_PARAM         = 0x47 # up to 62 parameter values in binary
    RP_BI_NAME          = 0x48 # blockinstance name, 8-bit blockdef number

# specific packet details - need to move these details from comments to code

# RP_NAME starts with 16-bit counts for blockspecs, blockdefs, block instances,
#   signals and threads; followed by the design name and maybe a design hash
# RQ_BS_NAME requests blockspec data by index number (16 bits)
# RP_BS_NAME contains name and hash as strings
# RQ_BS_META requests metadata by index number (16 bits) and packet number (8 bits)
# RP_BS_META contains 0-251 bytes of metadata, and says that there is no more
# RP_BS_META_MORE contains 251 bytes of metadata, and says that there is more


# -------------------------------------
# this section is a sample of what the generated metadata might look like
#
#
#  typedef struct {
#       const char const *name;
#       const char const *hash;
#       const uint8_t param_count;
#       const char const *compressed;
#  } blmd_blockspec_t;
#
#  blmd_blockspec_t blmd_blockspecs[] = {
#       { "mux", "172hxclkg", 2,
#         "acompressedescriptionthatcanbequitelong"},
#       { "limit1", "df8jw3lj", 0,
#         "anothercompresseddesription"}
#  };
#
#  uint32_t blmd_params[] = {
#       3, 2,          // params for blockdef 0
#       1, 3,          // params for blockdef 2
#  };
#
#  typedef struct {
#       const char const *name;
#       const uint16_t blockspec_num;
#       const uint16_t first_param;
#  } blmd_blockdef_t;
#
#  blmd_blockdef_t blmd_blockdefs[] = {
#       { "mux_3ch_2in", 0, 0 },
#       { "mylimit1", 1, 0 },
#       { "mux_1ch_3in", 2, }
#  };
#


