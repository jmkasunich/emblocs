"""
bundle.py

Multiplexed string and binary packet data over a shared byte stream.

Bundle accepts strings (string channel) and addressed binary packets
from callers, then multiplexes them into a single outgoing byte stream.
Binary packets take priority over string channel data.

Unbundle reads an incoming byte stream, demultiplexes into a string
channel and per-channel packets.

String channel data is delivered by a callback, registered by calling
'listen_string()'.  The string channel has no error detection.

Binary packets include a CRC; packets with bad CRCs are dropped and
counted.  Good packets are delivered by a callback, registered by
calling 'listen_packet()' for the channel desired.

The string channel can transmit only ASCII characters; non-ASCII will
result in a UnicodeEncodeError exception.  This is an inherent
limitation of the protocol, which uses the fact that ASCII characters
are seven bits to manage string/binary transitions.

The COBS encoding variant in use limits the binary packet length to
254 bytes.  Packet payloads are limited to 252 bytes to allow for the
2-byte CRC.  Packets that are too large will raise ValueError.

There are 128 binary packet channels, numbered 0x00 to 0x7F (0 to 127).
Only one listener is allowed per channel.


Wire format:
  String channel:  bytes 0x00-0x7F, sent as-is
  Packet start:    0x80 | (chan & 0x7F)
  Packet payload:  COBS-encoded data bytes
  Packet end:      0x00

Wire side API:

For transmit, calling get_tx_bytes() will return either a packet, a
chunk of string data, or '' if there is nothing to send.  A callback
can be configured to trigger when bytes are avaiable to send.

For receive, calling put_rx_bytes(data) will split 'data' into string and
packet channels.  Registered callbacks will be called in put_rx_bytes()
context for each completed packet and for string channel data in 'data'.

"""

import queue
import threading
import binascii
import re
from collections.abc import Callable


# ---------------------------------------------------------------------------
# COBS encode/decode (operates on bytes/bytearray)
# ---------------------------------------------------------------------------

def _cobs_encode(data: bytes) -> bytes:
    """
    COBS-encode data.  Returns encoded bytes including the leading code byte.
    Input may contain any byte value including 0x00.
    Output contains no 0x00 bytes.
    """
    out = bytearray(len(data) + 1)
    out[1:] = data
    end = len(out)
    cp = 0
    while True:
        next_zero = out.find(0, cp + 1, end)
        if next_zero == -1:
            out[cp] = end - cp
            return bytes(out)
        out[cp] = next_zero - cp
        cp = next_zero


def _cobs_decode(data: bytes) -> bytes:
    """
    COBS-decode data.  data must include the leading code byte and must
    not include the trailing 0x00 packet terminator.
    Returns decoded bytes.  Raises ValueError on malformed input.
    """
    if not data:
        raise ValueError("empty COBS data")
    buf = bytearray(data[1:])
    end = len(buf)
    bp = data[0] - 1
    while bp < end:
        code = buf[bp]
        buf[bp] = 0
        bp += code
    return bytes(buf)


# ---------------------------------------------------------------------------
# CRC-16-CCITT
# Polynomial 0x1021, uses provided seed (must be non-zero), no reflection.
# ---------------------------------------------------------------------------

def _crc16_append(seed: int, data: bytes) -> bytes:
    """
    Append 2-byte little-endian CRC-16-CCITT to data.
    """
    crc = binascii.crc_hqx(data, seed & 0xFFFF)
    return data + bytes([crc & 0xFF, crc >> 8])


def _crc16_verify(seed: int, data: bytes) -> tuple[bool, bytes]:
    """
    Verify CRC-16-CCITT appended to data.
    Returns (True, payload) on success, (False, b'') on failure.
    payload has the 2 CRC bytes removed.
    """
    if len(data) < 2:
        return False, b''
    payload = data[:-2]
    crc_recv = data[-2] | (data[-1] << 8)
    crc_calc = binascii.crc_hqx(payload, seed & 0xFFFF)
    if crc_calc != crc_recv:
        return False, b''
    return True, payload

def _crc_seed(channel: int) -> int:
    """
    Compute the per-channel CRC seed.  Must match bundle.c's seed
    formula exactly for interoperability:
    """
    return (channel << 8) | ((~channel) & 0xFF)

# ---------------------------------------------------------------------------
# Regex to detect "special" characters in string mode
#    0x80-0xFF marks start of binary packet
# ---------------------------------------------------------------------------

_SPECIAL = re.compile(b'[\x80-\xff]')

# ---------------------------------------------------------------------------
# Bundle - outgoing multiplexer
# ---------------------------------------------------------------------------

