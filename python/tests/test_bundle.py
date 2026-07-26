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

    @property
    def error_count(self) -> int:
        return self.api.get_error_count(self.rx)

    def reset_error_count(self) -> None:
        self.api.reset_error_count(self.rx)

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
# multi-packet tests
#-----------------------------------------------------------------------

def _event_recorder(pool):
    """
    Generic ordered event log spanning both callback shapes:
      - VOID_VOID_FUNC callbacks (string_avail, string_not_full,
        tx_bytes_available) record a caller-supplied string tag,
        since there's no argument to distinguish them by.
      - PACKET_FUNC callbacks record the CPacket object itself,
        resolved by address via 'pool' -- same trick as the list
        lifecycle tests.
    One shared list, appended to in real call order, means ordering
    between string and packet activity can be asserted directly
    rather than reconstructed from separate counters.
    """
    log = []
    def void_cb(tag):
        def _cb():
            log.append(tag)
        return _cb
    def packet_cb(addr):
        log.append(pool[addr])
    return log, void_cb, packet_cb


def test_c_rx_listener_list_lifecycle(bundle_api, c_object_pool):
    """
    Walks one receive listener list through its full lifecycle:
    unlistened channel against a full, non-empty list (exercises a
    head, a middle, and a tail node all failing to match in one
    search); a match requiring mid-list removal; two matches that
    drain the list to empty, one node at a time; and finally a search
    against a genuinely empty list.

    Registers two buffers on channel 5 and one on channel 6, in the
    order 5, 6, 5 -- producing the list [chan5_b, chan6, chan5_a]
    head-to-tail. Which specific buffer object catches a given
    channel-5 packet is deliberately never asserted: LIFO search order
    is a performance optimization (see add_pkt_to_rx_list's comment),
    not a documented contract. What the contract does promise is that
    both buffers eventually receive correct data, in wire order.
    """
    rx = CRx(bundle_api, string_bufsize=8, pool=c_object_pool)
    assert rx.error_count == 0
    log, _, cb = _event_recorder(c_object_pool)
    callback = register_callback(PACKET_FUNC, cb, c_object_pool)

    chan5_a = CPacket(bundle_api, chan=5, pool=c_object_pool)
    chan6   = CPacket(bundle_api, chan=6, pool=c_object_pool)
    chan5_b = CPacket(bundle_api, chan=5, pool=c_object_pool)
    chan5_buffers = {chan5_a, chan5_b}

    rx.packet_listen(chan5_a, callback)
    rx.packet_listen(chan6, callback)
    rx.packet_listen(chan5_b, callback)

    # --- unlistened channel against the full 3-node list: walks a
    # head, a middle, and a tail node, none of which match.
    rx.put_rx_bytes(make_packet_wire_bytes(b"nobody-home", chan=7))
    assert rx.error_count == 1
    assert log == []

    # --- middle removal: chan 6 sits between the two chan-5 buffers,
    # so matching it requires walking past a non-matching head and
    # unlinking from the middle. List drops from 3 nodes to 2.
    rx.put_rx_bytes(make_packet_wire_bytes(b"middle", chan=6))
    assert log == [chan6]
    assert chan6.state == BdlPacketState.BP_RX_DONE
    assert rx.packet_get(chan6) is True
    assert chan6.state == BdlPacketState.BP_IDLE
    assert chan6.read_data() == b"middle"
    assert chan5_a.state == BdlPacketState.BP_RX_WAIT
    assert chan5_b.state == BdlPacketState.BP_RX_WAIT
    # should be no additional errors
    assert rx.error_count == 1

    # --- first chan-5 delivery: 2 nodes -> 1. Not asserting which
    # buffer caught it -- see docstring.
    rx.put_rx_bytes(make_packet_wire_bytes(b"first-five", chan=5))
    assert len(log) == 2
    first_catcher = log[1]
    assert first_catcher in chan5_buffers
    assert first_catcher.state == BdlPacketState.BP_RX_DONE
    assert rx.packet_get(first_catcher) is True
    assert first_catcher.state == BdlPacketState.BP_IDLE
    assert first_catcher.read_data() == b"first-five"
    # should be no additional errors
    assert rx.error_count == 1

    # --- second chan-5 delivery: drains the sole remaining node,
    # emptying the list.
    rx.put_rx_bytes(make_packet_wire_bytes(b"second-five", chan=5))
    assert len(log) == 3
    second_catcher = log[2]
    assert second_catcher.state == BdlPacketState.BP_RX_DONE
    assert {first_catcher, second_catcher} == chan5_buffers
    assert second_catcher is not first_catcher
    assert rx.packet_get(second_catcher) is True
    assert second_catcher.state == BdlPacketState.BP_IDLE
    assert second_catcher.read_data() == b"second-five"
    # should be no additional errors
    assert rx.error_count == 1

    # --- third chan-5 packet against a genuinely empty list: the
    # zero-iteration boundary, distinct from "walked and found nothing".
    errors_before = rx.error_count
    rx.put_rx_bytes(make_packet_wire_bytes(b"nobody-left", chan=5))
    assert rx.error_count == 2
    assert len(log) == 3

    # handy plate to test the error reset mechanism
    rx.reset_error_count()
    assert rx.error_count == 0


