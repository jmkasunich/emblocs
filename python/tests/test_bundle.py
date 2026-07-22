# test_bundle.py
from __future__ import annotations
import pytest
import ctypes
import random
import binascii
from conftest import register_callback, assert_process_aborts, TESTS_DIR, PYTHON_DIR
from bundle import Bundle, Unbundle, _cobs_encode, _cobs_decode
from bundle import _crc_seed as crc_seed
from bundle_capi import PACKET_FUNC, VOID_VOID_FUNC, BdlPacketState


#-----------------------------------------------------------------------
# Prefix to provide imports, etc., when running tests in a subprocess
#  (we run C tests that are supposed to assert() in a subprocess since
#   the assert will kill that process)
#-----------------------------------------------------------------------

_ASSERT_PREFIX = f'''
import ctypes, sys
sys.path.insert(0, {str(TESTS_DIR)!r})
sys.path.insert(0, {str(PYTHON_DIR)!r})

if sys.platform == "win32":
    # Suppress Windows Error Reporting for this process. Without this, a
    # real assert()-triggered abort() can cost several seconds of WER
    # background processing before control returns to the parent, even
    # though no dialog is ever visibly shown in this non-interactive
    # context. SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX.
    ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002)

from conftest import _bundle_dll_path
from bundle_capi import BundleCAPI, PACKET_FUNC, VOID_VOID_FUNC, CRC16_FUNC
from test_bundle import CPacket, CTx, CRx
lib = ctypes.CDLL(str(_bundle_dll_path()))
api = BundleCAPI(lib)
'''

def assert_c_aborts(setup: str, should_assert: str, expected_assert_text: str) -> None:
    """Bundle-specific wrapper: `setup`/`should_assert` have ctypes, api,
    and the shape constants already available via _ASSERT_PREFIX."""
    assert_process_aborts(_ASSERT_PREFIX, setup, should_assert, expected_assert_text)

#-----------------------------------------------------------------------
# Wrappers for some C API objects
#-----------------------------------------------------------------------

class CPacket:
    """
    Wrapper for bdl_packet_t structure.
    'pool' is optional but recommended; declare an empty dict at the
    start of a test, then pass it when creating a packet.  This serves
    two purposes:
      1) A packet address passed to a callback can be converted to
         the corresponding CPacket object by obj = pool[address]
      2) Packets in the pool will not be garbage collected until
         the pool is destroyed at the end of the tests - solves
         the lifetime problem.
    """
    def __init__(self, api, bufsize: int = 254, chan: int = None,
                  data: bytes = None, pool: dict | None = None):
        self.api = api
        self.pkt = self.api.new_packet()
        self.address = ctypes.addressof(self.pkt)
        assert bufsize >= 2 and bufsize <= 254
        self.bufsize = bufsize
        self.buf = (ctypes.c_uint8 * bufsize)()
        self.api.packet_init_buf(self.pkt, self.buf, bufsize)
        if chan is not None:
            self.set_chan(chan)
        if data is not None:
            self.write_data(data)
        if pool is not None:
            pool[self.address] = self

    @property
    def state(self):
        return self.api.packet_get_state(self.pkt)

    @property
    def length(self):
        return self.api.packet_get_len(self.pkt)

    @property
    def chan(self):
        return self.api.packet_get_chan(self.pkt)

    def set_length(self, length: int):
        self.api.packet_set_len(self.pkt, length)

    def set_chan(self, chan: int):
        self.api.packet_set_chan(self.pkt, chan)

    def write_data(self, data: bytes):
        assert len(data) <= self.bufsize - 2
        for i, v in enumerate(data):
            self.buf[i] = v
        self.set_length(len(data))

    def read_data(self) -> bytes:
        return self.api.packet_read_data(self.pkt)

