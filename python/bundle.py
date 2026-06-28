# bundle.py
# Multiplexed string and binary packet channel over a shared byte stream.
#
# Bundle accepts str (string channel) and addressed binary packets from
# callers, multiplexes them into a single outgoing byte stream.  Binary
# packets take priority over string channel data.
#
# Unbundle reads an incoming byte stream, demultiplexes into a string
# channel queue and per-address packet queues.  String channel data is
# delivered to the queue as it arrives.
#
# Binary packets can optionally include a CRC; if so, packets with bad
# CRCs are dropped and counted.  The string channel has no error detection.
#
# The string channel can transmit only ASCII characters; non-ASCII will
# result in a UnicodeEncodeError exception.  This is an inherent
# limitation of the protocol, which uses the fact that ASCII characters
# are seven bits to manage string/binary transitions.
#
# The COBS encoding variant in use limits the binary packet length to
# 254 bytes.  Binary packets with CRC are limited to 252 bytes.
# Packets that are too large will raise ValueError.
#
# There are 128 binary packet channels, numbered 0x00 to 0x7F (0 to 127).
# Only one listener is allowed per channel.  Each binary packet channel
# must be configured with configure_channel() before use; this establishes
# whether CRC is used on that channel.  On Bundle, configure_channel() must
# be called before send_packet().  On Unbundle, configure_channel() must be
# called before listen().  Attempting to use an unconfigured channel raises
# ValueError.
#
# Both classes take an open io.RawIOBase-compatible stream (e.g. a
# pyserial.Serial) at init time.  Port lifecycle is the caller's
# responsibility.  Call start() to begin the background thread, stop() to
# end it.
#
# Wire format:
#   String channel:  bytes 0x00-0x7F, sent as-is
#   Packet start:    0x80 | (addr & 0x7F)
#   Packet payload:  COBS-encoded data bytes
#   Packet end:      0x00

import io
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
# Polynomial 0x1021, initial value 0xFFFF, no reflection.
# ---------------------------------------------------------------------------

def _crc16_append(data: bytes) -> bytes:
    """
    Append 2-byte little-endian CRC-16-CCITT to data.
    """
    crc = binascii.crc_hqx(data, 0xFFFF)
    return data + bytes([crc & 0xFF, crc >> 8])