def test_c_tx_list_strict_fifo(bundle_api, c_object_pool):
    """
    Queues three packets before draining any of them. FIFO ordering
    can only be verified this way -- draining after each individual
    put would never exercise 'insert into a non-empty tail' more than
    once before a removal happens.
    """
    tx = CTx(bundle_api, string_bufsize=8, pool=c_object_pool)
    log, _, cb = _event_recorder(c_object_pool)
    callback = register_callback(PACKET_FUNC, cb, c_object_pool)

    p1 = CPacket(bundle_api, chan=1, data=b"first", pool=c_object_pool)
    p2 = CPacket(bundle_api, chan=1, data=b"second", pool=c_object_pool)
    p3 = CPacket(bundle_api, chan=1, data=b"third", pool=c_object_pool)

    assert all(p.state == BdlPacketState.BP_IDLE for p in (p1, p2, p3))
    expected = b"".join(make_packet_wire_bytes(payload, chan=1) for payload in [b"first", b"second", b"third"])

    tx.packet_put(p1, callback)
    tx.packet_put(p2, callback)
    tx.packet_put(p3, callback)
    assert all(p.state == BdlPacketState.BP_TX_WAIT for p in (p1, p2, p3))

    wire = tx.get_tx_bytes()  # drains all three; callbacks fire as each completes

    assert all(p.state == BdlPacketState.BP_IDLE for p in (p1, p2, p3))
    assert log == [p1, p2, p3]
    assert wire == expected


def test_c_tx_list_empty_then_refill(bundle_api, c_object_pool):
    """
    Drains a single queued packet down to an empty list (exercising
    the tail-pointer reset back to &pkt_root), then immediately
    re-queues that same buffer plus a second one, confirming the tail
    pointer is still correct for appends after an empty-list reset --
    the specific transition most head/tail queue bugs live in.
    """
    tx = CTx(bundle_api, string_bufsize=8, pool=c_object_pool)
    log, _, cb = _event_recorder(c_object_pool)
    callback = register_callback(PACKET_FUNC, cb, c_object_pool)

    p1 = CPacket(bundle_api, chan=2, data=b"round-one", pool=c_object_pool)
    tx.packet_put(p1, callback)
    assert p1.state == BdlPacketState.BP_TX_WAIT
    tx.get_tx_bytes()
    assert log == [p1]
    assert p1.state == BdlPacketState.BP_IDLE

    # buffer is idle again -- reuse it, and add a second packet behind it
    p1.write_data(b"round-two")
    p2 = CPacket(bundle_api, chan=3, data=b"newcomer", pool=c_object_pool)
    tx.packet_put(p1, callback)
    tx.packet_put(p2, callback)
    tx.get_tx_bytes()

    assert log == [p1, p1, p2]

def test_c_rx_string_avail_callback(bundle_api, c_object_pool):
    """
    string_avail() fires once per byte actually stored by put_rx_byte()
    -- unconditionally, per successful store, not edge-triggered on an
    empty-to-nonempty transition -- and must NOT fire for a byte that's
    silently dropped because the buffer is full.
    """
    log, void_cb, _ = _event_recorder(c_object_pool)
    rx = CRx(bundle_api, string_bufsize=4, string_avail_funct=void_cb('avail'), pool=c_object_pool)

    rx.put_rx_bytes(b"abc")
    assert log == ['avail'] * 3
    assert [rx.string_get_nb() for _ in range(3)] == [ord('a'), ord('b'), ord('c')]

    rx.put_rx_bytes(b"wxyz")
    assert log == ['avail'] * 7

    rx.put_rx_byte(ord('Q'))  # buffer full -- dropped, no callback
    assert log == ['avail'] * 7
    assert [rx.string_get_nb() for _ in range(4)] == [ord(c) for c in "wxyz"]
    assert not rx.string_can_get()


def test_c_tx_string_not_full_callback(bundle_api, c_object_pool):
    """
    string_not_full() fires once per byte actually consumed by
    get_tx_byte() -- not on put(), not when there's nothing to send,
    and not while a packet is draining.
    """
    log, void_cb, _ = _event_recorder(c_object_pool)
    tx = CTx(bundle_api, string_bufsize=8, string_not_full_funct=void_cb('snf'), pool=c_object_pool)

    for ch in b"hi":
        tx.string_put_nb(ch)
    assert log == []  # put_nb() never touches this callback

    assert tx.get_tx_byte() == ord('h')
    assert log == ['snf']
    assert tx.get_tx_byte() == ord('i')
    assert log == ['snf', 'snf']

    assert tx.get_tx_byte() > 255  # BDL_NO_DATA
    assert log == ['snf', 'snf']

    pkt = CPacket(bundle_api, chan=3, data=b"xyz", pool=c_object_pool)
    tx.packet_put(pkt)
    wire = tx.get_tx_bytes()
    assert wire == make_packet_wire_bytes(b"xyz", chan=3)
    assert log == ['snf', 'snf']  # unchanged

