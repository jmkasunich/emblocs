# tests/test_bundle.py
# Tests for bundle.py - Bundle and Unbundle classes
#
# Test categories:
#   TestCOBS        - _cobs_encode / _cobs_decode internal helpers
#   TestCRC         - _crc16_append / _crc16_verify internal helpers
#   TestBundle      - Bundle class (outgoing multiplexer)
#   TestUnbundle    - Unbundle class (incoming demultiplexer)
#   TestRoundTrip   - Bundle -> MockStream -> Unbundle end-to-end
#   Hardware tests  - require --loopback-port, marked with @pytest.mark.hardware

import pytest
import threading
import queue
import time
import io
import string
from dataclasses import dataclass
from collections.abc import Callable

from bundle import (
    Bundle, Unbundle,
    _cobs_encode, _cobs_decode,
    _crc16_append, _crc16_verify,
)



# ---------------------------------------------------------------------------
# MockStream - bidirectional in-memory stream for round-trip tests
# ---------------------------------------------------------------------------

class MockStream:
    """
    Bidirectional in-memory stream for testing Bundle and Unbundle together.
    Bundle writes into it; Unbundle reads from it.
    readinto() blocks up to timeout seconds when no data is available,
    matching pyserial.Serial behavior with a read timeout set.
    """

    def __init__(self, timeout: float = 0.1) -> None:
        self._buf     = bytearray()
        self._lock    = threading.Lock()
        self._event   = threading.Event()
        self._timeout = timeout

    def write(self, data: bytes) -> int:
        with self._lock:
            self._buf.extend(data)
        self._event.set()
        return len(data)

    def readinto(self, buf) -> int:
        self._event.wait(timeout=self._timeout)
        with self._lock:
            n = min(len(buf), len(self._buf))
            if n > 0:
                buf[:n] = self._buf[:n]
                del self._buf[:n]
            if not self._buf:
                self._event.clear()
        return n


# ---------------------------------------------------------------------------
# TxCaptureStream - captures Bundle output as raw bytes for inspection
# ---------------------------------------------------------------------------

