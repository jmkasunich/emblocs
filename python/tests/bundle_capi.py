# python/tests/bundle_capi.py
"""
ctypes wrapper around the Bundle C library (bundle.c/bundle.h), built via
CMake into python/tests/data/tmp/bundle.{dll,so,dylib}.

Ordinary test code should only ever call methods on BundleCAPI. There are
no ctypes.Structure mirrors of bdl_tx_t/bdl_rx_t/bdl_packet_t/the config
structs -- every one of those is an opaque byte buffer as far as Python is
concerned, sized correctly via bdl_test_sizeof_*() and populated only by
real C calls. This isn't just simpler than mirroring their layout; it
makes "don't reach into internals" structurally true rather than a rule
someone has to remember, since there's no field to read except through
this class's methods.

Two lifetime pitfalls, both inherent to ctypes, worth knowing before
writing tests:
  - A packet's data buffer (passed to packet_init_buf) must stay alive
    for as long as that packet struct is in use -- the C struct stores
    a raw pointer, not a Python reference, so letting the buffer get
    garbage-collected while a packet still points at it is a real
    dangling-pointer bug. Keep it in a local variable for the test's
    duration.
  - Any Python callback passed to C must also be kept alive the
    same way. See register_callback() in conftest.py for one way
    to address that.
"""

import ctypes
import enum


CRC16_FUNC    = ctypes.CFUNCTYPE(ctypes.c_uint16, ctypes.c_uint16, ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint8)
VOID_VOID_FUNC = ctypes.CFUNCTYPE(None)
PACKET_FUNC = ctypes.CFUNCTYPE(None, ctypes.c_void_p)

class BdlPacketState(enum.IntEnum):
    BP_NOT_READY = 0
    BP_IDLE      = 1
    BP_RX_WAIT   = 2
    BP_RX_BUSY   = 3
    BP_RX_DONE   = 4
    BP_TX_WAIT   = 5
    BP_TX_BUSY   = 6