def test_c_tx_mixed_string_packet_priority(bundle_api, c_object_pool):
    """
    Queues string and packet data in strictly alternating put order
    (string, packet, string, packet, string, packet), then drains
    everything with get_tx_bytes(). Confirms put order has no bearing
    on transmit order -- packets always win, regardless of when they
    were queued relative to string data -- and that once queued, every
    packet fully drains (COBS byte through terminator, firing its
    completion callback) before any string byte is ever emitted.
    """
    log, void_cb, packet_cb = _event_recorder(c_object_pool)
    tx = CTx(bundle_api, string_bufsize=32, string_not_full_funct=void_cb('snf'),
             pool=c_object_pool)
    callback = register_callback(PACKET_FUNC, packet_cb, c_object_pool)

    packets = [
        (CPacket(bundle_api, chan=1, data=b"one", pool=c_object_pool), b"one", 1),
        (CPacket(bundle_api, chan=2, data=b"two", pool=c_object_pool), b"two", 2),
        (CPacket(bundle_api, chan=3, data=b"three", pool=c_object_pool), b"three", 3),
    ]
    strings = [b"aa", b"bb", b"cc"]

    for (pkt, _, _), s in zip(packets, strings):
        for ch in s:
            tx.string_put_nb(ch)
        tx.packet_put(pkt, callback)

    wire = tx.get_tx_bytes()

    expected_wire = b"".join(make_packet_wire_bytes(payload, chan) for _, payload, chan in packets)
    expected_wire += b"".join(strings)
    assert wire == expected_wire

    expected_log = [pkt for pkt, _, _ in packets] + ['snf'] * sum(len(s) for s in strings)
    assert log == expected_log


def test_c_rx_mixed_string_packet_priority(bundle_api, c_object_pool):
    """
    Feeds a wire stream containing three complete packets followed by
    string data -- the same shape bdl_get_tx_byte() naturally produces
    when both are queued, per the TX test above -- into a receiver.
    Confirms packets are delivered in wire order with correct
    payloads, followed by string bytes arriving in order with
    string_avail() firing once per byte.
    """
    log, void_cb, packet_cb = _event_recorder(c_object_pool)
    rx = CRx(bundle_api, string_bufsize=32, string_avail_funct=void_cb('avail'),
             pool=c_object_pool)
    callback = register_callback(PACKET_FUNC, packet_cb, c_object_pool)

    chans_payloads = [(1, b"one"), (2, b"two"), (3, b"three")]
    listeners = []
    for chan, _ in chans_payloads:
        p = CPacket(bundle_api, chan=chan, pool=c_object_pool)
        rx.packet_listen(p, callback)
        listeners.append(p)

    strings = [b"aa", b"bb", b"cc"]
    wire = b"".join(make_packet_wire_bytes(payload, chan) for chan, payload in chans_payloads)
    wire += b"".join(strings)

    rx.put_rx_bytes(wire)

    total_chars = sum(len(s) for s in strings)
    assert log == listeners + ['avail'] * total_chars

    for p, (_, payload) in zip(listeners, chans_payloads):
        assert p.state == BdlPacketState.BP_RX_DONE
        assert rx.packet_get(p) is True
        assert p.read_data() == payload

    received = bytes(rx.string_get_nb() for _ in range(total_chars))
    assert received == b"".join(strings)
    assert not rx.string_can_get()


def test_c_tx_bytes_available_callback(bundle_api, c_object_pool):
    """
    tx_bytes_available() is the hardware-side "wake up and start
    pumping bytes" signal, distinct from string_not_full() (the
    API-user-side "there's now room to put more" signal). It fires
    once per successful string_put_nb()/put_bl() call -- never on a
    failed (buffer-full) put_nb() -- and once per packet_put() call,
    unconditionally.
    """
    log, void_cb, _ = _event_recorder(c_object_pool)
    tx = CTx(bundle_api, string_bufsize=4, tx_bytes_available_funct=void_cb('tba'),
             pool=c_object_pool)

    assert tx.string_put_nb(ord('a')) is True
    assert log == ['tba']
    assert tx.string_put_nb(ord('b')) is True
    assert tx.string_put_nb(ord('c')) is True
    assert tx.string_put_nb(ord('d')) is True
    assert log == ['tba'] * 4  # buffer (size 4) now full

    # buffer full -- put_nb must fail and must NOT fire
    assert tx.string_put_nb(ord('e')) is False
    assert log == ['tba'] * 4

    # drain one byte to free a slot, confirming the prior non-fire was
    # a real rejection, not a fluke
    assert tx.get_tx_byte() == ord('a')
    assert tx.string_put_nb(ord('e')) is True
    assert log == ['tba'] * 5

    # packet_put fires exactly once per call, regardless of payload
    pkt = CPacket(bundle_api, chan=7, data=b"hello world", pool=c_object_pool)
    tx.packet_put(pkt)
    assert log == ['tba'] * 6


#-----------------------------------------------------------------------
# Python: Multiple string / multiple packet / mixed priority tests
#-----------------------------------------------------------------------

def test_py_string_transmit_multiple_calls():
    """
    Two separate send_string() calls, each shorter than
    STRING_CHUNK_LEN, must not have their chunks merged -- each call
    starts its own chunking at its own byte 0, independent of any
    previous call's leftover partial chunk.
    """
    tx = Bundle()
    tx.send_string("short one")
    tx.send_string("short two")
    wire_bytes = bytearray()
    while True:
        b = tx.get_tx_bytes()
        if b == b'':
            break
        wire_bytes.extend(b)
    assert bytes(wire_bytes) == b"short one" + b"short two"


def test_py_packet_transmit_multiple():
    """
    Three send_packet() calls, drained via repeated get_tx_bytes(),
    must emerge in strict FIFO submission order -- checked against
    independently-computed reference frames.
    """
    tx = Bundle()
    packets = [(1, b"one"), (2, b"two"), (3, b"three")]
    for chan, payload in packets:
        tx.send_packet(chan, payload)

    wire_bytes = bytearray()
    while True:
        b = tx.get_tx_bytes()
        if b == b'':
            break
        wire_bytes.extend(b)

    expected = b"".join(make_packet_wire_bytes(payload, chan) for chan, payload in packets)
    assert bytes(wire_bytes) == expected