class CTx:
    """
    Wrapper for bdl_tx_t structure.  Creates the struct and the
    required string buffer (of the specified size).  Calls
    bdl_init_tx() with the specified callbacks.
    'pool' is optional but recommended; declare an empty dict at the
    start of a test, then pass it when creating an object.  This serves
    two purposes:
      1) An object address passed to a callback can be converted to
         the corresponding CTx object by obj = pool[address]
      2) Objects in the pool will not be garbage collected until
         the pool is destroyed at the end of the tests - solves
         the lifetime problem.
    """
    def __init__(self, api, string_bufsize: int, crc_funct=None,
                  string_not_full_funct=None, tx_bytes_available_funct=None,
                  pool: dict | None = None):
        self.api = api
        self.tx = self.api.new_tx()
        self.address = ctypes.addressof(self.tx)
        assert string_bufsize >= 2
        self.strbufsize = string_bufsize
        self.strbuf = ctypes.create_string_buffer(string_bufsize)
        self.crc16 = crc_funct if crc_funct is not None else api.crc16_lookup_ptr
        self.snf_cb = register_callback(VOID_VOID_FUNC, string_not_full_funct, pool)
        self.tba_cb = register_callback(VOID_VOID_FUNC, tx_bytes_available_funct, pool)
        self.config = self.api.make_tx_config(self.strbuf, self.strbufsize, self.crc16,
                                              self.tba_cb, self.snf_cb)
        self.api.init_tx(self.tx, self.config)
        if pool is not None:
            pool[self.address] = self

    def string_put_nb(self, byte: int) -> bool:
        return self.api.string_put_nb(self.tx, byte)

    def string_can_put(self) -> bool:
        return self.api.string_can_put(self.tx)

    def packet_put(self, packet: CPacket, registered_callback=None):
        self.api.packet_put(self.tx, packet.pkt, registered_callback)

    def get_tx_byte(self) -> int:
        return self.api.get_tx_byte(self.tx)

    def get_tx_bytes(self) -> bytes:
        out = bytearray()
        while 1:
            b = self.api.get_tx_byte(self.tx)
            if b > 255:
                return bytes(out)
            out.append(b)

class CRx:
    """
    Wrapper for bdl_rx_t structure.  Creates the struct and the
    required string buffer (of the specified size).  Calls
    bdl_init_tx() with the specified callbacks.
    'pool' is optional but recommended; declare an empty dict at the
    start of a test, then pass it when creating an object.  This serves
    two purposes:
      1) An object address passed to a callback can be converted to
         the corresponding CRx object by obj = pool[address]
      2) Objects in the pool will not be garbage collected until
         the pool is destroyed at the end of the tests - solves
         the lifetime problem.
    """
    def __init__(self, api, string_bufsize: int, crc_funct=None,
                  string_avail_funct=None, pool: dict | None = None):
        self.api = api
        self.rx = self.api.new_rx()
        self.address = ctypes.addressof(self.rx)
        assert string_bufsize >= 2
        self.strbufsize = string_bufsize
        self.strbuf = ctypes.create_string_buffer(string_bufsize)
        self.crc16 = crc_funct if crc_funct is not None else api.crc16_lookup_ptr
        self.sa_cb = register_callback(VOID_VOID_FUNC, string_avail_funct, pool)
        self.config = self.api.make_rx_config(self.strbuf, self.strbufsize,
                                               self.crc16, self.sa_cb)
        self.api.init_rx(self.rx, self.config)
        if pool is not None:
            pool[self.address] = self

    def string_get_nb(self) -> int:
        return self.api.string_get_nb(self.rx)

    def string_can_get(self) -> bool:
        return self.api.string_can_get(self.rx)

    def packet_listen(self, packet: CPacket, registered_callback=None):
        self.api.packet_listen(self.rx, packet.pkt, registered_callback)

    def packet_get(self, packet: CPacket) -> bool:
        return self.api.packet_get(self.rx, packet.pkt)

    def put_rx_byte(self, byte: int):
        self.api.put_rx_byte(self.rx, byte)

    def put_rx_bytes(self, data: bytes):
        for b in data:
            self.api.put_rx_byte(self.rx, b)


#-----------------------------------------------------------------------
# Low-level tests of seed generation and CRC computation
#-----------------------------------------------------------------------