def _crc16_verify(data: bytes) -> tuple[bool, bytes]:
    """
    Verify CRC-16-CCITT appended to data.
    Returns (True, payload) on success, (False, b'') on failure.
    payload has the 2 CRC bytes removed.
    """
    if len(data) < 2:
        return False, b''
    payload = data[:-2]
    crc_recv = data[-2] | (data[-1] << 8)
    crc_calc = binascii.crc_hqx(payload, 0xFFFF)
    if crc_calc != crc_recv:
        return False, b''
    return True, payload


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

    def __init__(self) -> None:
        self._stream:    io.RawIOBase | None = None
        self._on_error:  Callable[[Exception], None] | None = None
        self._str_queue  = queue.Queue()     # queue of bytes (encoded str)
        self._pkt_queue  = queue.Queue()     # queue of (addr, data) tuples
        self._channels:  dict[int, bool] = {}   # ( channel, crc )
        self._stop_flag  = False
        self._tx_event   = threading.Event()
        self._thread     = None

    def start(self, stream: io.RawIOBase,
              on_error: Callable[[Exception], None]) -> None:
        """
        Start the transmit background thread using the given stream.
        If a stream error occurs, on_error is called with the stream
        exception, in the context of the Bundle worker thread.  GUI
        callers or other non-thread safe users of the class must relay
        the error to their main thread in an appropriate manner.
        The stream must already be open.
        """
        if self._thread is not None:
            raise RuntimeError(f"start() called when already running")
        self._stream    = stream
        self._on_error  = on_error
        self._stop_flag = False
        self._tx_event.clear()
        self._thread = threading.Thread(target=self._tx_worker, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """
        Signal the transmit thread to stop and wait for it to finish.
        Clears on_error so the callback does not fire during deliberate shutdown.
        Does not close the stream; that is the caller's responsibility.
        """
        self._on_error  = None
        self._stop_flag = True
        self._tx_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join()
        self._thread = None
        self._stream = None

    def configure_channel(self, addr: int, crc: bool = True) -> None:
        """
        Configure a binary packet channel.
        Must be called before send_packet() on this channel.
        addr must be 0-127.  crc=True means CRC-16 is appended to all
        outgoing packets on this channel.
        """
        if addr < 0 or addr > 127:
            raise ValueError(f"channel address {addr} out of range 0-127")
        self._channels[addr] = crc

    def write_ascii(self, data: str) -> None:
        """
        Queue a string for transmission on the string channel.
        Raises UnicodeEncodeError if data contains non-ASCII characters.
        """
        self._str_queue.put(data.encode('ascii'))
        self._tx_event.set()

    def send_packet(self, addr: int, data: bytes) -> None:
        """
        Queue a binary packet for transmission on the given channel.
        configure_channel() must have been called for this addr.
        Maximum data length is 252 bytes if channel uses CRC, 254 otherwise.
        Raises ValueError if channel is unconfigured or data is too long.
        """
        if addr not in self._channels:
            raise ValueError(f"channel {addr} not configured; call configure_channel() first")
        crc = self._channels[addr]
        max_len = 252 if crc else 254
        if len(data) > max_len:
            raise ValueError(f"packet data length {len(data)} exceeds maximum {max_len} for channel {addr}")
        if crc:
            data = _crc16_append(data)
        self._pkt_queue.put((addr, data))
        self._tx_event.set()

    def _tx_worker(self) -> None:
        try:
            while True:
                self._tx_event.wait()
                self._tx_event.clear()
                if self._stop_flag:
                    return
                # drain packet queue first (higher priority)
                while True:
                    try:
                        addr, data = self._pkt_queue.get_nowait()
                        header = bytes([0x80 | (addr & 0x7F)])
                        encoded = _cobs_encode(data)
                        self._stream.write(header + encoded + b'\x00')
                    except queue.Empty:
                        break
                # then drain string queue
                while True:
                    try:
                        data = self._str_queue.get_nowait()
                        self._stream.write(data)
                    except queue.Empty:
                        break
        except Exception as e:
            if self._on_error is not None:
                self._on_error(e)

# ---------------------------------------------------------------------------
# Unbundle - incoming demultiplexer
# ---------------------------------------------------------------------------

class Unbundle:
    """
    Demultiplexes an incoming byte stream into a string channel queue and
    per-address binary packet queues.

    String channel data is delivered to the string queue as it arrives.

    Binary packet channels must be configured with configure_channel()
    before registering a listener with listen().  Packets are delivered
    as bytes objects containing the decoded payload (CRC bytes removed
    if channel uses CRC).  Packets with bad CRCs or other errors are
    silently dropped and counted in bad_pkt_count.
    """

    _RX_BUF_SIZE = 30

    def __init__(self) -> None:
        self._stream:       io.RawIOBase | None = None
        self._on_error:     Callable[[Exception], None] | None = None
        self._thread        = None
        self._stop_flag     = False
        self._str_queue     = None          # set by listen_str()
        self._channels:     dict[int, tuple[bool, queue.Queue | None, Callable | None]] = {}
                            # channel: (crc, queue, callback)
        self._channels_lock = threading.Lock()
        self.bad_pkt_count  = 0

    def start(self, stream: io.RawIOBase,
            on_error: Callable[[Exception], None]) -> None:
        """
        Start the receive background thread using the given stream.
        The stream must implement readinto() and must not block indefinitely
        when no data is available.
        For pyserial.Serial, set a read timeout before calling start(). A
        value of 0.01 to 0.1 seconds is recommended but other values
        including zero will work.  None is not permitted.  Longer timeouts
        will increase latency when traffic is light and doesn't fill the
        receive buffer (_RX_BUF_SIZE).
        File objects satisfy this requirement naturally.
        Compatibility with other stream types (network sockets, asyncio
        streams, pipes) has not been verified.
        on_error is called with the stream exception if a stream error occurs,
        in the context of the Unbundle worker thread.  GUI callers or other
        non-thread-safe users of the class must relay the error to their main
        thread in an appropriate manner.
        Does not close the stream on error or stop; that is the caller's
        responsibility.
        """
        if self._thread is not None:
            raise RuntimeError(f"start() called when already running")
        self._stream    = stream
        self._on_error  = on_error
        self._stop_flag = False
        self._thread    = threading.Thread(target=self._rx_worker, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """
        Signal the receive thread to stop and wait for it to finish.
        Clears on_error so the callback does not fire during deliberate
        shutdown.  The thread will exit when the stream times out or
        when the next data arrives, whichever comes first.
        Does not close the stream; that is the caller's responsibility.
        """
        self._on_error  = None
        self._stop_flag = True
        if self._thread is not None and self._thread.is_alive():
            self._thread.join()
        self._thread = None
        self._stream = None

    def reset_counter(self) -> None:
        """Reset bad packet counter to zero."""
        self.bad_pkt_count = 0

    def configure_channel(self, addr: int, crc: bool = True) -> None:
        """
        Configure a binary packet channel.
        Must be called before listen() on this channel.
        addr must be 0-127.  crc=True means incoming packets on this
        channel are expected to carry a CRC-16; packets with bad CRCs
        are dropped and counted in bad_pkt_count.
        """
        if addr < 0 or addr > 127:
            raise ValueError(f"channel address {addr} out of range 0-127")
        with self._channels_lock:
            self._channels[addr] = (crc, None, None)

    def listen_str(self, q: queue.Queue) -> None:
        """
        Register a queue to receive string channel data.
        Raises ValueError if the string channel already has a
        listener queue.
        """
        if self._str_queue is not None:
            raise ValueError("string channel already has a listener; call unlisten_str() first")
        self._str_queue = q

    def unlisten_str(self) -> None:
        """Unregister the queue for the string channel."""
        self._str_queue = None

    def listen(self, addr: int,
            q: queue.Queue | None = None,
            callback: Callable[[bytes], None] | None = None) -> None:
        """
        Register a queue or callback for packets on the given channel.
        configure_channel() must have been called for this addr.
        Exactly one of q or callback must be provided.
        If q is provided, packets are delivered via q.put(payload).
        If callback is provided, it is called directly in _rx_worker's
        thread context and must return quickly.  Exceptions in the
        callback will propagate up and result in a call to on_error.
        Raises ValueError if channel is unconfigured, already has a
        listener, or neither/both of q and callback are provided.
        """
        if (q is None) == (callback is None):
            raise ValueError("exactly one of q or callback must be provided")
        if addr not in self._channels:
            raise ValueError(f"channel {addr} not configured; call configure_channel() first")
        with self._channels_lock:
            crc, existing_q, existing_cb = self._channels[addr]
            if existing_q is not None or existing_cb is not None:
                raise ValueError(f"channel {addr} already has a listener; call unlisten() first")
            self._channels[addr] = (crc, q, callback)

    def unlisten(self, addr: int) -> None:
        """Unregister the queue for the given channel."""
        with self._channels_lock:
            if addr in self._channels:
                crc, _, _ = self._channels[addr]
                self._channels[addr] = (crc, None, None)

    def _queue_str(self, data: bytes | bytearray | memoryview) -> None:
        """Deliver string data directly to the string queue if a listener is registered."""
        if self._str_queue is not None:
            self._str_queue.put(bytes(data).decode('ascii', errors='replace'))

    def _deliver_packet(self, addr: int, encoded: bytes) -> None:
        """COBS-decode, optionally CRC-check, and deliver packet to registered queue."""
        with self._channels_lock:
            entry = self._channels.get(addr)
        if entry is None:
            # unregistered channel - discard
            self.bad_pkt_count += 1
            return
        crc, q, callback = entry
        if q is None and callback is None:
            # configured but no listener yet - discard
            self.bad_pkt_count += 1
            return
        try:
            payload = _cobs_decode(encoded)
        except Exception:
            self.bad_pkt_count += 1
            return
        if crc:
            ok, payload = _crc16_verify(payload)
            if not ok:
                self.bad_pkt_count += 1
                return
        if callback is not None:
            callback(payload)
        else:
            q.put(payload)

    def _rx_worker(self) -> None:
        """Background thread: read chunks, demultiplex into string and packet channels."""
        rx_buf   = bytearray(self._RX_BUF_SIZE)
        pkt_buf = bytearray(256)  # preallocate for largest packet
        pkt_buf.clear()
        pkt_addr = 0
        state    = 'string'     # 'string' or 'packet'
        try:
            while not self._stop_flag:
                data_len = self._stream.readinto(rx_buf)
                bp = 0
                while bp < data_len:
                    if state == 'string':
                        if rx_buf[bp] >= 0x80:
                            # packet start immediately - no regex needed
                            # and no string data to save
                            index = bp
                            char  = rx_buf[bp]
                        else:
                            m = _SPECIAL.search(rx_buf, bp, data_len)
                            if m is None:
                                # no special byte
                                # everything after bp is string data
                                self._queue_str(rx_buf[bp:data_len])
                                bp = data_len
                                continue
                            # packet start detected
                            # everything before index is string data
                            index = m.start()
                            char  = rx_buf[index]
                            self._queue_str(rx_buf[bp:index])
                        # packet start found at index
                        pkt_addr = char & 0x7F
                        pkt_buf.clear()
                        bp = index + 1
                        state = 'packet'
                    else:
                        # state == 'packet': scan for packet terminator (0x00)
                        index = rx_buf.find(0, bp, data_len)
                        if index == -1:
                            # no terminator yet; accumulate packet data
                            pkt_buf.extend(rx_buf[bp:data_len])
                            if len(pkt_buf) > 255:
                                self.bad_pkt_count += 1
                                pkt_buf.clear()
                                state = 'string'
                            bp = data_len
                        else:
                            # terminator found; deliver packet
                            pkt_buf.extend(rx_buf[bp:index])
                            bp = index + 1
                            if len(pkt_buf) > 255:
                                self.bad_pkt_count += 1
                            else:
                                self._deliver_packet(pkt_addr, bytes(pkt_buf))
                            pkt_buf.clear()
                            # remainder of rx_buf might be string data
                            # next pass of loop will handle it
                            state = 'string'
        except Exception as e:
            if self._on_error is not None:
                self._on_error(e)