def test_py_mixed_string_packet_priority_transmit():
    """
    Strictly alternating send_string()/send_packet() calls, queued in
    that order, then fully drained. Confirms put order has no bearing
    on transmit order: every queued packet comes first (FIFO among
    themselves), followed by every queued string chunk (FIFO among
    themselves) -- same static-priority shape as the C TX test.
    """
    tx = Bundle()
    packets = [(1, b"one"), (2, b"two"), (3, b"three")]
    strings = ["aa", "bb", "cc"]

    for (chan, payload), s in zip(packets, strings):
        tx.send_string(s)
        tx.send_packet(chan, payload)

    wire_bytes = bytearray()
    while True:
        b = tx.get_tx_bytes()
        if b == b'':
            break
        wire_bytes.extend(b)

    expected = b"".join(make_packet_wire_bytes(payload, chan) for chan, payload in packets)
    expected += "".join(strings).encode('ascii')
    assert bytes(wire_bytes) == expected


def test_py_packet_receive_multiple_channels():
    """
    Three channels registered, three packets delivered in one
    put_rx_bytes() call; callbacks must fire in wire order.
    """
    received = []
    def cb(chan, payload):
        received.append((chan, payload))

    rx = Unbundle()
    chans_payloads = [(1, b"one"), (2, b"two"), (3, b"three")]
    for chan, _ in chans_payloads:
        rx.listen_packet(chan, cb)

    wire = b"".join(make_packet_wire_bytes(payload, chan) for chan, payload in chans_payloads)
    rx.put_rx_bytes(wire)

    assert received == chans_payloads


def test_py_mixed_string_packet_priority_receive():
    """
    Feeds string/packet/string/packet/string/packet segments in one
    put_rx_bytes() call. Packet callbacks fire in wire order, as each
    completes -- but per the documented contract, the string callback
    fires only ONCE, just before put_rx_bytes() returns, with all
    string segments from the call concatenated in encounter order --
    regardless of how many separate segments were interspersed with
    packets. Deliberate difference from bundle.c's string_avail(),
    which fires once per byte in real time.
    """
    log = []
    def packet_cb(chan, payload):
        log.append(('packet', chan, payload))
    def string_cb(s):
        log.append(('string', s))

    rx = Unbundle()
    chans_payloads = [(1, b"one"), (2, b"two"), (3, b"three")]
    for chan, _ in chans_payloads:
        rx.listen_packet(chan, packet_cb)
    rx.listen_string(string_cb)

    strings = ["aa", "bb", "cc"]
    wire = b""
    for (chan, payload), s in zip(chans_payloads, strings):
        wire += s.encode('ascii')
        wire += make_packet_wire_bytes(payload, chan)

    rx.put_rx_bytes(wire)

    assert log == [
        ('packet', 1, b"one"),
        ('packet', 2, b"two"),
        ('packet', 3, b"three"),
        ('string', "aabbcc"),
    ]


#-----------------------------------------------------------------------
# Python: API contract tests -- send_packet, listen/unlisten
#-----------------------------------------------------------------------

def test_py_send_packet_bad_channel_raises():
    tx = Bundle()
    with pytest.raises(ValueError):
        tx.send_packet(-1, b"data")
    with pytest.raises(ValueError):
        tx.send_packet(128, b"data")
    # boundary values must NOT raise
    tx.send_packet(0, b"data")
    tx.send_packet(127, b"data")


def test_py_send_packet_data_too_long_raises():
    tx = Bundle()
    with pytest.raises(ValueError):
        tx.send_packet(5, bytes(253))
    # boundary value must NOT raise
    tx.send_packet(5, bytes(252))


def test_py_listen_string_none_callback_raises():
    rx = Unbundle()
    with pytest.raises(ValueError):
        rx.listen_string(None)


def test_py_listen_string_duplicate_raises():
    rx = Unbundle()
    rx.listen_string(lambda s: None)
    with pytest.raises(ValueError):
        rx.listen_string(lambda s: None)


def test_py_unlisten_string_allows_relisten():
    received = []
    rx = Unbundle()
    rx.listen_string(lambda s: None)
    rx.unlisten_string()
    # a second unlisten_string(), with no active listener, must not raise
    rx.unlisten_string()
    # now a fresh listen_string() must succeed, and actually work
    rx.listen_string(lambda s: received.append(s))
    rx.put_rx_bytes(b"hello")
    assert received == ["hello"]


def test_py_listen_packet_bad_channel_raises():
    rx = Unbundle()
    cb = lambda chan, data: None
    with pytest.raises(ValueError):
        rx.listen_packet(-1, cb)
    with pytest.raises(ValueError):
        rx.listen_packet(128, cb)
    # boundary values must NOT raise
    rx.listen_packet(0, cb)
    rx.listen_packet(127, cb)


def test_py_listen_packet_none_callback_raises():
    rx = Unbundle()
    with pytest.raises(ValueError):
        rx.listen_packet(5, None)


def test_py_listen_packet_duplicate_raises():
    rx = Unbundle()
    rx.listen_packet(5, lambda chan, data: None)
    with pytest.raises(ValueError):
        rx.listen_packet(5, lambda chan, data: None)
    # a different channel must be unaffected by the duplicate on chan 5
    rx.listen_packet(6, lambda chan, data: None)


def test_py_unlisten_packet_allows_relisten():
    received = []
    rx = Unbundle()
    rx.listen_packet(5, lambda chan, data: None)
    rx.unlisten_packet(5)
    # a fresh listen_packet() on the same channel must succeed, and work
    rx.listen_packet(5, lambda chan, data: received.append((chan, data)))
    rx.put_rx_bytes(make_packet_wire_bytes(b"payload", chan=5))
    assert received == [(5, b"payload")]