def test_crc_seed_matches_python(bundle_api):
    seeds = {}
    for chan in range(128):
        seed_py = crc_seed(chan)
        seed_c  =bundle_api.crc_seed(chan)
        # C and Python must get the same key
        assert seed_py == seed_c
        # all zeros is a bad key for CRC-16
        assert seed_py != 0
        # not strictly required - aiming for some amount of entropy
        assert seed_py.bit_count() >= 4
        assert seed_py.bit_count() <= 12
        # all seeds should be unique
        assert seed_py not in seeds, (
            f"channels {chan:#06x} and {seeds[seed_py]:#06x} produced same seed: {seed_py:#06x}"
        )
        seeds[seed_py] = chan


CRC_VECTORS = [
    # (seed, expected_crc, name) -- two independently published CRC-16
    # parameterizations sharing the same polynomial (0x1021) and framing
    # (no reflection) but different standard seeds, both computed over
    # the ASCII string "123456789". Using two seeds, not just one,
    # specifically catches an implementation that accepts a seed
    # argument but silently ignores it in favor of a hardcoded value
    pytest.param(0xFFFF, 0x29B1, id="CCITT-FALSE"),
    pytest.param(0x1D0F, 0xE5CC, id="AUG-CCITT"),
]

@pytest.mark.parametrize("seed, expected", CRC_VECTORS)
def test_crc16_python_against_published_vectors(seed, expected):
    assert binascii.crc_hqx(b"123456789", seed) == expected

@pytest.mark.parametrize("seed, expected", CRC_VECTORS)
def test_crc16_bitwise_against_published_vectors(bundle_api, seed, expected):
    assert bundle_api.crc16_bitwise(seed, b"123456789") == expected

@pytest.mark.parametrize("seed, expected", CRC_VECTORS)
def test_crc16_lookup_against_published_vectors(bundle_api, seed, expected):
    assert bundle_api.crc16_lookup(seed, b"123456789") == expected

def test_crc16_implementations_agree_across_all_channel_seeds(bundle_api):
    """
    Confirm bitwise, lookup, and Python implementations agree across
    every seed Bundle actually uses in real operation -- one per
    channel, 128 total. Neither published vector touches this seed
    space at all (both use non-Bundle seeds).  Fixed payload; see
    test_crc16_implementations_agree_random_data for payload variation.
    """
    data = b"a representative packet payload, arbitrary content"
    crcs = {}
    for chan in range(128):
        seed = crc_seed(chan)
        bw = bundle_api.crc16_bitwise(seed, data)
        lk = bundle_api.crc16_lookup(seed, data)
        py = binascii.crc_hqx(data, seed)
        assert bw == lk == py, (
            f"mismatch at chan={chan} seed={seed:#06x}: "
            f"bitwise={bw:#06x} lookup={lk:#06x} python={py:#06x}"
        )
        # for a fixed message, CRC-16-CCITT (unreflected) is a linear,
        # invertible function of the seed, so distinct seeds are
        # guaranteed to produce distinct CRCs -- any collision
        # indicates a bug (duplicate seed or broken CRC linearity)
        assert py not in crcs, (
            f"seeds {seed:#06x} and {crcs[py]:#06x} produced same crc: {py:#06x}"
        )
        crcs[py] = seed

def test_crc16_implementations_agree_random_data(bundle_api):
    """
    Confirm bitwise, lookup, and Python implementations agree across a
    broad sample of random payloads. The two published vectors only
    exercise a handful of the lookup table's 256 entries (which entries
    get touched depends on the running CRC state, not just the raw
    input bytes); this exercises a much larger fraction, at realistic
    packet lengths. Fixed, seeded RNG for reproducibility. One seed;
    see test_crc16_implementations_agree_across_all_channel_seeds
    for seed variation.
    """
    rng = random.Random(1234)
    seed = crc_seed(5)
    for _ in range(300):
        length = rng.randint(0, 252)
        data = bytes(rng.randint(0, 255) for _ in range(length))
        bw = bundle_api.crc16_bitwise(seed, data)
        lk = bundle_api.crc16_lookup(seed, data)
        py = binascii.crc_hqx(data, seed)
        assert bw == lk == py, (
            f"mismatch at length={length}: "
            f"bitwise={bw:#06x} lookup={lk:#06x} python={py:#06x}"
        )