class TxCaptureStream:
    """Capture stream for inspecting raw bytes written by Bundle."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def write(self, data: bytes) -> int:
        self._buf.extend(data)
        return len(data)

    def readinto(self, buf) -> int:
        return 0

    @property
    def data(self) -> bytes:
        return bytes(self._buf)

    def clear(self) -> None:
        self._buf.clear()


# ---------------------------------------------------------------------------
# Shared error handler for tests
# ---------------------------------------------------------------------------

class ErrorCapture:
    """Captures on_error callbacks for assertions."""

    def __init__(self) -> None:
        self.errors = []

    def __call__(self, exc: Exception) -> None:
        self.errors.append(exc)

    @property
    def count(self) -> int:
        return len(self.errors)


# ---------------------------------------------------------------------------
# TestCOBS
# ---------------------------------------------------------------------------

class TestCOBS:

    def _assert_cobs_contract(self, data: bytes) -> None:
        """
        Apply full COBS contract checks:
          1. encoded output is exactly one byte longer than input
          2. encoded output contains no zero bytes
          3. decode(encode(data)) == data
        """
        encoded = _cobs_encode(data)
        assert len(encoded) == len(data) + 1, \
            f"encoded length {len(encoded)} != input length {len(data)} + 1"
        assert 0 not in encoded, \
            f"zero byte found at index {encoded.index(0)} in encoded output"
        assert _cobs_decode(encoded) == data, \
            f"decode(encode(data)) != data"

    def test_no_zeros(self):
        self._assert_cobs_contract(b'\x01\x02\x03\x04\x05')

    def test_with_zeros(self):
        self._assert_cobs_contract(b'\x01\x00\x02\x00\x03')

    def test_all_zeros(self):
        self._assert_cobs_contract(b'\x00\x00\x00\x00')

    def test_first_byte_zero(self):
        self._assert_cobs_contract(b'\x00\x01\x02\x03')

    def test_last_byte_zero(self):
        self._assert_cobs_contract(b'\x01\x02\x03\x00')

    def test_first_and_last_zero(self):
        self._assert_cobs_contract(b'\x00\x01\x02\x00')

    def test_consecutive_zeros(self):
        self._assert_cobs_contract(b'\x01\x00\x00\x02')

    def test_single_zero(self):
        self._assert_cobs_contract(b'\x00')

    def test_single_nonzero(self):
        self._assert_cobs_contract(b'\x42')

    def test_alternating_zeros(self):
        self._assert_cobs_contract(bytes([0, 1, 0, 1, 0, 1, 0]))

    def test_all_nonzero_bytes(self):
        self._assert_cobs_contract(bytes(range(1, 255)))

    def test_max_length(self):
        self._assert_cobs_contract(bytes(range(256))[:254])

    def test_empty(self):
        self._assert_cobs_contract(b'')

    def test_decode_empty_raises(self):
        with pytest.raises(ValueError):
            _cobs_decode(b'')


# ---------------------------------------------------------------------------
# TestCRC
# ---------------------------------------------------------------------------

class TestCRC:

    def _assert_crc_contract(self, data: bytes) -> None:
        """
        Apply full CRC contract checks:
          1. appended result is exactly 2 bytes longer than input
          2. verify passes and returns original payload
          3. single byte corruption causes verify to fail
        """
        appended = _crc16_append(data)
        assert len(appended) == len(data) + 2, \
            f"appended length {len(appended)} != input length {len(data)} + 2"
        ok, payload = _crc16_verify(appended)
        assert ok, "verify failed on uncorrupted data"
        assert payload == data, "verify returned wrong payload"
        # corrupt one byte and verify it fails
        if len(appended) > 0:
            corrupted = bytearray(appended)
            corrupted[0] ^= 0xFF
            ok_corrupted, _ = _crc16_verify(bytes(corrupted))
            assert not ok_corrupted, "verify passed on corrupted data"

    def test_single_byte(self):
        self._assert_crc_contract(b'\x42')

    def test_empty_payload(self):
        self._assert_crc_contract(b'')

    def test_max_length(self):
        self._assert_crc_contract(bytes(range(256))[:252])

    def test_typical_payload(self):
        self._assert_crc_contract(b'\x01\x02\x03\x04\x05')

    def test_payload_with_zeros(self):
        self._assert_crc_contract(b'\x00\x01\x00\x02\x00')

    def test_all_zeros_payload(self):
        self._assert_crc_contract(b'\x00' * 10)

    def test_verify_too_short_one_byte(self):
        ok, payload = _crc16_verify(b'\x42')
        assert not ok
        assert payload == b''

    def test_verify_too_short_empty(self):
        ok, payload = _crc16_verify(b'')
        assert not ok
        assert payload == b''

    def test_verify_corrupted_crc_byte(self):
        data = b'\x01\x02\x03'
        appended = bytearray(_crc16_append(data))
        appended[-1] ^= 0xFF    # corrupt last CRC byte only
        ok, _ = _crc16_verify(bytes(appended))
        assert not ok

    def test_verify_single_bit_corruption(self):
        data = b'\x01\x02\x03'
        appended = bytearray(_crc16_append(data))
        appended[1] ^= 0x01    # flip one bit in payload
        ok, _ = _crc16_verify(bytes(appended))
        assert not ok

    def test_known_answer_vectors(self):
        # CRC-16-CCITT (poly=0x1021, init=0xFFFF, no reflection)
        # Values independently verifiable against published CRC tables.
        # These same values must be produced by the C implementation in
        # ser_crc.c to ensure interoperability.
        vectors = [
            (b'123456789',          0x29B1),  # canonical published test vector
            (b'\x41',               0xB915),  # single byte 'A'
            (b'\x00\x00\x00\x00',  0x84C0),  # all zeros
            (b'\x01\x02\x03\x04\x05', 0x9304),
        ]
        import binascii
        for data, expected in vectors:
            actual = binascii.crc_hqx(data, 0xFFFF)
            assert actual == expected, \
                f"CRC16 of {data!r}: expected 0x{expected:04X}, got 0x{actual:04X}"


# ---------------------------------------------------------------------------
# TestBundle
# ---------------------------------------------------------------------------

class TestBundle:

    @pytest.fixture(autouse=True)
    def bundle(self):
        self.stream = TxCaptureStream()
        self.errors = ErrorCapture()
        self.b = Bundle()
        yield
        if self.b._thread is not None and self.b._thread.is_alive():
            self.b.stop()

    def test_configure_channel_valid_min(self):
        self.b.configure_channel(0)

    def test_configure_channel_valid_max(self):
        self.b.configure_channel(127)

    def test_configure_channel_too_high(self):
        with pytest.raises(ValueError):
            self.b.configure_channel(128)

    def test_configure_channel_negative(self):
        with pytest.raises(ValueError):
            self.b.configure_channel(-1)

    def test_send_packet_unconfigured_raises(self):
        self.b.start(self.stream, self.errors)
        with pytest.raises(ValueError):
            self.b.send_packet(0x7F, b'\x01\x02')

    def test_send_packet_oversized_with_crc_raises(self):
        self.b.configure_channel(0x7F, crc=True)
        self.b.start(self.stream, self.errors)
        with pytest.raises(ValueError):
            self.b.send_packet(0x7F, bytes(253))

    def test_send_packet_oversized_without_crc_raises(self):
        self.b.configure_channel(0x7F, crc=False)
        self.b.start(self.stream, self.errors)
        with pytest.raises(ValueError):
            self.b.send_packet(0x7F, bytes(255))

    def test_send_packet_max_length_with_crc(self):
        self.b.configure_channel(0x7F, crc=True)
        self.b.start(self.stream, self.errors)
        self.b.send_packet(0x7F, bytes(252))    # should not raise

    def test_send_packet_max_length_without_crc(self):
        self.b.configure_channel(0x7F, crc=False)
        self.b.start(self.stream, self.errors)
        self.b.send_packet(0x7F, bytes(254))    # should not raise

    def test_send_packet_zero_length(self):
        self.b.configure_channel(0x7F, crc=False)
        self.b.start(self.stream, self.errors)
        self.b.send_packet(0x7F, b'')           # should not raise

    def test_start_creates_running_thread(self):
        self.b.start(self.stream, self.errors)
        assert self.b._thread is not None
        assert self.b._thread.is_alive()

    def test_write_ascii_str(self):
        self.b.start(self.stream, self.errors)
        self.b.write_ascii("hello\n")
        time.sleep(0.2)
        assert self.stream.data == b"hello\n"

    def test_write_ascii_non_ascii_raises(self):
        self.b.start(self.stream, self.errors)
        with pytest.raises(UnicodeEncodeError):
            self.b.write_ascii("héllo")

    def test_wire_format_packet_start_byte(self):
        # packet on channel 0x7F should start with 0xFF
        self.b.configure_channel(0x7F, crc=False)
        self.b.start(self.stream, self.errors)
        self.b.send_packet(0x7F, b'\x01\x02\x03')
        time.sleep(0.2)
        assert self.stream.data[0] == 0xFF

    def test_wire_format_packet_end_byte(self):
        # packet should end with 0x00
        self.b.configure_channel(0x7F, crc=False)
        self.b.start(self.stream, self.errors)
        self.b.send_packet(0x7F, b'\x01\x02\x03')
        time.sleep(0.2)
        assert self.stream.data[-1] == 0x00

    def test_wire_format_no_zeros_in_payload(self):
        # COBS-encoded payload between start and end bytes must not contain 0x00
        self.b.configure_channel(0x7F, crc=False)
        self.b.start(self.stream, self.errors)
        self.b.send_packet(0x7F, b'\x00\x01\x00\x02')
        time.sleep(0.2)
        payload = self.stream.data[1:-1]    # strip start and end bytes
        assert 0 not in payload

    def test_start_twice_raises(self):
        self.b.start(self.stream, self.errors)
        with pytest.raises(RuntimeError):
            self.b.start(self.stream, self.errors)

    def test_stop_twice_is_safe(self):
        self.b.start(self.stream, self.errors)
        self.b.stop()
        self.b.stop()               # should not raise

    def test_start_after_stop(self):
        self.b.start(self.stream, self.errors)
        self.b.stop()
        self.b.start(self.stream, self.errors)   # should not raise

    def test_packet_priority_over_string(self):
        # fill string queue first, then add a packet
        # packet should appear before string data in output
        self.b.configure_channel(0x7F, crc=False)
        self.b.start(self.stream, self.errors)
        # stop the tx thread so we can pre-load both queues
        self.b._stop_flag = True
        self.b._tx_event.set()
        self.b._thread.join()
        self.b._stop_flag = False
        self.stream.clear()
        # pre-load string queue and packet queue
        self.b._str_queue.put(b"hello")
        self.b._pkt_queue.put((0x7F, b'\x01'))
        # restart thread
        self.b._thread = threading.Thread(target=self.b._tx_worker, daemon=True)
        self.b._thread.start()
        self.b._tx_event.set()
        time.sleep(0.2)
        # first byte should be packet start (0xFF), not 'h' (0x68)
        assert self.stream.data[0] == 0xFF


# ---------------------------------------------------------------------------
# TestUnbundle
# ---------------------------------------------------------------------------

class TestUnbundle:

    @pytest.fixture(autouse=True)
    def unbundle(self):
        self.errors = ErrorCapture()
        self.u = Unbundle()
        yield
        if self.u._thread is not None and self.u._thread.is_alive():
            self.u.stop()

    def _make_stream(self, data: bytes) -> io.BytesIO:
        """BytesIO pre-loaded with test data; readinto returns 0 at EOF."""
        return io.BytesIO(data)

    def test_configure_channel_valid_min(self):
        self.u.configure_channel(0)

    def test_configure_channel_valid_max(self):
        self.u.configure_channel(127)

    def test_configure_channel_too_high(self):
        with pytest.raises(ValueError):
            self.u.configure_channel(128)

    def test_configure_channel_negative(self):
        with pytest.raises(ValueError):
            self.u.configure_channel(-1)

    def test_listen_unconfigured_raises(self):
        with pytest.raises(ValueError):
            self.u.listen(0x7F, queue.Queue())

    def test_listen_duplicate_raises(self):
        self.u.configure_channel(0x7F)
        q = queue.Queue()
        self.u.listen(0x7F, q)
        with pytest.raises(ValueError):
            self.u.listen(0x7F, queue.Queue())

    def test_unlisten_removes_listener(self):
        self.u.configure_channel(0x7F)
        q = queue.Queue()
        self.u.listen(0x7F, q)
        self.u.unlisten(0x7F)
        # should be able to listen again
        self.u.listen(0x7F, q)

    def test_unlisten_idempotent(self):
        self.u.configure_channel(0x7F)
        self.u.unlisten(0x7F)    # no listener registered, should not raise
        self.u.unlisten(0x7F)    # second call also safe

    def test_unlisten_preserves_channel_config(self):
        self.u.configure_channel(0x7F, crc=True)
        q = queue.Queue()
        self.u.listen(0x7F, q)
        self.u.unlisten(0x7F)
        # channel still configured, should be able to listen again without configure
        self.u.listen(0x7F, q)

    def test_listen_str_duplicate_raises(self):
        """Calling listen_str() twice without unlisten_str() raises ValueError."""
        str_q = queue.Queue()
        self.u.listen_str(str_q)
        with pytest.raises(ValueError):
            self.u.listen_str(queue.Queue())

    def test_unlisten_str_removes_listener(self):
        """After unlisten_str(), listen_str() can be called again."""
        str_q = queue.Queue()
        self.u.listen_str(str_q)
        self.u.unlisten_str()
        self.u.listen_str(str_q)    # should not raise

    def test_unlisten_str_idempotent(self):
        """unlisten_str() with no listener registered does not raise."""
        self.u.unlisten_str()       # no listener, should not raise
        self.u.unlisten_str()       # second call also safe

    def test_listen_callback_delivered(self):
        """Callback is called with correct payload when packet arrives."""
        received = []
        self.u.configure_channel(0x7F, crc=False)
        self.u.listen(0x7F, callback=lambda data: received.append(data))
        payload = b'\x41\x42\x43'
        encoded = _cobs_encode(payload)
        wire = bytes([0xFF]) + encoded + b'\x00'
        stream = io.BytesIO(wire)
        self.u.start(stream, self.errors)
        time.sleep(0.2)
        self.u.stop()
        assert len(received) == 1
        assert received[0] == payload

    def test_listen_callback_with_crc(self):
        """Callback receives CRC-stripped payload on CRC channel."""
        received = []
        self.u.configure_channel(0x7F, crc=True)
        self.u.listen(0x7F, callback=lambda data: received.append(data))
        payload = b'\x41\x42\x43'
        with_crc = _crc16_append(payload)
        encoded = _cobs_encode(with_crc)
        wire = bytes([0xFF]) + encoded + b'\x00'
        stream = io.BytesIO(wire)
        self.u.start(stream, self.errors)
        time.sleep(0.2)
        self.u.stop()
        assert len(received) == 1
        assert received[0] == payload

    def test_listen_callback_bad_crc_dropped(self):
        """Callback not called and counter incremented when CRC fails."""
        received = []
        self.u.configure_channel(0x7F, crc=True)
        self.u.listen(0x7F, callback=lambda data: received.append(data))
        payload = b'\x41\x42\x43'
        with_crc = bytearray(_crc16_append(payload))
        with_crc[0] ^= 0xFF    # corrupt payload
        encoded = _cobs_encode(bytes(with_crc))
        wire = bytes([0xFF]) + encoded + b'\x00'
        stream = io.BytesIO(wire)
        self.u.start(stream, self.errors)
        time.sleep(0.2)
        self.u.stop()
        assert len(received) == 0
        assert self.u.bad_pkt_count == 1

    def test_listen_both_q_and_callback_raises(self):
        """Providing both q and callback raises ValueError."""
        self.u.configure_channel(0x7F, crc=False)
        with pytest.raises(ValueError):
            self.u.listen(0x7F, q=queue.Queue(), callback=lambda d: None)

    def test_listen_neither_q_nor_callback_raises(self):
        """Providing neither q nor callback raises ValueError."""
        self.u.configure_channel(0x7F, crc=False)
        with pytest.raises(ValueError):
            self.u.listen(0x7F)

    def test_listen_callback_exception_propagates_to_on_error(self):
        """Exception raised in callback propagates to on_error."""
        def bad_callback(data):
            raise RuntimeError("callback error")
        self.u.configure_channel(0x7F, crc=False)
        self.u.listen(0x7F, callback=bad_callback)
        payload = b'\x41\x42\x43'
        encoded = _cobs_encode(payload)
        wire = bytes([0xFF]) + encoded + b'\x00'
        stream = io.BytesIO(wire)
        self.u.start(stream, self.errors)
        time.sleep(0.2)
        self.u.stop()
        assert self.errors.count == 1
        assert isinstance(self.errors.errors[0], RuntimeError)

    def test_listen_callback_then_unlisten_then_queue(self):
        """After unlisten, can register a queue on a channel that had a callback."""
        pkt_q = queue.Queue()
        self.u.configure_channel(0x7F, crc=False)
        self.u.listen(0x7F, callback=lambda d: None)
        self.u.unlisten(0x7F)
        self.u.listen(0x7F, q=pkt_q)    # should not raise
        payload = b'\x41\x42\x43'
        encoded = _cobs_encode(payload)
        wire = bytes([0xFF]) + encoded + b'\x00'
        stream = io.BytesIO(wire)
        self.u.start(stream, self.errors)
        time.sleep(0.2)
        self.u.stop()
        data = pkt_q.get_nowait()
        assert data == payload

    def test_string_channel_complete_line(self):
        str_q = queue.Queue()
        self.u.listen_str(str_q)
        stream = self._make_stream(b"hello\n")
        self.u.start(stream, self.errors)
        time.sleep(0.2)
        self.u.stop()
        text = str_q.get_nowait()
        assert text == "hello\n"

    def test_string_channel_multiple_lines(self):
        str_q = queue.Queue()
        self.u.listen_str(str_q)
        stream = self._make_stream(b"line1\nline2\nline3\n")
        self.u.start(stream, self.errors)
        time.sleep(0.2)
        self.u.stop()
        lines = []
        while not str_q.empty():
            text = str_q.get_nowait()
            lines.append(text)
        assert lines == ["line1\nline2\nline3\n"]

    def test_string_channel_partial_flush_on_timeout(self):
        # partial line with no newline should flush on timeout
        str_q = queue.Queue()
        self.u.listen_str(str_q)
        stream = self._make_stream(b"partial")
        self.u.start(stream, self.errors)
        time.sleep(0.3)    # wait for at least one timeout cycle
        self.u.stop()
        text = str_q.get_nowait()
        assert text == "partial"

    def test_packet_delivered_to_queue(self):
        pkt_q = queue.Queue()
        self.u.configure_channel(0x7F, crc=False)
        self.u.listen(0x7F, pkt_q)
        # build a valid wire-format packet: start + COBS(payload) + end
        payload = b'\x41\x42\x43'
        encoded = _cobs_encode(payload)
        wire = bytes([0xFF]) + encoded + b'\x00'
        stream = self._make_stream(wire)
        self.u.start(stream, self.errors)
        time.sleep(0.2)
        self.u.stop()
        data = pkt_q.get_nowait()
        assert data == payload

    def test_packet_with_crc_delivered(self):
        pkt_q = queue.Queue()
        self.u.configure_channel(0x7F, crc=True)
        self.u.listen(0x7F, pkt_q)
        payload = b'\x41\x42\x43'
        with_crc = _crc16_append(payload)
        encoded = _cobs_encode(with_crc)
        wire = bytes([0xFF]) + encoded + b'\x00'
        stream = self._make_stream(wire)
        self.u.start(stream, self.errors)
        time.sleep(0.2)
        self.u.stop()
        data = pkt_q.get_nowait()
        assert data == payload

    def test_packet_bad_crc_dropped(self):
        pkt_q = queue.Queue()
        self.u.configure_channel(0x7F, crc=True)
        self.u.listen(0x7F, pkt_q)
        payload = b'\x41\x42\x43'
        with_crc = bytearray(_crc16_append(payload))
        with_crc[0] ^= 0xFF    # corrupt payload
        encoded = _cobs_encode(bytes(with_crc))
        wire = bytes([0xFF]) + encoded + b'\x00'
        stream = self._make_stream(wire)
        self.u.start(stream, self.errors)
        time.sleep(0.2)
        self.u.stop()
        assert pkt_q.empty()
        assert self.u.bad_pkt_count == 1

    def test_packet_oversized_dropped(self):
        pkt_q = queue.Queue()
        self.u.configure_channel(0x7F, crc=False)
        self.u.listen(0x7F, pkt_q)
        # build a packet with 256 bytes of payload (too long)
        payload = bytes(256)
        encoded = _cobs_encode(payload)
        wire = bytes([0xFF]) + encoded + b'\x00'
        stream = self._make_stream(wire)
        self.u.start(stream, self.errors)
        time.sleep(0.2)
        self.u.stop()
        assert pkt_q.empty()
        assert self.u.bad_pkt_count == 1

    def test_unregistered_channel_discarded(self):
        pkt_q = queue.Queue()
        # configure 0x7E but send on 0x7F
        self.u.configure_channel(0x7E, crc=False)
        self.u.listen(0x7E, pkt_q)
        payload = b'\x01\x02\x03'
        encoded = _cobs_encode(payload)
        wire = bytes([0xFF]) + encoded + b'\x00'    # address 0x7F, not registered
        stream = self._make_stream(wire)
        self.u.start(stream, self.errors)
        time.sleep(0.2)
        self.u.stop()
        assert pkt_q.empty()

    def test_reset_counter(self):
        self.u.bad_pkt_count = 3
        self.u.reset_counter()
        assert self.u.bad_pkt_count == 0

    def test_packet_split_across_chunks(self):
        # simulate packet arriving in two separate reads
        pkt_q = queue.Queue()
        self.u.configure_channel(0x7F, crc=False)
        self.u.listen(0x7F, pkt_q)
        payload = b'\x41\x42\x43'
        encoded = _cobs_encode(payload)
        wire = bytes([0xFF]) + encoded + b'\x00'
        # split in middle of encoded payload
        split = len(wire) // 2
        part1 = wire[:split]
        part2 = wire[split:]

        class SplitStream:
            def __init__(self):
                self._chunks = [part1, part2]
                self._done = False
            def readinto(self, buf):
                if self._chunks:
                    chunk = self._chunks.pop(0)
                    n = min(len(buf), len(chunk))
                    buf[:n] = chunk[:n]
                    return n
                if not self._done:
                    self._done = True
                    return 0
                time.sleep(0.05)
                return 0

        self.u.start(SplitStream(), self.errors)
        time.sleep(0.3)
        self.u.stop()
        data = pkt_q.get_nowait()
        assert data == payload

    def test_start_twice_raises(self):
        stream = self._make_stream(b'')
        self.u.start(stream, self.errors)
        with pytest.raises(RuntimeError):
            self.u.start(stream, self.errors)

    def test_stop_twice_is_safe(self):
        stream = self._make_stream(b'')
        self.u.start(stream, self.errors)
        self.u.stop()
        self.u.stop()

    def test_start_after_stop(self):
        stream = self._make_stream(b'')
        self.u.start(stream, self.errors)
        self.u.stop()
        self.u.start(stream, self.errors)

    def test_string_interrupted_by_packet(self):
        """Packet arriving mid-string doesn't corrupt string or packet data."""
        pkt_q = queue.Queue()
        str_q = queue.Queue()
        self.u.configure_channel(0x7F, crc=False)
        self.u.listen(0x7F, pkt_q)
        self.u.listen_str(str_q)
        # construct wire data: "hello" + packet + "world\n"
        payload = b'\x42'
        encoded = _cobs_encode(payload)
        wire = b"hello" + bytes([0xFF]) + encoded + b'\x00' + b"world\n"
        stream = io.BytesIO(wire)
        self.u.start(stream, self.errors)
        time.sleep(0.2)
        self.u.stop()
        # packet must arrive intact
        pkt_data = pkt_q.get_nowait()
        assert pkt_data == payload
        # string data must arrive intact (possibly as multiple chunks)
        strings = []
        while not str_q.empty():
            strings.append(str_q.get_nowait())
        combined = ''.join(strings)
        assert combined == "helloworld\n"

    def test_false_packet_start_recovery_string(self):
        """
        Case 1A: bit flip sets bit 7 in string data, no zero bytes in the
        false packet region, recovery via 255-byte limit.
        305 bytes of padding after the false start guarantees 'world\\n'
        survives regardless of chunk boundaries (assuming _RX_BUF_SIZE <= 50).
        Valid packet after recovery confirms sync is restored.
        """
        pkt_q = queue.Queue()
        str_q = queue.Queue()
        self.u.configure_channel(0x7F, crc=False)
        self.u.listen(0x7F, q=pkt_q)
        self.u.listen_str(str_q)
        # good string data before error
        before    = b"hello\n"
        # false packet start: 'A' (0x41) with bit 7 set = 0xC1
        # followed by 305 bytes of 0x41 - no zeros so no early termination
        false_pkt = bytes([0xC1]) + bytes([0x41] * 305)
        # good string data after recovery - guaranteed to survive
        after     = b"world\n"
        # valid packet to confirm sync is restored
        payload   = b'\x01\x02\x03'
        encoded   = _cobs_encode(payload)
        valid_pkt = bytes([0xFF]) + encoded + b'\x00'
        wire      = before + false_pkt + after + valid_pkt
        stream    = io.BytesIO(wire)
        self.u.start(stream, self.errors)
        time.sleep(0.2)
        self.u.stop()
        # collect all string data
        strings = []
        while not str_q.empty():
            strings.append(str_q.get_nowait())
        combined = ''.join(strings)
        assert "hello\n" in combined, f"pre-error string not received: {combined!r}"
        assert "world\n" in combined, f"post-recovery string not received: {combined!r}"
        assert self.u.bad_pkt_count == 1, \
            f"expected 1 bad packet, got {self.u.bad_pkt_count}"
        # valid packet must arrive confirming sync restored
        data = pkt_q.get_nowait()
        assert data == payload

    def test_false_packet_start_recovery_packet(self):
        """
        Case 1B: bit flip sets bit 7 in string data, a short packet follows
        whose terminator arrives before 255 bytes are consumed, causing early
        recovery.  The recovery packet is discarded (wrong channel), but a
        subsequent packet on the correct channel arrives correctly.
        """
        pkt_q = queue.Queue()
        str_q = queue.Queue()
        self.u.configure_channel(0x7F, crc=False)
        self.u.listen(0x7F, q=pkt_q)
        self.u.listen_str(str_q)
        before          = b"hello\n"
        false_start     = bytes([0xC1])    # 'A' with bit 7 set, addr = 0x41
        # recovery packet: start byte consumed as packet data,
        # terminator ends the false packet
        recovery_payload = b'\x0A\x0B\x0C'
        recovery_encoded = _cobs_encode(recovery_payload)
        recovery_pkt     = bytes([0xFF]) + recovery_encoded + b'\x00'
        after           = b"world\n"
        payload         = b'\x01\x02\x03'
        encoded         = _cobs_encode(payload)
        valid_pkt       = bytes([0xFF]) + encoded + b'\x00'
        wire   = before + false_start + recovery_pkt + after + valid_pkt
        stream = io.BytesIO(wire)
        self.u.start(stream, self.errors)
        time.sleep(0.2)
        self.u.stop()
        strings = []
        while not str_q.empty():
            strings.append(str_q.get_nowait())
        combined = ''.join(strings)
        assert "hello\n" in combined, \
            f"pre-error string not received: {combined!r}"
        assert "world\n" in combined, \
            f"post-recovery string not received: {combined!r}"
        assert self.u.bad_pkt_count == 1, \
            f"expected 1 bad packet, got {self.u.bad_pkt_count}"
        data = pkt_q.get_nowait()
        assert data == payload

    def test_unbundle_corrupted_packet_start(self):
        """
        Case 2: bit flip clears bit 7 of packet start byte.
        Receiver stays in string mode, payload appears as garbled string data.
        Terminator arrives harmlessly in string mode.
        Next valid packet arrives correctly.
        """
        pkt_q = queue.Queue()
        str_q = queue.Queue()
        self.u.configure_channel(0x7F, crc=False)
        self.u.listen(0x7F, q=pkt_q)
        self.u.listen_str(str_q)
        # valid packet with corrupted start byte and all-low payload
        # so no false packet starts from payload bytes
        payload         = bytes([0x01, 0x02, 0x03, 0x04, 0x05])
        encoded         = _cobs_encode(payload)
        # corrupt start byte: 0xFF -> 0x7F
        corrupted_pkt   = bytes([0x7F]) + encoded + b'\x00'
        # valid packet after
        valid_payload   = b'\x0A\x0B\x0C'
        valid_encoded   = _cobs_encode(valid_payload)
        valid_pkt       = bytes([0xFF]) + valid_encoded + b'\x00'
        after     = b"recovered\n"
        wire      = corrupted_pkt + valid_pkt + after
        stream = io.BytesIO(wire)
        self.u.start(stream, self.errors)
        time.sleep(0.2)
        self.u.stop()
        # collect string data
        strings = []
        while not str_q.empty():
            strings.append(str_q.get_nowait())
        combined = ''.join(strings)
        # string channel must still be working after the error
        assert "recovered\n" in combined, \
                f"post-recovery string not received: {combined!r}"
        # no bad packets - the corrupted packet just flows through string channel
        assert self.u.bad_pkt_count == 0
        # valid packet arrives correctly
        data = pkt_q.get_nowait()
        assert data == valid_payload
        # string queue has the garbled packet data - we don't check content
        # but combined is non-empty proves string channel was active throughout
        assert len(combined) > len("recovered\n")

    @pytest.mark.parametrize("corrupt_index, description", [
        (0,  "COBS overhead byte"),
        (1,  "first payload byte"),
        (3,  "middle payload byte"),
        (-2, "first CRC byte"),
        (-1, "second CRC byte"),
    ])
    def test_corrupted_encoded_byte(self, corrupt_index, description):
        """
        Cases 3, 4, 5: bit flip in COBS overhead byte, payload byte, or CRC byte.
        In all cases CRC catches the corruption, packet is dropped and counted.
        Next packet and string channel both recover correctly.
        """
        pkt_q = queue.Queue()
        str_q = queue.Queue()
        self.u.configure_channel(0x7F, crc=True)
        self.u.listen(0x7F, q=pkt_q)
        self.u.listen_str(str_q)
        payload        = b'\x01\x02\x00\x04\x05'   # zero in payload ensures COBS chain
        with_crc       = _crc16_append(payload)
        encoded        = _cobs_encode(with_crc)
        corrupted      = bytearray(encoded)
        corrupted[corrupt_index] ^= 0x01
        corrupted_pkt  = bytes([0xFF]) + bytes(corrupted) + b'\x00'
        valid_payload  = b'\x0A\x0B\x0C'
        valid_with_crc = _crc16_append(valid_payload)
        valid_encoded  = _cobs_encode(valid_with_crc)
        valid_pkt      = bytes([0xFF]) + valid_encoded + b'\x00'
        after          = b"ok\n"
        wire   = corrupted_pkt + valid_pkt + after
        stream = io.BytesIO(wire)
        self.u.start(stream, self.errors)
        time.sleep(0.2)
        self.u.stop()
        assert self.u.bad_pkt_count >= 1, \
            f"corrupt {description}: expected at least 1 bad packet, got {self.u.bad_pkt_count}"
        data = pkt_q.get_nowait()
        assert data == valid_payload, \
            f"corrupt {description}: valid packet not received correctly"
        strings = []
        while not str_q.empty():
            strings.append(str_q.get_nowait())
        combined = ''.join(strings)
        assert "ok\n" in combined, \
            f"corrupt {description}: post-error string not received"

    def test_corrupted_terminator_string(self):
        """
        Case 6B: bit flip corrupts packet terminator (0x00 -> non-zero).
        Receiver never sees end of packet; subsequent string data accumulates
        in pkt_buf until 255-byte limit fires, then recovers to string mode.
        Valid packet after recovery confirms sync is restored.
        """
        pkt_q = queue.Queue()
        str_q = queue.Queue()
        self.u.configure_channel(0x7F, crc=True)
        self.u.listen(0x7F, q=pkt_q)
        self.u.listen_str(str_q)
        payload        = b'\x01\x02\x03\x04\x05'
        with_crc       = _crc16_append(payload)
        encoded        = _cobs_encode(with_crc)
        # corrupt terminator: 0x00 -> 0x01
        corrupted_pkt  = bytes([0xFF]) + encoded + b'\x01'
        # string data after - will be consumed as false packet data
        # need 305 bytes to guarantee recovery and safe 'after' string
        filler         = bytes([0x41] * 305)
        after          = b"recovered\n"
        valid_payload  = b'\x0A\x0B\x0C'
        valid_with_crc = _crc16_append(valid_payload)
        valid_encoded  = _cobs_encode(valid_with_crc)
        valid_pkt      = bytes([0xFF]) + valid_encoded + b'\x00'
        wire   = corrupted_pkt + filler + after + valid_pkt
        stream = io.BytesIO(wire)
        self.u.start(stream, self.errors)
        time.sleep(0.2)
        self.u.stop()
        assert self.u.bad_pkt_count >= 1, \
            f"expected at least 1 bad packet, got {self.u.bad_pkt_count}"
        data = pkt_q.get_nowait()
        assert data == valid_payload
        strings = []
        while not str_q.empty():
            strings.append(str_q.get_nowait())
        combined = ''.join(strings)
        assert "recovered\n" in combined, \
            f"post-recovery string not received: {combined!r}"

    def test_corrupted_terminator_early_recovery(self):
        """
        Case 6B alternate: corrupted terminator followed by two packets.
        First packet's terminator causes early recovery but that packet
        is lost. Second packet arrives correctly.
        """
        pkt_q = queue.Queue()
        str_q = queue.Queue()
        self.u.configure_channel(0x7F, crc=True)
        self.u.listen(0x7F, q=pkt_q)
        self.u.listen_str(str_q)
        # packet with corrupted terminator
        payload        = b'\x01\x02\x03'
        with_crc       = _crc16_append(payload)
        encoded        = _cobs_encode(with_crc)
        corrupted_pkt  = bytes([0xFF]) + encoded + b'\x01'  # 0x00 -> 0x01
        # recovery packet: its terminator ends the false packet
        # but the packet itself is lost (consumed as false packet data)
        recovery_payload = b'\x04\x05\x06'
        recovery_with_crc = _crc16_append(recovery_payload)
        recovery_encoded = _cobs_encode(recovery_with_crc)
        recovery_pkt     = bytes([0xFF]) + recovery_encoded + b'\x00'
        # valid packet after recovery
        valid_payload  = b'\x0A\x0B\x0C'
        valid_with_crc  = _crc16_append(valid_payload)
        valid_encoded  = _cobs_encode(valid_with_crc)
        valid_pkt      = bytes([0xFF]) + valid_encoded + b'\x00'
        after          = b"ok\n"
        wire   = corrupted_pkt + recovery_pkt + valid_pkt + after
        stream = io.BytesIO(wire)
        self.u.start(stream, self.errors)
        time.sleep(0.2)
        self.u.stop()
        assert self.u.bad_pkt_count >= 1, \
            f"expected at least 1 bad packet, got {self.u.bad_pkt_count}"
        # valid packet must arrive correctly
        data = pkt_q.get_nowait()
        assert data == valid_payload
        # string channel still working
        strings = []
        while not str_q.empty():
            strings.append(str_q.get_nowait())
        combined = ''.join(strings)
        assert "ok\n" in combined, \
            f"post-recovery string not received: {combined!r}"