def test_py_unlisten_packet_missing_channel_no_error():
    rx = Unbundle()
    # unlisten on a channel with no listener must not raise
    rx.unlisten_packet(5)


#-----------------------------------------------------------------------
# Python: TX callback behavior
#-----------------------------------------------------------------------

def test_py_tx_bytes_available_callback():
    """
    tx_bytes_available fires exactly once per send_string()/
    send_packet() call -- a deliberate, documented difference from
    bundle.c's per-byte-consumed string_not_full()/tx_bytes_available().
    Python's callback signals "a producer call just queued something",
    once per call, regardless of how many bytes or chunks resulted.
    """
    count = 0
    def cb():
        nonlocal count
        count += 1

    tx = Bundle()
    tx.set_tx_bytes_available_callback(cb)

    tx.send_string("a string well past the twenty four character "
                    "chunk boundary, so it queues multiple chunks")
    assert count == 1  # one call -> one fire, regardless of chunk count

    tx.send_packet(1, b"payload")
    assert count == 2

    tx.send_string("x")
    tx.send_packet(2, b"more")
    assert count == 4


def test_py_tx_bytes_available_callback_exception_propagates():
    """
    Per the documented contract, an exception raised inside the
    tx_bytes_available callback must propagate through send_string()/
    send_packet() to the caller, not be silently swallowed.
    """
    class _Boom(Exception):
        pass

    def cb():
        raise _Boom("callback failure")

    tx = Bundle()
    tx.set_tx_bytes_available_callback(cb)

    with pytest.raises(_Boom):
        tx.send_string("hello")

    with pytest.raises(_Boom):
        tx.send_packet(5, b"payload")


def test_py_tx_bytes_available_callback_exception_does_not_lose_data():
    """
    Even though the callback's exception propagates, the string/packet
    data itself was already queued before the callback ran -- a caller
    catching the exception can still expect get_tx_bytes() to have
    something for them.
    """
    class _Boom(Exception):
        pass

    def cb():
        raise _Boom()

    tx = Bundle()
    tx.set_tx_bytes_available_callback(cb)

    with pytest.raises(_Boom):
        tx.send_string("hello")

    wire = tx.get_tx_bytes()
    assert wire == b"hello"


#-----------------------------------------------------------------------
# Python: error_count / reset_error_count, unregistered channel
#-----------------------------------------------------------------------

def test_py_error_count_starts_at_zero():
    rx = Unbundle()
    assert rx.error_count == 0
    # resetting an already-zero counter must not raise or go negative
    rx.reset_error_count()
    assert rx.error_count == 0


def test_py_unregistered_channel_dropped_and_counted():
    """
    A packet sent to a channel with no registered listener is silently
    dropped and counted -- this can happen with zero wire corruption,
    simply by calling send_packet() for a channel the receiver never
    listened on. Confirms no callback anywhere fires (including on an
    unrelated, correctly-registered channel), error_count increments
    by exactly one, and reset_error_count() clears it.
    """
    other_channel_fired = []
    rx = Unbundle()
    rx.listen_packet(6, lambda chan, data: other_channel_fired.append((chan, data)))

    assert rx.error_count == 0
    wire = make_packet_wire_bytes(b"nobody home", chan=5)  # chan 5: no listener
    rx.put_rx_bytes(wire)

    assert rx.error_count == 1
    assert other_channel_fired == []

    rx.reset_error_count()
    assert rx.error_count == 0


#-----------------------------------------------------------------------
# Python: send_string edge cases
#-----------------------------------------------------------------------

def test_py_send_string_non_ascii_raises():
    tx = Bundle()
    with pytest.raises(UnicodeEncodeError):
        tx.send_string("caf\u00e9")  # 'é' is non-ASCII
    # the raise happens before any chunking/queuing -- nothing partial
    # should have been left behind
    assert tx.get_tx_bytes() == b''


def test_py_send_string_empty():
    """
    An empty string encodes to zero chunks -- nothing is queued -- but
    tx_bytes_available still fires, since that check sits outside the
    chunking loop in send_string(). Pinning this down deliberately: a
    caller must not assume "callback fired" implies "something is now
    queued".
    """
    count = 0
    def cb():
        nonlocal count
        count += 1

    tx = Bundle()
    tx.set_tx_bytes_available_callback(cb)
    tx.send_string("")

    assert count == 1
    assert tx.get_tx_bytes() == b''


#-----------------------------------------------------------------------
# Python: get_tx_bytes() with nothing queued
#-----------------------------------------------------------------------

def test_py_get_tx_bytes_empty_bundle():
    tx = Bundle()
    assert tx.get_tx_bytes() == b''


#-----------------------------------------------------------------------
# Zero-length packet payload -- Python and C, transmit and receive
#-----------------------------------------------------------------------

def test_py_packet_transmit_zero_length():
    chan = 5
    expected = make_packet_wire_bytes(b'', chan)

    tx = Bundle()
    tx.send_packet(chan, b'')
    wire_bytes = bytearray()
    while True:
        b = tx.get_tx_bytes()
        if b == b'':
            break
        wire_bytes.extend(b)
    assert bytes(wire_bytes) == expected
    assert len(expected) == 5  # header, COBS byte, 2 CRC bytes, terminator