#-----------------------------------------------------------------------
# Low-level tests of COBS encode/decode
#  this tests the Python implementation
#  the C implementation is inlined and not directly testable
#  but is validated by C->Python and Python->C packet testing later
#-----------------------------------------------------------------------

COBS_VECTORS = [
    pytest.param(bytes.fromhex("00"), bytes.fromhex("0101"), id="single_zero"),
    pytest.param(bytes.fromhex("03"), bytes.fromhex("0203"), id="single_nonzero"),
    pytest.param(bytes.fromhex("0000"), bytes.fromhex("010101"), id="two_zeros"),
    pytest.param(bytes.fromhex("0204"), bytes.fromhex("030204"), id="two_nonzeros"),
    pytest.param(bytes.fromhex("0005"), bytes.fromhex("010205"), id="zero_nonzero"),
    pytest.param(bytes.fromhex("0500"), bytes.fromhex("020501"), id="nonzero_zero"),
    pytest.param(bytes.fromhex("001100"), bytes.fromhex("01021101"), id="zero_data_zero"),
    pytest.param(bytes.fromhex("00223344"), bytes.fromhex("0104223344"), id="leading_zero"),
    pytest.param(bytes.fromhex("11220033"), bytes.fromhex("0311220233"), id="interior_zero"),
    pytest.param(bytes.fromhex("11223344"), bytes.fromhex("0511223344"), id="no_zeros"),
    pytest.param(bytes.fromhex("11223300"), bytes.fromhex("0411223301"), id="trailing_zero"),
    pytest.param(bytes(range(1, 255)), bytes([0xFF]) + bytes(range(1, 255)), id="max_length_no_zeros"),
    pytest.param(bytes(range(1, 100))+bytes([0x00])+bytes(range(101, 255)),
                 bytes([100])+bytes(range(1, 100))+bytes([155])+bytes(range(101,255)), id="max_length_with_zero"),
    pytest.param(bytes([0x00] * 254), bytes([0x01] * 255), id="max_length_all_zeros"),
]

@pytest.mark.parametrize("data, expected", COBS_VECTORS)
def test_cobs_encode_matches_published_vectors(data, expected):
    assert _cobs_encode(data) == expected

@pytest.mark.parametrize("data, expected", COBS_VECTORS)
def test_cobs_decode_matches_published_vectors(data, expected):
    assert _cobs_decode(expected) == data

#-----------------------------------------------------------------------
# Helper function to make a packet in wire format
#-----------------------------------------------------------------------

def make_packet_wire_bytes(payload: bytes, chan: int) -> bytes:
    crc = binascii.crc_hqx(payload, crc_seed(chan))
    crcbytes = bytes([crc & 0xFF, (crc >> 8) & 0xFF])
    header = 0x80 + chan
    return bytes([header]) + _cobs_encode(payload + crcbytes) + bytes([0x00])


#-----------------------------------------------------------------------
# Basic Transmit Tests
#-----------------------------------------------------------------------

def test_c_string_transmit(bundle_api, c_object_pool):
    api = bundle_api
    tx = CTx(api, 100, pool=c_object_pool)
    test_string = "this is a nice long test string that C won't split into chunks"
    test_bytes = test_string.encode('ascii')
    for b in test_bytes:
        assert tx.string_put_nb(b)
    wire_bytes = tx.get_tx_bytes()
    assert wire_bytes == test_bytes

def test_py_string_transmit():
    tx = Bundle()
    test_string = "this is a nice long test string that should get split into chunks"
    test_bytes = test_string.encode('ascii')
    tx.send_string(test_string)
    wire_bytes = bytearray()
    while 1:
        b = tx.get_tx_bytes()
        if b == b'':
            break
        wire_bytes.extend(b)
    wire_bytes = bytes(wire_bytes)
    assert wire_bytes == test_bytes