# ---------------------------------------------------------------------------
# TestRoundTrip - Bundle -> MockStream -> Unbundle
# ---------------------------------------------------------------------------

class TestRoundTrip:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.stream   = MockStream()
        self.b_errors = ErrorCapture()
        self.u_errors = ErrorCapture()
        self.b = Bundle()
        self.u = Unbundle()
        yield
        self.b.stop()
        self.u.stop()

    def test_string_roundtrip(self):
        str_q = queue.Queue()
        self.u.listen_str(str_q)
        self.u.start(self.stream, self.u_errors)
        self.b.start(self.stream, self.b_errors)
        self.b.write_ascii("hello\n")
        time.sleep(0.3)
        text = str_q.get_nowait()
        assert text == "hello\n"

    def test_packet_roundtrip_with_crc(self):
        pkt_q = queue.Queue()
        self.b.configure_channel(0x7F, crc=True)
        self.u.configure_channel(0x7F, crc=True)
        self.u.listen(0x7F, pkt_q)
        self.u.start(self.stream, self.u_errors)
        self.b.start(self.stream, self.b_errors)
        payload = b'\x41\x42\x43'
        self.b.send_packet(0x7F, payload)
        time.sleep(0.3)
        data = pkt_q.get_nowait()
        assert data == payload

    def test_packet_roundtrip_without_crc(self):
        pkt_q = queue.Queue()
        self.b.configure_channel(0x7F, crc=False)
        self.u.configure_channel(0x7F, crc=False)
        self.u.listen(0x7F, pkt_q)
        self.u.start(self.stream, self.u_errors)
        self.b.start(self.stream, self.b_errors)
        payload = b'\x01\x02\x03'
        self.b.send_packet(0x7F, payload)
        time.sleep(0.3)
        data = pkt_q.get_nowait()
        assert data == payload

    def test_multiple_packet_addresses(self):
        q1 = queue.Queue()
        q2 = queue.Queue()
        self.b.configure_channel(0x7E, crc=False)
        self.b.configure_channel(0x7F, crc=False)
        self.u.configure_channel(0x7E, crc=False)
        self.u.configure_channel(0x7F, crc=False)
        self.u.listen(0x7E, q1)
        self.u.listen(0x7F, q2)
        self.u.start(self.stream, self.u_errors)
        self.b.start(self.stream, self.b_errors)
        self.b.send_packet(0x7E, b'\x01')
        self.b.send_packet(0x7F, b'\x02')
        time.sleep(0.3)
        d1 = q1.get_nowait()
        d2 = q2.get_nowait()
        assert d1 == b'\x01'
        assert d2 == b'\x02'

    def test_interleaved_string_and_packet(self):
        str_q = queue.Queue()
        pkt_q = queue.Queue()
        self.b.configure_channel(0x7F, crc=False)
        self.u.configure_channel(0x7F, crc=False)
        self.u.listen_str(str_q)
        self.u.listen(0x7F, pkt_q)
        self.u.start(self.stream, self.u_errors)
        self.b.start(self.stream, self.b_errors)
        self.b.write_ascii("hello\n")
        self.b.send_packet(0x7F, b'\x42')
        self.b.write_ascii("world\n")
        time.sleep(0.3)
        pkt_data = pkt_q.get_nowait()
        assert pkt_data == b'\x42'
        strings = []
        while not str_q.empty():
            text = str_q.get_nowait()
            strings.append(text)
        combined = ''.join(strings)
        assert combined == "hello\nworld\n"