def test_py_packet_receive_zero_length():
    chan = 5
    wire_bytes = make_packet_wire_bytes(b'', chan)
    received = []
    rx = Unbundle()
    rx.listen_packet(chan, lambda chan, data: received.append((chan, data)))
    rx.put_rx_bytes(wire_bytes)
    assert received == [(chan, b'')]


def test_c_packet_transmit_zero_length(bundle_api, c_object_pool):
    api = bundle_api
    pkt = CPacket(api, bufsize=12, chan=5, data=b'', pool=c_object_pool)
    expected = make_packet_wire_bytes(b'', 5)

    tx = CTx(api, 100, pool=c_object_pool)
    tx.packet_put(pkt)
    wire_bytes = tx.get_tx_bytes()
    assert wire_bytes == expected
    assert pkt.state == BdlPacketState.BP_IDLE


def test_c_packet_receive_zero_length(bundle_api, c_object_pool):
    api = bundle_api
    chan = 5
    wire_bytes = make_packet_wire_bytes(b'', chan)
    pkt = CPacket(api, bufsize=12, chan=chan, pool=c_object_pool)

    rx = CRx(api, 100, pool=c_object_pool)
    rx.packet_listen(pkt)
    rx.put_rx_bytes(wire_bytes)
    assert pkt.state == BdlPacketState.BP_RX_DONE
    assert rx.packet_get(pkt) is True
    assert pkt.length == 0
    assert pkt.read_data() == b''


def test_py_packet_receive_fragmented_across_calls():
    """
    A single packet, with leading and trailing string data, delivered
    to put_rx_bytes() split across two calls at every possible byte
    boundary. Regardless of where the split falls -- including the
    trivial cases of splitting at position 0 or at the very end,
    which double as a sanity check that this harness agrees with the
    unfragmented single-call tests -- the result must always be
    exactly one packet delivered with the correct payload, and the
    string channel data intact as "hello".

    Note: because the string callback fires once per put_rx_bytes()
    call (not once per logical stream), a split landing between the
    leading and trailing string data means the callback fires twice
    (once with "hel", once with "lo") rather than once with "hello".
    Both firings are concatenated before comparing to the expected
    string, in the order received, which preserves wire order because
    each call itself processes its chunk in order and the two calls
    happen in sequence.
    """
    chan = 5
    payload = b"abcde"
    packet_wire = make_packet_wire_bytes(payload, chan)
    wire = b"hel" + packet_wire + b"lo"
    assert len(wire) == 15

    for split in range(0, len(wire) + 1):
        received_packets = []
        received_strings = []
        rx = Unbundle()
        rx.listen_packet(chan, lambda c, d: received_packets.append((c, d)))
        rx.listen_string(lambda s: received_strings.append(s))

        rx.put_rx_bytes(wire[:split])
        rx.put_rx_bytes(wire[split:])

        assert received_packets == [(chan, payload)], f"split={split}"
        assert ''.join(received_strings) == "hello", f"split={split}"
        assert rx.error_count == 0, f"split={split}"

#-----------------------------------------------------------------------
# C & Python - binary and max length packet handling
#-----------------------------------------------------------------------

def _binary_test_payload() -> bytes:
    """
    252-byte (maximum legal) binary payload covering the full byte
    range, deliberately including a leading zero, two consecutive
    zero bytes, and a trailing zero immediately before where the CRC
    gets appended. Proves packet payloads are never filtered or
    specially interpreted (only string-channel data has any byte-value
    restriction), and stresses COBS's in-place zero-rewriting at its
    tightest points -- adjacent zeros are the closest-spaced case for
    an off-by-one in the rewrite chain.
    """
    payload = bytearray((i * 173) % 256 for i in range(252))  # full-range pseudo-random spread
    payload[0]   = 0x00   # leading zero
    payload[10]  = 0x00   # embedded zero
    payload[11]  = 0x00   # consecutive with the one above
    payload[251] = 0x00   # trailing zero -- immediately precedes the CRC bytes
    return bytes(payload)


def test_py_packet_transmit_max_length_binary():
    chan = 5
    payload = _binary_test_payload()
    expected = make_packet_wire_bytes(payload, chan)

    tx = Bundle()
    tx.send_packet(chan, payload)
    wire_bytes = bytearray()
    while True:
        b = tx.get_tx_bytes()
        if b == b'':
            break
        wire_bytes.extend(b)
    wire_bytes = bytes(wire_bytes)

    assert len(wire_bytes) == len(payload) + 5
    assert 0x00 not in wire_bytes[0:-1]
    assert wire_bytes == expected


def test_py_packet_receive_max_length_binary():
    chan = 5
    payload = _binary_test_payload()
    wire_bytes = make_packet_wire_bytes(payload, chan)
    received = []
    rx = Unbundle()
    rx.listen_packet(chan, lambda c, d: received.append((c, d)))
    rx.put_rx_bytes(wire_bytes)
    assert received == [(chan, payload)]
    assert rx.error_count == 0


def test_c_packet_transmit_max_length_binary(bundle_api, c_object_pool):
    api = bundle_api
    chan = 5
    payload = _binary_test_payload()
    expected = make_packet_wire_bytes(payload, chan)

    pkt = CPacket(api, bufsize=254, chan=chan, data=payload, pool=c_object_pool)
    tx = CTx(api, 100, pool=c_object_pool)
    tx.packet_put(pkt)
    wire_bytes = tx.get_tx_bytes()

    assert len(wire_bytes) == len(payload) + 5
    assert 0x00 not in wire_bytes[0:-1]
    assert wire_bytes == expected
    assert pkt.state == BdlPacketState.BP_IDLE