def test_c_packet_transmit(bundle_api, c_object_pool):
    api = bundle_api
    pkt = CPacket(api, bufsize=12, pool=c_object_pool)
    chan = 5
    payload = bytes([0x11, 0x00, 0xFF, 0x32, 0x00, 0x33])
    pkt.set_chan(chan)
    pkt.write_data(payload)
    expected = make_packet_wire_bytes(payload, chan)
    tx = CTx(api, 100, pool=c_object_pool)
    tx.packet_put(pkt)
    assert pkt.state == BdlPacketState.BP_TX_WAIT
    wire_bytes = tx.get_tx_bytes()
    assert pkt.state == BdlPacketState.BP_IDLE
    assert len(wire_bytes) == len(payload) + 5 # header, COBS byte, 2 CRC, terminator
    assert 0x00 not in wire_bytes[0:-1]  # validate COBS encoding
    assert wire_bytes == expected

def test_py_packet_transmit():
    chan = 5
    payload = bytes([0x11, 0x00, 0xFF, 0x32, 0x00, 0x33])
    expected = make_packet_wire_bytes(payload, chan)

    tx = Bundle()
    tx.send_packet(chan, payload)
    wire_bytes = bytearray()
    while 1:
        b = tx.get_tx_bytes()
        if b == b'':
            break
        wire_bytes.extend(b)
    wire_bytes = bytes(wire_bytes)
    assert len(wire_bytes) == len(payload) + 5 # header, COBS byte, 2 CRC, terminator
    assert 0x00 not in wire_bytes[0:-1]  # validate COBS encoding
    assert wire_bytes == expected


#-----------------------------------------------------------------------
# Basic Receive Tests
#-----------------------------------------------------------------------


def test_c_string_receive(bundle_api, c_object_pool):
    api = bundle_api
    rx = CRx(api, 100, pool=c_object_pool)
    test_string = "this is a test string"
    wire_bytes = test_string.encode('ascii')
    for b in wire_bytes:
        rx.put_rx_byte(b)
    received_bytes = bytearray()
    while 1:
        b = rx.string_get_nb();
        if b == 256:
            break
        received_bytes.append(b)
    received_string = received_bytes.decode('ascii')
    assert received_string == test_string

def test_py_string_receive():
    received_strings = []
    def string_callback(string: str):
        nonlocal received_strings
        received_strings.append(string)
    rx = Unbundle()
    test_string = "this is a test string"
    wire_bytes = test_string.encode('ascii')
    rx.listen_string(string_callback)
    rx.put_rx_bytes(wire_bytes)
    received_string = ''.join(received_strings)
    assert received_string == test_string

def test_c_packet_receive(bundle_api, c_object_pool):
    api = bundle_api
    pkt = CPacket(api, bufsize=12, pool=c_object_pool)
    chan = 5
    payload = bytes([0x11, 0x00, 0xFF, 0x32, 0x00, 0x33])
    wire_bytes = make_packet_wire_bytes(payload, chan)
    pkt.set_chan(chan)
    rx = CRx(api, 100, pool=c_object_pool)
    rx.packet_listen(pkt)
    assert pkt.state == BdlPacketState.BP_RX_WAIT
    rx.put_rx_bytes(wire_bytes)
    assert pkt.state == BdlPacketState.BP_RX_DONE
    assert rx.packet_get(pkt)
    assert pkt.state == BdlPacketState.BP_IDLE
    assert pkt.length == len(payload)
    assert pkt.chan == chan
    data = pkt.read_data()
    assert data == payload

def test_py_packet_receive():
    chan = 5
    payload = bytes([0x11, 0x00, 0xFF, 0x32, 0x00, 0x33])
    wire_bytes = make_packet_wire_bytes(payload, chan)
    received_chan = -1
    received_data = bytes(0)
    def packet_callback(chan: int, data: bytes):
        nonlocal received_chan
        nonlocal received_data
        received_chan = chan
        received_data = data
    rx = Unbundle()
    rx.listen_packet(chan, packet_callback)
    rx.put_rx_bytes(wire_bytes)
    assert received_chan == chan
    assert received_data == payload


