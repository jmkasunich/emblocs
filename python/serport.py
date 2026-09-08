#!/usr/bin/env python3
"""
serport.py

Non-GUI wrapper combining Bundle, Unbundle, and Serial port I/O.
Manages RX and TX threads for multiplexed string and binary packet data
over a serial connection.
"""

import threading
import time
import queue
from datetime import datetime
from serial import Serial, SerialException
import serial.tools.list_ports

from bundle import Bundle, Unbundle


class SerPort:
    """
    Wrapper around Bundle, Unbundle, and Serial that manages transmit and
    receive threads. Clients can listen on packet channels or string channel,
    and can send strings or packets.
    """

    def __init__(self, port: str, baud: int, debug: bool = False) -> None:
        """
        Initialize and connect to a serial port.

        Args:
            port: Serial port name (e.g., '/dev/ttyUSB0' or 'COM3')
            baud: Baud rate (e.g., 115200)
            debug: Enable debug output

        Raises:
            SerialException if the port cannot be opened
        """
        self.debug = debug
        self.port = port
        self.baud = baud

        # Create serial port instance
        self.serial = Serial()
        self.serial.port = port
        self.serial.baudrate = baud
        self.serial.timeout = 0.1
        self.serial.open()

        if self.debug:
            print(f"SerPort: connected to {port} at {baud} baud")

        # Create Bundle (TX) and Unbundle (RX)
        self.bundle = Bundle()
        self.unbundle = Unbundle()

        # Thread control
        self.stop_event = threading.Event()
        self.tx_event = threading.Event()
        self.rx_thread = None
        self.tx_thread = None

        # Register TX availability callback with Bundle
        self.bundle.set_tx_bytes_available_callback(self.tx_event.set)

        # Start RX and TX threads
        self.rx_thread = threading.Thread(target=self._rx_worker, daemon=False)
        self.tx_thread = threading.Thread(target=self._tx_worker, daemon=False)
        self.rx_thread.start()
        self.tx_thread.start()

    @staticmethod
    def get_available_ports():
        """
        Get a list of available serial ports.

        Returns:
            List of port name strings (e.g., ['/dev/ttyUSB0', '/dev/ttyUSB1'])
        """
        return [port.device for port in serial.tools.list_ports.comports()]

    def send_string(self, data: str) -> None:
        """
        Queue a string for transmission on the string channel.

        Args:
            data: String to send (ASCII only)

        Raises:
            UnicodeEncodeError if data contains non-ASCII characters
        """
        if self.debug:
            print(f"SerPort.send_string: {len(data)} chars")
        self.bundle.send_string(data)

    def send_packet(self, chan: int, data: bytes) -> None:
        """
        Queue a binary packet for transmission.

        Args:
            chan: Packet channel (0-127)
            data: Packet payload (max 252 bytes)

        Raises:
            ValueError if channel or data length is invalid
        """
        if self.debug:
            print(f"SerPort.send_packet: chan={chan}, len={len(data)}")
        self.bundle.send_packet(chan, data)

    def listen_on_packet_channel(self, chan: int, q: queue.Queue, with_timestamp: bool = False) -> None:
        """
        Register a queue to receive packets on the given channel.

        Args:
            chan: Packet channel (0-127)
            q: Queue to receive data
            with_timestamp: If False (default), queue receives just the payload (bytes).
                           If True, queue receives (timestamp, payload) tuples.

        Raises:
            ValueError if channel is invalid or already has a listener
        """
        if with_timestamp:
            def callback(chan, payload):
                q.put((datetime.now(), payload))
        else:
            def callback(chan, payload):
                q.put(payload)

        if self.debug:
            print(f"SerPort.listen_on_packet_channel: chan={chan}, with_timestamp={with_timestamp}")
        self.unbundle.listen_packet(chan, callback)

    def listen_on_string_channel(self, q: queue.Queue, with_timestamp: bool = False) -> None:
        """
        Register a queue to receive string channel data.

        Args:
            q: Queue to receive data
            with_timestamp: If False (default), queue receives just the string (str).
                           If True, queue receives (timestamp, string) tuples.

        Raises:
            ValueError if string channel already has a listener
        """
        if with_timestamp:
            def callback(data):
                q.put((datetime.now(), data))
        else:
            def callback(data):
                q.put(data)

        if self.debug:
            print(f"SerPort.listen_on_string_channel: with_timestamp={with_timestamp}")
        self.unbundle.listen_string(callback)

    def close(self) -> None:
        """
        Stop threads and close the serial port.
        """
        if self.debug:
            print("SerPort.close: stopping threads")
        self.stop_event.set()

        if self.rx_thread is not None and self.rx_thread.is_alive():
            self.rx_thread.join()
        if self.tx_thread is not None and self.tx_thread.is_alive():
            self.tx_thread.join()

        if self.serial.is_open:
            self.serial.close()

        if self.debug:
            print("SerPort.close: done")

    def __del__(self) -> None:
        """
        Resource cleanup safety net.
        Called when SerPort instance is garbage collected.
        Quietly closes the connection if it wasn't already closed.
        """
        try:
            if self.serial and self.serial.is_open:
                self.stop_event.set()
                if self.serial.is_open:
                    self.serial.close()
        except Exception:
            # Silently ignore errors during cleanup
            pass

    # -----------------------------------------------------------------------
    # Worker threads
    # -----------------------------------------------------------------------

    def _rx_worker(self) -> None:
        """
        Receive thread: read from serial port and feed to Unbundle.
        Unbundle's callbacks fire in this thread context and queue data
        for the main thread to consume.
        """
        if self.debug:
            print("SerPort._rx_worker: starting")

        while not self.stop_event.is_set():
            try:
                data = self.serial.read(256)
                if data:
                    if self.debug:
                        print(f"SerPort._rx_worker: read {len(data)} bytes")
                    self.unbundle.put_rx_bytes(data)
            except SerialException as e:
                if not self.stop_event.is_set():
                    print(f"SerPort._rx_worker: SerialException: {e}")
                break
            except Exception as e:
                if not self.stop_event.is_set():
                    print(f"SerPort._rx_worker: Exception: {e}")
                break

        if self.debug:
            print("SerPort._rx_worker: stopping")

    def _tx_worker(self) -> None:
        """
        Transmit thread: wait on tx_event for data availability, drain Bundle,
        and write to serial port. Packets take priority over string data
        (Bundle.get_tx_bytes handles this).
        """
        if self.debug:
            print("SerPort._tx_worker: starting")

        while not self.stop_event.is_set():
            try:
                # Wait for Bundle to signal that data is available
                # Timeout prevents blocking indefinitely if stop_event is set
                self.tx_event.wait(timeout=0.1)
                self.tx_event.clear()

                # Drain all available data from Bundle
                while True:
                    data = self.bundle.get_tx_bytes()
                    if not data:
                        break
                    if self.debug:
                        print(f"SerPort._tx_worker: write {len(data)} bytes")
                    self.serial.write(data)

            except SerialException as e:
                if not self.stop_event.is_set():
                    print(f"SerPort._tx_worker: SerialException: {e}")
                break
            except Exception as e:
                if not self.stop_event.is_set():
                    print(f"SerPort._tx_worker: Exception: {e}")
                break

        if self.debug:
            print("SerPort._tx_worker: stopping")