def test_c_packet_receive_max_length_binary(bundle_api, c_object_pool):
    api = bundle_api
    chan = 5
    payload = _binary_test_payload()
    wire_bytes = make_packet_wire_bytes(payload, chan)

    pkt = CPacket(api, bufsize=254, chan=chan, pool=c_object_pool)
    rx = CRx(api, 100, pool=c_object_pool)
    rx.packet_listen(pkt)
    rx.put_rx_bytes(wire_bytes)

    assert pkt.state == BdlPacketState.BP_RX_DONE
    assert rx.packet_get(pkt) is True
    assert pkt.length == len(payload)
    assert pkt.read_data() == payload
    assert bundle_api.get_error_count(rx.rx) == 0


#-----------------------------------------------------------------------
# Wire error fault tree: shared canary helper
#-----------------------------------------------------------------------
# Every wire-error test appends one of these after its corrupted/
# recovering stream and confirms both fire -- proof recovery is
# complete on BOTH channel types, not just one. Parametrized across
# both orderings (packet-then-string, string-then-packet) via
# @pytest.mark.parametrize("canary_suffix", ...) on each test; the
# per-test docstrings below don't repeat this explanation.

CANARY_CHAN = 50
CANARY_PAYLOAD = b"PACKET_CANARY"
CANARY_STRING = "STRING_CANARY"

def canary_suffix_packet_first() -> bytes:
    return make_packet_wire_bytes(CANARY_PAYLOAD, CANARY_CHAN) + CANARY_STRING.encode('ascii')

def canary_suffix_string_first() -> bytes:
    return CANARY_STRING.encode('ascii') + make_packet_wire_bytes(CANARY_PAYLOAD, CANARY_CHAN)

_CANARY_PARAMS = pytest.mark.parametrize(
    "canary_suffix", [canary_suffix_packet_first, canary_suffix_string_first],
    ids=["packet_first", "string_first"],
)

def assert_canary_recovered(received_packets, received_strings):
    assert (CANARY_CHAN, CANARY_PAYLOAD) in received_packets
    assert ''.join(received_strings).endswith(CANARY_STRING)


#-----------------------------------------------------------------------
# Wire error fault tree: commen wrapper for C and Python rx engines
#-----------------------------------------------------------------------

class WireErrorRx:
    """Common interface for wire-error tests, backed by either Unbundle
    or a C bdl_rx_t. Hides backend-specific mechanics (C's buffer
    pooling/recycling, per-byte vs. batched string delivery) behind one
    surface. Constraint: listen_packet() must be called at most once
    per channel -- matches Python's actual restriction, and the C
    backend relies on this too (it isn't built to support C's
    multi-buffer pooling; tests needing that stay C-only)."""

    def listen_packet(self, chan): ...
    def listen_string(self): ...
    def put_rx_bytes(self, data: bytes): ...
    @property
    def error_count(self) -> int: ...
    received_strings: list       # populated as test proceeds
    received_packets: list       # list of (chan, data) tuples


class PyWireErrorRx(WireErrorRx):
    def __init__(self):
        self._rx = Unbundle()
        self.received_strings = []
        self.received_packets = []

    def listen_packet(self, chan):
        self._rx.listen_packet(chan, lambda c, d: self.received_packets.append((c, d)))

    def listen_string(self):
        self._rx.listen_string(lambda s: self.received_strings.append(s))

    def put_rx_bytes(self, data):
        self._rx.put_rx_bytes(data)

    @property
    def error_count(self):
        return self._rx.error_count


class CWireErrorRx(WireErrorRx):
    def __init__(self, api, pool):
        self.api = api
        self.pool = pool
        self.received_strings = []
        self.received_packets = []
        self._packet_cb = register_callback(PACKET_FUNC, self._on_packet, pool)
        self._rx = CRx(api, 100, string_avail_funct=self._on_string_avail, pool=pool)

    def _on_string_avail(self):
        b = self.api.string_get_nb(self._rx.rx)
        if b < 256:
            self.received_strings.append(chr(b))

    def listen_packet(self, chan):
        pkt = CPacket(self.api, bufsize=20, chan=chan, pool=self.pool)
        self._rx.packet_listen(pkt, self._packet_cb)

    def _on_packet(self, addr):
        pkt_obj = self.pool[addr]
        ok = self._rx.packet_get(pkt_obj)
        if ok:
            self.received_packets.append((pkt_obj.chan, pkt_obj.read_data()))
        assert pkt_obj.state == BdlPacketState.BP_IDLE, (
            f"bdl_packet_get() left state={pkt_obj.state!r} instead of BP_IDLE "
            f"(ok={ok}) -- packet_get() must always release the buffer"
        )
        self._rx.packet_listen(pkt_obj, self._packet_cb)

    def listen_string(self):
        pass  # already wired at construction

    def put_rx_bytes(self, data):
        self._rx.put_rx_bytes(data)

    @property
    def error_count(self):
        return self.api.get_error_count(self._rx.rx)


@pytest.fixture(params=["python", "c"])
def wire_error_rx(request, bundle_api, c_object_pool):
    if request.param == "python":
        return PyWireErrorRx()
    return CWireErrorRx(bundle_api, c_object_pool)

#-----------------------------------------------------------------------
# Wire error fault tree: Case 1 -- corrupted string byte
#-----------------------------------------------------------------------