#-----------------------------------------------------------------------
# fatal error handling - bdl_packet_t
#-----------------------------------------------------------------------


def test_c_packet_init_buf_asserts_when_null(bundle_api):
    assert_c_aborts(
        setup='',
        should_assert='api.packet_init_buf(None, None, 32)',
        expected_assert_text='p != NULL',
    )

def test_c_packet_init_buf_asserts_when_buf_null(bundle_api):
    assert_c_aborts(
        setup='pkt = api.new_packet()',
        should_assert='api.packet_init_buf(pkt, None, 32)',
        expected_assert_text='buf != NULL',
    )

def test_c_packet_init_buf_asserts_buf_too_small(bundle_api):
    assert_c_aborts(
        setup=
        '''
        pkt = api.new_packet()
        buf = (ctypes.c_uint8 * 254)()
        ''',
        should_assert='api.packet_init_buf(pkt, buf, 1)',
        expected_assert_text='len >= 2',
    )

def test_c_packet_init_buf_asserts_buf_too_large(bundle_api):
    assert_c_aborts(
        setup=
        '''
        pkt = api.new_packet()
        buf = (ctypes.c_uint8 * 254)()
        ''',
        should_assert='api.packet_init_buf(pkt, buf, 255)',
        expected_assert_text='len <= 254',
    )

def test_c_packet_set_chan_asserts_when_null(bundle_api):
    assert_c_aborts(
        setup='',
        should_assert='api.packet_set_chan(None, 5)',
        expected_assert_text='p != NULL',
    )

def test_c_packet_set_chan_asserts_when_not_idle(bundle_api):
    assert_c_aborts(setup=
        '''
        pool = {}
        pkt = CPacket(api, chan=5, data=b"abc", pool=pool)
        tx = CTx(api, 100, pool=pool)
        tx.packet_put(pkt)
        ''',
        should_assert= 'pkt.set_chan(6)',
        expected_assert_text='p->state == BP_IDLE'
    )

def test_c_packet_set_chan_asserts_bad_chan(bundle_api):
    assert_c_aborts(setup=
        '''
        pool = {}
        pkt = CPacket(api, chan=5, data=b"abc", pool=pool)
        ''',
        should_assert= 'pkt.set_chan(128)',
        expected_assert_text='chan <= MAX_CHAN'
    )

def test_c_packet_set_len_asserts_when_null(bundle_api):
    assert_c_aborts(
        setup='',
        should_assert='api.packet_set_len(None, 5)',
        expected_assert_text='p != NULL',
    )

def test_c_packet_set_len_asserts_when_not_idle(bundle_api):
    assert_c_aborts(setup=
        '''
        pool = {}
        pkt = CPacket(api, chan=5, data=b"abc", pool=pool)
        tx = CTx(api, 100, pool=pool)
        tx.packet_put(pkt)
        ''',
        should_assert= 'pkt.set_length(6)',
        expected_assert_text='p->state == BP_IDLE'
    )

def test_c_packet_set_len_asserts_bad_length(bundle_api):
    assert_c_aborts(setup=
        '''
        pool = {}
        pkt = CPacket(api, chan=5, bufsize=20, data=b"abc", pool=pool)
        ''',
        should_assert= 'pkt.set_length(19)',
        expected_assert_text='len <= (p->buf_len - 2)'
    )


#-----------------------------------------------------------------------
# fatal error handling - bdl_tx_t
#-----------------------------------------------------------------------

def test_c_tx_init_tx_asserts_when_null(bundle_api):
    assert_c_aborts(
        setup='',
        should_assert='api.init_tx(None, None)',
        expected_assert_text='bdl != NULL',
    )

def test_c_tx_init_tx_asserts_when_config_null(bundle_api):
    assert_c_aborts(
        setup='tx = api.new_tx()',
        should_assert='api.init_tx(tx, None)',
        expected_assert_text='cfg != NULL',
    )

def test_c_tx_init_tx_asserts_when_string_buf_null(bundle_api):
    assert_c_aborts(
        setup='''
        tx = api.new_tx()
        cfg = api.make_tx_config(None, 64, api.crc16_lookup_ptr)
        ''',
        should_assert='api.init_tx(tx, cfg)',
        expected_assert_text='cfg->string_buf != NULL',
    )