class Bundle:
    """
    Multiplexes a string channel and addressed binary packets into a single
    outgoing byte stream.  Binary packets take priority over string data.
    """

    # prevent binary packets from being delayed by long strings - packets
    # can be injected on chunk boundaries
    STRING_CHUNK_LEN = 24

    def __init__(self) -> None:
        self._str_queue  = queue.Queue()     # queue of bytes (chunked str)
        self._pkt_queue  = queue.Queue()     # queue of bytes (encoded packet)
        self._tx_bytes_avail_callback: Callable[[], None] | None = None

    def set_tx_bytes_available_callback(self, callback: Callable[[], None] | None) -> None:
        """
        Sets a callback which will be invoked in send_string() or send_packet()
        context when either of those functions has placed data in a queue for
        transmission.  Can be used to trigger the actual wire transmission,
        either by directly calling get_tx_bytes() until it returns '' (for a
        single-threaded system), or by setting an event to wake up a separate
        transmit thread which will call get_tx_bytes() until it returns ''.
        Exceptions occurring within the callback will propagate back through
        send_string() or send_packet() to the original caller.  If calling
        send_string() and/or send_packet() from multiple threads, then the
        callback must be thread-safe.
        Call with None to disable the callback.
        """
        self._tx_bytes_avail_callback = callback

    def send_string(self, data: str) -> None:
        """
        Queue a string for transmission on the string channel.  The string
        is split into STRING_CHUNK_LEN-sized chunks before queueing, so a
        packet queued shortly after a long string is not stuck behind the
        whole string in get_tx_bytes().
        Raises UnicodeEncodeError if data contains non-ASCII characters.
        If the tx_bytes_available() callback is set, it will be called
        before send_string returns; if that function blocks, then
        send_string() will also block.  If calling send_string() from
        multiple threads, then the callback must be thread-safe.  Note
        that calling send_string() from multiple threads is not advised,
        chunks of strings from different threads may be intermingled.
        """
        encoded = data.encode('ascii')
        for i in range(0, len(encoded), self.STRING_CHUNK_LEN):
            self._str_queue.put(encoded[i:i + self.STRING_CHUNK_LEN])
        if self._tx_bytes_avail_callback is not None:
            self._tx_bytes_avail_callback()

    def send_packet(self, chan: int, data: bytes) -> None:
        """
        Prepare and queue a binary packet for transmission on the given
        channel.  Maximum data length is 252 bytes.
        Raises ValueError on bad channel number or if data is too long.
        If the tx_bytes_available() callback is set, it will be called
        before send_packet returns; if that function blocks, then
        send_packet() will also block.  If calling send_packet() from
        multiple threads, then the callback must be thread-safe.
        """
        if chan < 0 or chan > 127:
            raise ValueError(f"channel number {chan} must be 0-127")
        if len(data) > 252:
            raise ValueError(f"packet data length {len(data)} exceeds 252")
        data = _crc16_append(_crc_seed(chan), data)
        header = bytes([0x80 | (chan & 0x7F)])
        self._pkt_queue.put(header + _cobs_encode(data) + b'\x00')
        if self._tx_bytes_avail_callback is not None:
            self._tx_bytes_avail_callback()

    def get_tx_bytes(self) -> bytes:
        """
        Return exactly one item ready for transmission: one fully framed
        packet if any is queued, otherwise one string chunk, otherwise b''
        if nothing is queued. Packets always take priority. Call repeatedly
        until it returns b'' -- e.g. in a loop, or once per wire-ready
        notification.
        """
        try:
            return self._pkt_queue.get_nowait()
        except queue.Empty:
            pass
        try:
            return self._str_queue.get_nowait()
        except queue.Empty:
            pass
        return b''

# ---------------------------------------------------------------------------
# Unbundle - incoming demultiplexer
# ---------------------------------------------------------------------------

