# test_bundle.py
from __future__ import annotations
import pytest
import ctypes
import random
import binascii
from conftest import register_callback
from bundle import Bundle, Unbundle
from bundle import _crc_seed as crc_seed
from bundle_capi import PACKET_FUNC, VOID_VOID_FUNC, BdlPacketState

#-----------------------------------------------------------------------
# Adapters to make C and Python APIs compatible (where practical)
#-----------------------------------------------------------------------

class _CapiRxAdapter:
    """Wraps a C bdl_rx_t behind the same minimal interface as Unbundle."""
    def __init__(self, api, rx):
        self._api = api
        self._rx = rx

    def put_bytes(self, data: bytes) -> None:
        for b in data:
            self._api.put_rx_byte(self._rx, b)

    @property
    def error_count(self) -> int:
        return self._api.get_error_count(self._rx)

    def reset_error_count(self) -> None:
        self._api.reset_error_count(self._rx)


class _PythonRxAdapter:
    """Wraps an Unbundle behind the same minimal interface, for symmetry
    with _CapiRxAdapter."""
    def __init__(self, ub):
        self._ub = ub

    def put_bytes(self, data: bytes) -> None:
        self._ub.put_rx_bytes(data)

    @property
    def error_count(self) -> int:
        return self._ub.error_count

    def reset_error_count(self) -> None:
        self._ub.reset_error_count()


#-----------------------------------------------------------------------
# Fixtures, using the above adapters
#-----------------------------------------------------------------------

@pytest.fixture
def capi_rx(bundle_api):
    api = bundle_api
    rx = api.new_rx()
    string_buf = ctypes.create_string_buffer(64)
    cfg = api.make_rx_config(string_buf, 64, api.crc16_lookup_ptr)
    api.init_rx(rx, cfg)
    return _CapiRxAdapter(api, rx)

@pytest.fixture
def python_rx():
    return _PythonRxAdapter(Unbundle())



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
        assert length >= 0 and length <= self.bufsize - 2
        self.api.packet_set_len(self.pkt, length)

    def set_chan(self, chan: int):
        assert chan >= 0 and chan < 0x80
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
        assert string_bufsize > 0
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
        assert packet is not None
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
        assert string_bufsize > 0
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
        assert packet is not None
        self.api.packet_listen(self.rx, packet.pkt, registered_callback)

    def packet_get(self, packet: CPacket) -> bool:
        assert packet is not None
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
        header = 0x80 | chan
        seed_py = crc_seed(chan)
        seed_c  =bundle_api.crc_seed(header)
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
        if b == 0:
            break
        received_bytes.append(b)
    received_string = received_bytes.decode('ascii')
    assert received_string == test_string

def test_py_string_receive():
    received_strings = []
    def string_callback(string: str):
        received_strings.append(string)
    rx = Unbundle()
    test_string = "this is a test string"
    wire_bytes = test_string.encode('ascii')
    rx.listen_string(string_callback)
    rx.put_rx_bytes(wire_bytes)
    received_string = ''.join(received_strings)
    assert received_string == test_string



#-----------------------------------------------------------------------
# Callback firing tests
#-----------------------------------------------------------------------



def test_c_rx_packet_callback_fires(bundle_api):
    print()
    api = bundle_api
    fired = []

    def callback(p):
        s = api.packet_get_state(p)
        c = api.packet_get_chan(p)
        l = api.packet_get_len(p)
        print(f"before: {p=}  {s=} {c=} {l=}")
        if s is BdlPacketState.BP_RX_DONE:
            api.packet_get(rx, p)
            s = api.packet_get_state(p)
            c = api.packet_get_chan(p)
            l = api.packet_get_len(p)
            d = api.packet_read_data(p)
            print(f"after:  {p=}  {s=} {c=} {l=} {d=}")
            print(f"data: {d[0]=} {d[1]=} {d[2]=}")
        fired.append(1)

    cb = PACKET_FUNC(callback)

    rx = api.new_rx()
    string_buf = ctypes.create_string_buffer(64)
    cfg = api.make_rx_config(string_buf, 64, api.crc16_lookup_ptr)
    api.init_rx(rx, cfg)

    rx_pkt = api.new_packet()
    rx_buf = (ctypes.c_uint8 * 32)()
    api.packet_init_buf(rx_pkt, rx_buf, 32)
    api.packet_set_chan(rx_pkt, 5)
    callback = PACKET_FUNC(lambda p: fired.append(1))
    api.packet_listen(rx, rx_pkt, cb)

    tx = api.new_tx()
    tx_string_buf = ctypes.create_string_buffer(64)
    tx_cfg = api.make_tx_config(tx_string_buf, 64, api.crc16_lookup_ptr)
    api.init_tx(tx, tx_cfg)

    tx_pkt = api.new_packet()
    tx_buf = (ctypes.c_uint8 * 32)()
    api.packet_init_buf(tx_pkt, tx_buf, 32)
    api.packet_set_chan(tx_pkt, 5)
    api.packet_set_len(tx_pkt, 3)
    tx_buf[0] = 0x42
    tx_buf[1] = 0x43
    tx_buf[2] = 0x44
    api.packet_put(tx, tx_pkt)

    while True:
        b = api.get_tx_byte(tx)
        if b > 255:
            break
        api.put_rx_byte(rx, b)

    assert fired == [1]


def test_c_tx_packet_callback_fires(bundle_api):
    api = bundle_api
    tx = api.new_tx()
    string_buf = ctypes.create_string_buffer(64)
    cfg = api.make_tx_config(string_buf, 64, api.crc16_lookup_ptr)
    api.init_tx(tx, cfg)

    fired = []
    pkt = api.new_packet()
    buf = (ctypes.c_uint8 * 32)()
    api.packet_init_buf(pkt, buf, 32)
    api.packet_set_chan(pkt, 5)
    api.packet_set_len(pkt, 3)
    buf[0] = 0x42
    buf[1] = 0x43
    buf[2] = 0x44
    callback = PACKET_FUNC(lambda p: fired.append(1))
    api.packet_put(tx, pkt, callback)

    while True:
        b = api.get_tx_byte(tx)
        if b > 255:
            break

    assert fired == [1]

def test_python_rx_packet_callback_fires():
    ub = Unbundle()
    fired = []
    ub.listen_packet(5, lambda chan, payload: fired.append((chan, payload)))
    bundle = Bundle()
    bundle.send_packet(5, b"\x42")
    wire = bytearray()
    while True:
        chunk = bundle.get_tx_bytes()
        if not chunk:
            break
        wire += chunk
    ub.put_rx_bytes(bytes(wire))
    assert fired == [(5, b"\x42")]

#-----------------------------------------------------------------------
# Parameterized test
#-----------------------------------------------------------------------

# @pytest.mark.parametrize("fixture_name, trigger", [
#     # C detects an unmatched channel at packet-start; a bare 0x80 with
#     # nothing listening is enough. Python only detects it once a packet
#     # is fully framed -- this is a deliberate, kept asymmetry (see
#     # earlier discussion), not something the adapter should paper over.
#     ("capi_rx", bytes([0x80])),
#     ("python_rx", bytes([0x80, 0x01, 0x00])),
# ])
# def test_error_counter(fixture_name, trigger, request):
#     rx = request.getfixturevalue(fixture_name)
#     assert rx.error_count == 0
#     rx.put_bytes(trigger)
#     assert rx.error_count == 1
#     rx.reset_error_count()
#     assert rx.error_count == 0