class BundleCAPI:
    """One thin Python method per Bundle C function."""

    def __init__(self, lib: ctypes.CDLL):
        self._lib = lib
        self._bind()
        self.sizeof_packet    = lib.bdl_test_sizeof_packet()
        self.sizeof_tx        = lib.bdl_test_sizeof_tx()
        self.sizeof_rx        = lib.bdl_test_sizeof_rx()
        self.sizeof_tx_config = lib.bdl_test_sizeof_tx_config()
        self.sizeof_rx_config = lib.bdl_test_sizeof_rx_config()

    def _bind(self):
        lib = self._lib

        for name in ("bdl_test_sizeof_packet", "bdl_test_sizeof_tx", "bdl_test_sizeof_rx",
                     "bdl_test_sizeof_tx_config", "bdl_test_sizeof_rx_config"):
            getattr(lib, name).restype = ctypes.c_size_t

        lib.bdl_init_tx.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        lib.bdl_init_tx.restype  = None
        lib.bdl_init_rx.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        lib.bdl_init_rx.restype  = None

        lib.bdl_string_get_nb.argtypes = [ctypes.c_void_p]
        lib.bdl_string_get_nb.restype  = ctypes.c_uint32
        lib.bdl_string_get_bl.argtypes = [ctypes.c_void_p]
        lib.bdl_string_get_bl.restype  = ctypes.c_char
        lib.bdl_string_put_nb.argtypes = [ctypes.c_void_p, ctypes.c_char]
        lib.bdl_string_put_nb.restype  = ctypes.c_bool
        lib.bdl_string_put_bl.argtypes = [ctypes.c_void_p, ctypes.c_char]
        lib.bdl_string_put_bl.restype  = ctypes.c_bool

        lib.bdl_string_can_get.argtypes = [ctypes.c_void_p]
        lib.bdl_string_can_get.restype  = ctypes.c_bool
        lib.bdl_string_can_put.argtypes = [ctypes.c_void_p]
        lib.bdl_string_can_put.restype  = ctypes.c_bool

        lib.bdl_packet_init_buf.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint8]
        lib.bdl_packet_init_buf.restype  = None
        lib.bdl_packet_set_chan.argtypes = [ctypes.c_void_p, ctypes.c_uint8]
        lib.bdl_packet_set_chan.restype  = None
        lib.bdl_packet_set_len.argtypes  = [ctypes.c_void_p, ctypes.c_uint8]
        lib.bdl_packet_set_len.restype   = None
        lib.bdl_packet_listen.argtypes   = [ctypes.c_void_p, ctypes.c_void_p, PACKET_FUNC]
        lib.bdl_packet_listen.restype    = None
        lib.bdl_packet_get.argtypes      = [ctypes.c_void_p, ctypes.c_void_p]
        lib.bdl_packet_get.restype       = ctypes.c_bool
        lib.bdl_packet_put.argtypes      = [ctypes.c_void_p, ctypes.c_void_p, PACKET_FUNC]
        lib.bdl_packet_put.restype       = None

        lib.bdl_put_rx_byte.argtypes = [ctypes.c_void_p, ctypes.c_uint8]
        lib.bdl_put_rx_byte.restype  = None
        lib.bdl_get_tx_byte.argtypes = [ctypes.c_void_p]
        lib.bdl_get_tx_byte.restype  = ctypes.c_uint32

        lib.bdl_get_error_count.argtypes   = [ctypes.c_void_p]
        lib.bdl_get_error_count.restype    = ctypes.c_uint32
        lib.bdl_reset_error_count.argtypes = [ctypes.c_void_p]
        lib.bdl_reset_error_count.restype  = None

        lib.bdl_test_packet_get_state.argtypes = [ctypes.c_void_p]
        lib.bdl_test_packet_get_state.restype  = ctypes.c_int
        lib.bdl_test_packet_get_chan.argtypes  = [ctypes.c_void_p]
        lib.bdl_test_packet_get_chan.restype   = ctypes.c_uint8
        lib.bdl_test_packet_get_len.argtypes   = [ctypes.c_void_p]
        lib.bdl_test_packet_get_len.restype    = ctypes.c_uint8
        lib.bdl_test_packet_read_data.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint8]
        lib.bdl_test_packet_read_data.restype  = None

        lib.bdl_test_make_tx_config.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t,
                                                 CRC16_FUNC, VOID_VOID_FUNC, VOID_VOID_FUNC]
        lib.bdl_test_make_tx_config.restype  = None
        lib.bdl_test_make_rx_config.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t,
                                                 CRC16_FUNC, VOID_VOID_FUNC]
        lib.bdl_test_make_rx_config.restype  = None

        lib.bdl_crc16_bitwise.argtypes = [ctypes.c_uint16, ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint8]
        lib.bdl_crc16_bitwise.restype  = ctypes.c_uint16
        lib.bdl_crc16_lookup.argtypes  = [ctypes.c_uint16, ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint8]
        lib.bdl_crc16_lookup.restype   = ctypes.c_uint16

        lib.bdl_test_crc_seed.argtypes = [ctypes.c_uint8]
        lib.bdl_test_crc_seed.restype  = ctypes.c_uint16

    # -- allocation helpers ----------------------------------------------

    def new_tx(self) -> ctypes.Array:
        return ctypes.create_string_buffer(self.sizeof_tx)

    def new_rx(self) -> ctypes.Array:
        return ctypes.create_string_buffer(self.sizeof_rx)

    def new_packet(self) -> ctypes.Array:
        return ctypes.create_string_buffer(self.sizeof_packet)

    def make_tx_config(self, string_buf, string_buf_size: int, crc16, tx_bytes_available=None, string_not_full=None) -> ctypes.Array:
        if tx_bytes_available is None:
            tx_bytes_available = ctypes.cast(None, VOID_VOID_FUNC)
        if string_not_full is None:
            string_not_full = ctypes.cast(None, VOID_VOID_FUNC)
        cfg = ctypes.create_string_buffer(self.sizeof_tx_config)
        self._lib.bdl_test_make_tx_config(cfg, string_buf, string_buf_size, crc16, tx_bytes_available, string_not_full)
        return cfg

    def make_rx_config(self, string_buf, string_buf_size: int, crc16, string_avail=None) -> ctypes.Array:
        if string_avail is None:
            string_avail = ctypes.cast(None, VOID_VOID_FUNC)
        cfg = ctypes.create_string_buffer(self.sizeof_rx_config)
        self._lib.bdl_test_make_rx_config(cfg, string_buf, string_buf_size, crc16, string_avail)
        return cfg

    @property
    def crc16_lookup_ptr(self):
        """Real bdl_crc16_lookup, cast to a function pointer for use in a config."""
        return ctypes.cast(self._lib.bdl_crc16_lookup, CRC16_FUNC)

    @property
    def crc16_bitwise_ptr(self):
        """Real bdl_crc16_bitwise, cast to a function pointer for use in a config."""
        return ctypes.cast(self._lib.bdl_crc16_bitwise, CRC16_FUNC)

    # -- real API ----------------------------------------------------------

    def init_tx(self, tx, cfg) -> None:
        self._lib.bdl_init_tx(tx, cfg)

    def init_rx(self, rx, cfg) -> None:
        self._lib.bdl_init_rx(rx, cfg)

    def string_get_nb(self, rx) -> int:
        """Returns the next string-channel byte as an int, or 256 if none available."""
        return self._lib.bdl_string_get_nb(rx)

    def string_get_bl(self, rx) -> int:
        """Returns the next string-channel byte as an int, or blocks if none available."""
        return ord(self._lib.bdl_string_get_bl(rx))

    def string_put_nb(self, tx, byte: int) -> bool:
        return self._lib.bdl_string_put_nb(tx, bytes([byte]))

    def string_put_bl(self, tx, byte: int) -> bool:
        """ blocks if buffer full - call with caution """
        return self._lib.bdl_string_put_bl(tx, bytes([byte]))

    def string_can_get(self, tx) -> bool:
        return self._lib.bdl_string_can_get(tx)

    def string_can_put(self, tx) -> bool:
        return self._lib.bdl_string_can_put(tx)

    def packet_init_buf(self, pkt, buf: ctypes.Array, length: int) -> None:
        self._lib.bdl_packet_init_buf(pkt, ctypes.cast(buf, ctypes.POINTER(ctypes.c_uint8)), length)

    def packet_set_chan(self, pkt, chan: int) -> None:
        self._lib.bdl_packet_set_chan(pkt, chan)

    def packet_set_len(self, pkt, length: int) -> None:
        self._lib.bdl_packet_set_len(pkt, length)

    def packet_listen(self, rx, pkt, callback=None) -> None:
        if callback is None:
            callback = ctypes.cast(None, PACKET_FUNC)
        self._lib.bdl_packet_listen(rx, pkt, callback)

    def packet_get(self, rx, pkt) -> bool:
        return self._lib.bdl_packet_get(rx, pkt)

    def packet_put(self, tx, pkt, callback=None) -> None:
        if callback is None:
            callback = ctypes.cast(None, PACKET_FUNC)
        self._lib.bdl_packet_put(tx, pkt, callback)

    def put_rx_byte(self, rx, byte: int) -> None:
        self._lib.bdl_put_rx_byte(rx, byte)

    def get_tx_byte(self, tx) -> int:
        return self._lib.bdl_get_tx_byte(tx)

    def get_error_count(self, rx) -> int:
        return self._lib.bdl_get_error_count(rx)

    def reset_error_count(self, rx) -> None:
        self._lib.bdl_reset_error_count(rx)

    # -- test-only introspection --------------------------------------------

    def packet_get_state(self, pkt) -> BdlPacketState:
        return BdlPacketState(self._lib.bdl_test_packet_get_state(pkt))

    def packet_get_chan(self, pkt) -> int:
        return self._lib.bdl_test_packet_get_chan(pkt)

    def packet_get_len(self, pkt) -> int:
        return self._lib.bdl_test_packet_get_len(pkt)

    def packet_read_data(self, pkt) -> bytes:
        length = self.packet_get_len(pkt)
        buf = (ctypes.c_uint8 * length)()
        self._lib.bdl_test_packet_read_data(pkt, buf, length)
        return bytes(buf)

    def crc_seed(self, header: int) -> int:
        """Returns bundle.c's internal per-channel CRC seed for the given
        header byte (0x80|chan). Test-only; used to verify bundle.c's seed
        formula matches bundle.py's _crc_seed() independently of any packet
        framing."""
        return self._lib.bdl_test_crc_seed(header)

    # -- CRC (operates on raw bytes; unaffected by the struct changes) -----

    def crc16_bitwise(self, seed: int, data: bytes) -> int:
        buf = (ctypes.c_uint8 * len(data)).from_buffer_copy(data)
        return self._lib.bdl_crc16_bitwise(seed, buf, len(data))

    def crc16_lookup(self, seed: int, data: bytes) -> int:
        buf = (ctypes.c_uint8 * len(data)).from_buffer_copy(data)
        return self._lib.bdl_crc16_lookup(seed, buf, len(data))