def test_c_tx_init_tx_asserts_when_string_buf_size_too_small(bundle_api):
    assert_c_aborts(
        setup='''
        tx = api.new_tx()
        strbuf = ctypes.create_string_buffer(64)
        cfg = api.make_tx_config(strbuf, 1, api.crc16_lookup_ptr)
        ''',
        should_assert='api.init_tx(tx, cfg)',
        expected_assert_text='cfg->string_buf_size >= 2',
    )

def test_c_tx_init_tx_asserts_when_crc16_null(bundle_api):
    assert_c_aborts(
        setup='''
        tx = api.new_tx()
        strbuf = ctypes.create_string_buffer(64)
        null_crc16 = ctypes.cast(None, CRC16_FUNC)
        cfg = api.make_tx_config(strbuf, 64, null_crc16)
        ''',
        should_assert='api.init_tx(tx, cfg)',
        expected_assert_text='cfg->crc16 != NULL',
    )

def test_c_tx_string_put_nb_asserts_when_null(bundle_api):
    assert_c_aborts(
        setup='',
        should_assert='api.string_put_nb(None, 0x41)',
        expected_assert_text='bdl != NULL',
    )

def test_c_tx_string_put_bl_asserts_when_null(bundle_api):
    assert_c_aborts(
        setup='',
        should_assert='api.string_put_bl(None, 0x41)',
        expected_assert_text='bdl != NULL',
    )

def test_c_tx_string_can_put_asserts_when_null(bundle_api):
    assert_c_aborts(
        setup='',
        should_assert='api.string_can_put(None)',
        expected_assert_text='bdl != NULL',
    )

def test_c_tx_packet_put_asserts_when_null(bundle_api):
    assert_c_aborts(
        setup='',
        should_assert='api.packet_put(None, None, None)',
        expected_assert_text='bdl != NULL',
    )

def test_c_tx_packet_put_asserts_when_packet_null(bundle_api):
    assert_c_aborts(
        setup='tx = api.new_tx()',
        should_assert='api.packet_put(tx, None, None)',
        expected_assert_text='p != NULL',
    )

def test_c_tx_packet_put_asserts_when_packet_not_idle(bundle_api):
    assert_c_aborts(
        setup='''
        tx = api.new_tx()
        pkt = api.new_packet()
        ''',
        should_assert='api.packet_put(tx, pkt, None)',
        expected_assert_text='p->state == BP_IDLE',
    )

def test_c_tx_get_tx_byte_asserts_when_null(bundle_api):
    assert_c_aborts(
        setup='',
        should_assert='api.get_tx_byte(None)',
        expected_assert_text='bdl != NULL',
    )

def test_c_tx_get_tx_byte_asserts_when_not_ready(bundle_api):
    assert_c_aborts(
        setup='tx = api.new_tx()',
        should_assert='api.get_tx_byte(tx)',
        expected_assert_text='invalid state',
    )


#-----------------------------------------------------------------------
# fatal error handling - bdl_rx_t
#-----------------------------------------------------------------------

def test_c_rx_init_rx_asserts_when_null(bundle_api):
    assert_c_aborts(
        setup='',
        should_assert='api.init_rx(None, None)',
        expected_assert_text='bdl != NULL',
    )

def test_c_rx_init_rx_asserts_when_config_null(bundle_api):
    assert_c_aborts(
        setup='rx = api.new_rx()',
        should_assert='api.init_rx(rx, None)',
        expected_assert_text='cfg != NULL',
    )

def test_c_rx_init_rx_asserts_when_string_buf_null(bundle_api):
    assert_c_aborts(
        setup='''
        rx = api.new_rx()
        cfg = api.make_rx_config(None, 64, api.crc16_lookup_ptr)
        ''',
        should_assert='api.init_rx(rx, cfg)',
        expected_assert_text='cfg->string_buf != NULL',
    )