class Unbundle:
    """
    Demultiplexes an incoming byte stream into a string channel and
    per-channel binary packets.

    String channel data is delivered via callback, which is registered
    by calling listen_string().

    Binary packet channels are registered by calling listen_packet().
    Packets are delivered via callback with the channel number and
    the decoded payload (CRC bytes removed). Packets with bad CRCs
    or other errors are silently dropped and counted in error_count.
    """

    _RX_BUF_SIZE = 30

    def __init__(self) -> None:
        self._string_callback: Callable[[bytes], None] | None = None
        self._channels:        dict[int, Callable[[int, bytes], None]] = {}
        self._channels_lock    = threading.Lock()
        self.error_count       = 0
        # RX state machine state, persists across put_rx_bytes() calls
        self._state      = 'string'       # 'string' or 'packet'
        self._pkt_buf    = bytearray()
        self._pkt_chan   = 0

    def reset_error_count(self) -> None:
        """Reset error counter to zero."""
        self.error_count = 0

    def listen_string(self, callback: Callable[[str], None]) -> None:
        """
        Register a callback to receive string channel data.
        Raises ValueError if callback is None or the string channel
        already has a listener.
        """
        if callback is None:
            raise ValueError("callback must not be None")
        if self._string_callback is not None:
            raise ValueError("string channel already has a listener; call unlisten_string() first")
        self._string_callback = callback

    def unlisten_string(self) -> None:
        """Unregister the callback for the string channel."""
        self._string_callback = None

    def listen_packet(self, chan: int, callback: Callable[[int, bytes], None]) -> None:
        """
        Register a callback for packets on the given channel. Called as
        callback(chan, payload) once a packet is fully assembled and its
        CRC verified. Called from within put_rx_bytes() and must return
        quickly; exceptions propagate up through put_rx_bytes().
        Raises ValueError on a bad channel number, if callback is None,
        or if the channel already has a listener.
        """
        if chan < 0 or chan > 127:
            raise ValueError(f"channel number {chan} must be 0-127")
        if callback is None:
            raise ValueError("callback must not be None")
        with self._channels_lock:
            if chan in self._channels:
                raise ValueError(f"channel {chan} already has a listener; call unlisten_packet() first")
            self._channels[chan] = callback

    def unlisten_packet(self, chan: int) -> None:
        """Unregister the callback for the given channel."""
        with self._channels_lock:
            self._channels.pop(chan, None)

    def _deliver_packet(self, chan: int, encoded: bytes) -> None:
        """COBS-decode, CRC-check, and deliver packet to registered callback."""
        with self._channels_lock:
            callback = self._channels.get(chan)
        if callback is None:
            # unregistered channel - discard
            self.error_count += 1
            return
        try:
            payload = _cobs_decode(encoded)
        except Exception:
            self.error_count += 1
            return
        ok, payload = _crc16_verify(_crc_seed(chan), payload)
        if not ok:
            self.error_count += 1
            return
        callback(chan, payload)

    def put_rx_bytes(self, data: bytes) -> None:
        """
        Process a chunk of received bytes, demultiplexing into string data
        and binary packets and dispatching to registered listeners.

        Packet callback(s) fires once per fully assembled packet, in the
        order packets complete. The string callback fires just before
        put_rx_bytes() returns, only if 'data' contained string channel
        bytes (all of which are concatenated together for the callback).

        Not thread-safe against concurrent calls to itself -- calls must be
        serialized by the caller. Safe to call concurrently with
        listen_packet()/unlisten_packet() from a different thread.
        """
        bp = 0
        data_len = len(data)
        string_out = bytearray()
        while bp < data_len:
            if self._state == 'string':
                if data[bp] >= 0x80:
                    # packet start immediately - no regex needed
                    # and no string data to save
                    index = bp
                    char  = data[bp]
                else:
                    m = _SPECIAL.search(data, bp, data_len)
                    if m is None:
                        # no special byte
                        # everything after bp is string data
                        string_out.extend(data[bp:data_len])
                        bp = data_len
                        continue
                    # packet start detected
                    # everything before index is string data
                    index = m.start()
                    char  = data[index]
                    string_out.extend(data[bp:index])
                # packet start found at index
                self._pkt_chan = char & 0x7F
                self._pkt_buf.clear()
                bp = index + 1
                self._state = 'packet'
            else:
                # state == 'packet': scan for packet terminator (0x00)
                index = data.find(0, bp, data_len)
                if index == -1:
                    # no terminator yet; accumulate packet data
                    self._pkt_buf.extend(data[bp:data_len])
                    if len(self._pkt_buf) > 255:
                        self.error_count += 1
                        self._pkt_buf.clear()
                        self._state = 'string'
                    bp = data_len
                else:
                    # terminator found; deliver packet
                    self._pkt_buf.extend(data[bp:index])
                    bp = index + 1
                    if len(self._pkt_buf) > 255:
                        self.error_count += 1
                    else:
                        self._deliver_packet(self._pkt_chan, bytes(self._pkt_buf))
                    self._pkt_buf.clear()
                    # remainder of rx_buf might be string data
                    # next pass of loop will handle it
                    self._state = 'string'
        if string_out and self._string_callback is not None:
            self._string_callback(bytes(string_out).decode('ascii'))