# ---------------------------------------------------------------------------
# Hardware tests (require --loopback-port)
# ---------------------------------------------------------------------------

@dataclass
class TransferRecord:
    """
    Records a single string or packet transfer event, sent or received.
    timestamp is time.monotonic() at the moment of the send or receive call.
    kind is 'string' or 'packet'.
    channel is None for string records, packet address for packet records.
    data is the str sent/received for strings, bytes for packets.
    """
    timestamp: float
    kind:      str
    channel:   int | None
    data:      bytes | str

    def compare(self, other: 'TransferRecord') -> tuple[bool, float]:
        """
        Compare kind, channel, and data with another record.
        Returns (match, delta) where delta = other.timestamp - self.timestamp.
        Always returns (False, 0.0) for string records since strings may
        arrive fragmented; use reassemble_strings() for string comparison.
        """
        if self.kind == 'string' or other.kind == 'string':
            return False, 0.0
        match = (self.kind    == other.kind and
                 self.channel == other.channel and
                 self.data    == other.data)
        return match, other.timestamp - self.timestamp


def reassemble_strings(records: list[TransferRecord]) -> str:
    """Concatenate all string records in order, returning the complete string."""
    return ''.join(r.data for r in records if r.kind == 'string')


def string_fragments(records: list[TransferRecord]) -> list[TransferRecord]:
    """Return only string records, preserving order and timestamps."""
    return [r for r in records if r.kind == 'string']