@_CANARY_PARAMS
@pytest.mark.parametrize("corrupt_value,expected_char", [(ord('!'), '!'), (0x00, '\x00')])
def test_wire_error_1a_string_byte_to_valid_string_byte(wire_error_rx, canary_suffix, corrupt_value, expected_char):
    """
    Fault tree case 1A: a string byte corrupted to a different value
    that is still a legal string byte (0x00-0x7F) causes no state
    error -- the string channel has no error detection, by design.
    Covers both an ordinary substitution and corrupt-to-0x00.
    """
    rx = wire_error_rx
    rx.listen_string()
    rx.listen_packet(CANARY_CHAN)

    corrupted = bytearray(b"hello world")
    corrupted[4] = corrupt_value
    stream = bytes(corrupted) + canary_suffix()
    rx.put_rx_bytes(stream)

    assert rx.error_count == 0
    assert ''.join(rx.received_strings) == f"hell{expected_char} world" + CANARY_STRING
    assert_canary_recovered(rx.received_packets, rx.received_strings)

@_CANARY_PARAMS
def test_wire_error_1b1_string_byte_to_header_recovers_via_255_cap(wire_error_rx, canary_suffix):
    """
    Fault tree case 1B, variant 1: a string byte corrupted to >=0x80
    falsely enters packet mode. A long, zero-free run follows with no
    natural terminator, so the 255-byte fail-safe is what ends the
    bogus "packet".  Recovery discards at most one packet's worth of
    collateral data (256 bytes) -- the trailing 'A's beyond
    that point are live string data again, not swallowed.
    In this variant, the bogus packet is addressed to a channel with
    no listener.
    """
    rx = wire_error_rx
    rx.listen_string()
    rx.listen_packet(CANARY_CHAN)

    stream = b"abc" + bytes([100 + 0x80]) + b"A" * 260 + canary_suffix()
    rx.put_rx_bytes(stream)

    assert rx.error_count >= 1
    assert len(rx.received_packets) == 1
    assert_canary_recovered(rx.received_packets, rx.received_strings)

@_CANARY_PARAMS
def test_wire_error_1b2_string_byte_to_header_recovers_via_255_cap(wire_error_rx, canary_suffix):
    """
    Fault tree case 1B, variant 2: a string byte corrupted to >=0x80
    falsely enters packet mode. A long, zero-free run follows with no
    natural terminator, so the 255-byte fail-safe is what ends the
    bogus "packet".  Recovery discards at most one packet's worth of
    collateral data (256 bytes) -- the trailing 'A's beyond
    that point are live string data again, not swallowed.
    In this variant, the bogus packet is addressed to a channel with
    a valid listener; we verify that the bogus packet is discarded
    and that a valid packet still makes it to that listener.
    """
    rx = wire_error_rx
    rx.listen_string()
    rx.listen_packet(CANARY_CHAN)

    stream = b"abc" + bytes([CANARY_CHAN + 0x80]) + b"A" * 260 + canary_suffix()
    rx.put_rx_bytes(stream)

    assert rx.error_count >= 1
    assert len(rx.received_packets) == 1
    assert_canary_recovered(rx.received_packets, rx.received_strings)

@_CANARY_PARAMS
def test_wire_error_1b3_string_byte_to_header_recovers_via_swallowed_packet(wire_error_rx, canary_suffix):
    """
    Fault tree case 1B3: a string byte corrupted to >=0x80 falsely
    enters packet mode, with a genuine packet (channel 9) following
    shortly after. The bogus "packet" swallows that real packet's
    header/COBS/payload/CRC bytes as its own opaque body, and the
    real packet's own terminator ends the bogus packet early.
    In this variant, the bogus packet is addressed to a channel with
    no listener.
    """
    rx = wire_error_rx
    rx.listen_string()
    rx.listen_packet(9)
    rx.listen_packet(CANARY_CHAN)

    swallowed_packet = make_packet_wire_bytes(b"xyz", chan=9)
    stream = b"abc" + bytes([100+0x80]) + swallowed_packet + canary_suffix()
    rx.put_rx_bytes(stream)

    assert rx.error_count >= 1
    assert len(rx.received_packets) == 1
    assert_canary_recovered(rx.received_packets, rx.received_strings)

@_CANARY_PARAMS
def test_wire_error_1b4_string_byte_to_header_recovers_via_swallowed_packet(wire_error_rx, canary_suffix):
    """
    Fault tree case 1B4: a string byte corrupted to >=0x80 falsely
    enters packet mode, with a genuine packet (channel 9) following
    shortly after. The bogus "packet" swallows that real packet's
    header/COBS/payload/CRC bytes as its own opaque body, and the
    real packet's own terminator ends the bogus packet early.
    In this variant, the bogus packet is addressed to a channel with
    a valid listener; we verify that the bogus packet is discarded
    and that a valid packet still makes it to that listener.
    """
    rx = wire_error_rx
    rx.listen_string()
    rx.listen_packet(9)
    rx.listen_packet(CANARY_CHAN)

    swallowed_packet = make_packet_wire_bytes(b"xyz", chan=9)
    stream = b"abc" + bytes([CANARY_CHAN+0x80]) + swallowed_packet + canary_suffix()
    rx.put_rx_bytes(stream)

    assert rx.error_count >= 1
    assert len(rx.received_packets) == 1
    assert_canary_recovered(rx.received_packets, rx.received_strings)

#-----------------------------------------------------------------------
# C fatal error handling - bdl_packet_t
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
# C fatal error handling - bdl_tx_t
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
# C fatal error handling - bdl_rx_t
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