def test_c_rx_init_rx_asserts_when_string_buf_size_too_small(bundle_api):
    assert_c_aborts(
        setup='''
        rx = api.new_rx()
        strbuf = ctypes.create_string_buffer(64)
        cfg = api.make_rx_config(strbuf, 1, api.crc16_lookup_ptr)
        ''',
        should_assert='api.init_rx(rx, cfg)',
        expected_assert_text='cfg->string_buf_size >= 2',
    )

def test_c_rx_init_rx_asserts_when_crc16_null(bundle_api):
    assert_c_aborts(
        setup='''
        rx = api.new_rx()
        strbuf = ctypes.create_string_buffer(64)
        null_crc16 = ctypes.cast(None, CRC16_FUNC)
        cfg = api.make_rx_config(strbuf, 64, null_crc16)
        ''',
        should_assert='api.init_rx(rx, cfg)',
        expected_assert_text='cfg->crc16 != NULL',
    )

def test_c_rx_string_get_nb_asserts_when_null(bundle_api):
    assert_c_aborts(
        setup='',
        should_assert='api.string_get_nb(None)',
        expected_assert_text='bdl != NULL',
    )

def test_c_rx_string_get_bl_asserts_when_null(bundle_api):
    assert_c_aborts(
        setup='',
        should_assert='api.string_get_nb(None)',
        expected_assert_text='bdl != NULL',
    )

def test_c_rx_string_can_get_asserts_when_null(bundle_api):
    assert_c_aborts(
        setup='',
        should_assert='api.string_can_get(None)',
        expected_assert_text='bdl != NULL',
    )

def test_c_rx_packet_listen_asserts_when_null(bundle_api):
    assert_c_aborts(
        setup='',
        should_assert='api.packet_listen(None, None, None)',
        expected_assert_text='bdl != NULL',
    )

def test_c_rx_packet_listen_asserts_when_packet_null(bundle_api):
    assert_c_aborts(
        setup='rx = api.new_rx()',
        should_assert='api.packet_listen(rx, None, None)',
        expected_assert_text='p != NULL',
    )

def test_c_rx_packet_listen_asserts_when_packet_not_idle(bundle_api):
    assert_c_aborts(
        setup='''
        rx = api.new_rx()
        pkt = api.new_packet()
        ''',
        should_assert='api.packet_listen(rx, pkt, None)',
        expected_assert_text='p->state == BP_IDLE',
    )

def test_c_rx_packet_get_asserts_when_null(bundle_api):
    assert_c_aborts(
        setup='',
        should_assert='api.packet_get(None, None)',
        expected_assert_text='bdl != NULL',
    )

def test_c_rx_packet_get_asserts_when_packet_null(bundle_api):
    assert_c_aborts(
        setup='rx = api.new_rx()',
        should_assert='api.packet_get(rx, None)',
        expected_assert_text='p != NULL',
    )

def test_c_rx_packet_listen_asserts_when_packet_not_done(bundle_api):
    assert_c_aborts(
        setup='''
        rx = api.new_rx()
        pkt = api.new_packet()
        ''',
        should_assert='api.packet_get(rx, pkt)',
        expected_assert_text='p->state == BP_RX_DONE',
    )

def test_c_rx_put_rx_byte_asserts_when_null(bundle_api):
    assert_c_aborts(
        setup='',
        should_assert='api.put_rx_byte(None, 0x41)',
        expected_assert_text='bdl != NULL',
    )

def test_c_rx_put_rx_byte_asserts_when_not_ready(bundle_api):
    assert_c_aborts(
        setup='rx = api.new_rx()',
        should_assert='api.put_rx_byte(rx, 0x41)',
        expected_assert_text='invalid state',
    )

def test_c_rx_get_error_count_asserts_when_null(bundle_api):
    assert_c_aborts(
        setup='',
        should_assert='api.get_error_count(None)',
        expected_assert_text='bdl != NULL',
    )

def test_c_rx_reset_error_count_asserts_when_null(bundle_api):
    assert_c_aborts(
        setup='',
        should_assert='api.reset_error_count(None)',
        expected_assert_text='bdl != NULL',
    )