def packet_records(records: list[TransferRecord],
                   channel: int | None = None) -> list[TransferRecord]:
    """
    Return only packet records, optionally filtered by channel.
    If channel is None, returns all packet records.
    """
    return [r for r in records if r.kind == 'packet'
            and (channel is None or r.channel == channel)]


class TestHardware:

    def setup_method(self) -> None:
        """Called before each test method; initialize sent/received lists."""
        self._sent:     list[TransferRecord] = []
        self._received: list[TransferRecord] = []
        self._done      = False

    # ------------------------------------------------------------------
    # start with two simple go/no-go tests before building infrastructure
    # ------------------------------------------------------------------

    @pytest.mark.hardware
    def test_hw_single_string(self, loopback_port):
        """Send a single string and verify it arrives intact."""
        import serial
        port = serial.Serial(loopback_port, 115200, timeout=0.1)
        try:
            b = Bundle()
            u = Unbundle()
            str_q = queue.Queue()
            u.listen_str(str_q)
            u.start(port, lambda e: None)
            b.start(port, lambda e: None)
            b.write_ascii("hello\n")
            time.sleep(0.2)
            b.stop()
            u.stop()
            text = str_q.get_nowait()
            assert text == "hello\n"
            assert u.bad_pkt_count == 0
        finally:
            port.close()

    @pytest.mark.hardware
    def test_hw_single_packet(self, loopback_port):
        """Send a single packet with CRC and verify it arrives intact."""
        import serial
        port = serial.Serial(loopback_port, 115200, timeout=0.1)
        try:
            b = Bundle()
            u = Unbundle()
            pkt_q = queue.Queue()
            b.configure_channel(0x7F, crc=True)
            u.configure_channel(0x7F, crc=True)
            u.listen(0x7F, q=pkt_q)
            u.start(port, lambda e: None)
            b.start(port, lambda e: None)
            payload = b'\x01\x02\x03\x04\x05'
            b.send_packet(0x7F, payload)
            time.sleep(0.2)
            b.stop()
            u.stop()
            data = pkt_q.get_nowait()
            assert data == payload
            assert u.bad_pkt_count == 0
        finally:
            port.close()

    # ------------------------------------------------------------------
    # Send wrappers - capture timestamp and record before sending
    # ------------------------------------------------------------------

    def send_string(self, b: Bundle, text: str) -> None:
        ts = time.monotonic()
        b.write_ascii(text)
        self._sent.append(TransferRecord(ts, 'string', None, text))

    def send_packet(self, b: Bundle, addr: int, data: bytes) -> None:
        ts = time.monotonic()
        b.send_packet(addr, data)
        self._sent.append(TransferRecord(ts, 'packet', addr, data))

    # ------------------------------------------------------------------
    # Receive infrastructure
    # ------------------------------------------------------------------

    def make_packet_callback(self, addr: int) -> Callable:
        """
        Returns a callback for use with Unbundle.listen().
        Captures timestamp and appends a TransferRecord to self._received.
        Runs in _rx_worker context - must return quickly.
        """
        def callback(data: bytes) -> None:
            self._received.append(
                TransferRecord(time.monotonic(), 'packet', addr, data))
        return callback

    def start_string_listener(self, str_q: queue.Queue) -> threading.Thread:
        """
        Start a thread that reads from str_q and appends TransferRecords
        to self._received until self._done is set.
        Returns the thread so the caller can join it.
        """
        def listener() -> None:
            while not self._done:
                try:
                    text = str_q.get(timeout=0.1)
                    self._received.append(
                        TransferRecord(time.monotonic(), 'string', None, text))
                except queue.Empty:
                    pass
        t = threading.Thread(target=listener, daemon=True)
        t.start()
        return t

    # ------------------------------------------------------------------
    # General test infrastructure
    # ------------------------------------------------------------------

    def open_port(self, loopback_port: str, baud: int = 115200) -> tuple:
        """
        Open serial port, create Bundle and Unbundle, return (port, b, u).
        Caller is responsible for calling close_port() in finally block.
        """
        import serial
        port = serial.Serial(loopback_port, baud, timeout=0.1)
        b = Bundle()
        u = Unbundle()
        return port, b, u

    def setup_channels(self, b: Bundle, u: Unbundle,
                    str_q: queue.Queue,
                    packet_addrs: list[int],
                    crc: bool = True) -> None:
        """
        Configure Bundle and Unbundle for the given packet addresses and
        register listeners.  String channel is always set up.
        """
        u.listen_str(str_q)
        for addr in packet_addrs:
            b.configure_channel(addr, crc=crc)
            u.configure_channel(addr, crc=crc)
            u.listen(addr, callback=self.make_packet_callback(addr))

    def start_all(self, port, b: Bundle, u: Unbundle,
                str_q: queue.Queue, packet_addrs: list[int],
                crc: bool = True) -> threading.Thread:
        """
        Set up channels, start listener thread, start Bundle and Unbundle.
        Returns the string listener thread.
        """
        self.setup_channels(b, u, str_q, packet_addrs, crc)
        listener = self.start_string_listener(str_q)
        u.start(port, lambda e: None)
        b.start(port, lambda e: None)
        return listener

    def stop_all(self, b: Bundle, u: Unbundle,
                listener: threading.Thread) -> None:
        """Stop Bundle, Unbundle, and string listener thread."""
        b.stop()
        u.stop()
        self._done = True
        listener.join()

    # ------------------------------------------------------------------
    # End-to-end Tests
    # ------------------------------------------------------------------

    @pytest.mark.hardware
    def test_hw_one_string_one_packet(self, loopback_port):
        """Send one string and one packet; verify both arrive intact."""
        str_q = queue.Queue()
        port, b, u = self.open_port(loopback_port)
        try:
            listener = self.start_all(port, b, u, str_q, [0x7F])
            self.send_string(b, "hello\n")
            self.send_packet(b, 0x7F, b'\x01\x02\x03\x04\x05')
            time.sleep(0.2)
            self.stop_all(b, u, listener)
            # verify string
            assert reassemble_strings(self._received) == "hello\n"
            # verify packet
            sent_pkts    = packet_records(self._sent,     channel=0x7F)
            received_pkts = packet_records(self._received, channel=0x7F)
            assert len(received_pkts) == 1
            match, delta = sent_pkts[0].compare(received_pkts[0])
            assert match
            print(f"\npacket transit time: {delta*1000:.1f}ms")
            assert u.bad_pkt_count == 0
        finally:
            port.close()

    @pytest.mark.hardware_perf
    def test_hw_packet_timing(self, loopback_port):
        """
        Send N packets back-to-back and measure individual and overall timing.
        Verifies all packets arrive intact with no CRC errors.
        """
        import random
        random.seed(42)  # fixed seed, same data every run
        baud = 3000000
        N = 20
        PAYLOAD_SIZE = 250
        str_q = queue.Queue()
        port, b, u = self.open_port(loopback_port, baud=baud)
        try:
            listener = self.start_all(port, b, u, str_q, [0x7F])
            # generate all payloads before sending to minimize send loop overhead
            payloads = [random.randbytes(PAYLOAD_SIZE) for _ in range(N)]
            #payloads = [bytes([0x41] * PAYLOAD_SIZE) for _ in range(N)]
            for payload in payloads:
                self.send_packet(b, 0x7F, payload)
            time.sleep(2.0)
            self.stop_all(b, u, listener)
            print(f"\n{N} packets, {PAYLOAD_SIZE} byte payload, {baud} baud")
            print(f"{u.bad_pkt_count=}")
            sent_pkts     = packet_records(self._sent,     channel=0x7F)
            received_pkts = packet_records(self._received, channel=0x7F)
            print(f"{len(received_pkts)=}")
            print(f"  {'pkt':>3}  {'off':>3}  {'transit ms':>10}  {'interval ms':>11}")
            offset = 0
            for i in range(len(received_pkts)):
                match, delta = sent_pkts[i+offset].compare(received_pkts[i])
                if not match:
                    offset = offset + 1
                    match, delta = sent_pkts[i+offset].compare(received_pkts[i])
                assert match, f"packet {i} data mismatch"
                if i == 0:
                    interval_ms = 0.0
                else:
                    interval = received_pkts[i].timestamp - received_pkts[i-1].timestamp
                    interval_ms = interval * 1000
                print(f"  {i:>3}  {offset:>3}  {delta*1000:>10.6f}  {interval_ms:>11.6f}")
            overall_transit = received_pkts[-1].timestamp - sent_pkts[0].timestamp
            overall_interval = received_pkts[-1].timestamp - received_pkts[0].timestamp
            print(f"\n  overall transit:  {overall_transit*1000:.6f}ms")
            print(f"  overall interval: {overall_interval*1000:.6f}ms")
            assert u.bad_pkt_count == 0
            assert len(received_pkts) == N, \
                f"expected {N} packets, received {len(received_pkts)}"
        finally:
            port.close()

