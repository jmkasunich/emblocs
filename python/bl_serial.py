#! /usr/bin/env python3
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from serial import Serial, SerialException
import serial.tools.list_ports
import threading
import queue
from datetime import datetime

import time

class SerPort(ttk.Frame):
    '''
    serial port selection/access widget

    Implements the host side of the EMBLOCS serial protocol described in
    `src/misc/serial.h`.  ASCII characters (0x01..0x7F) and binary packets
    (leading byte >=0x80 containing address, followed by COBS payload and
    terminating 0x00) share the same stream.  A receive thread separates the
    two streams, decodes packets, adds timestamps, places text and packets
    into their respective receive queues. The GUI thread can poll these
    queues to update widgets.  A transmit thread drains two queues (text
    and packets), performs COBS encoding on outgoing packets, and sends
    both text and packets to the serial port.
    '''
    def __init__(self, parent, config, **kwargs):
        '''
        :param port: desired COM port name
        :param baud: desired baud rate (must appear in list below)
        '''
        # Call the parent class (ttk.Frame) constructor
        super().__init__(parent, **kwargs)

        self.cfgdata = config.data
        self.serport = Serial()

        padx=5
        pady=5

        self.port_label = ttk.Label(self, text="Port:")
        self.port_var = tk.StringVar(value=self.cfgdata['port']['port'])
        self.port_combobox = ttk.Combobox(self, postcommand=self.check_ports, textvariable=self.port_var, state="normal")

        self.baud_label = ttk.Label(self, text="Baud Rate:")
        self.baud_var = tk.StringVar(value=self.cfgdata['port']['baud'])
        self.baudrates = ('2400', '4800', '9600', '115.2K', '1.0M')
        self.baud_combobox = ttk.Combobox(self, values=self.baudrates, textvariable=self.baud_var, state="normal")

        self.connect_button = ttk.Button(self, text="Connect", command=self.connect)
        self.connected = False

        self.port_label.grid(row=0, column=0, padx=padx, pady=pady)
        self.port_combobox.grid(row=0, column=1, padx=padx, pady=pady)
        self.baud_label.grid(row=0, column=2, padx=padx, pady=pady)
        self.baud_combobox.grid(row=0, column=3, padx=padx, pady=pady)
        self.connect_button.grid(row=0, column=4, padx=padx, pady=pady)

        self.stop_event = threading.Event()

        # receive queues/state
        self.rx_thread = None
        self.rx_text_queue = queue.Queue()
        self.rx_packet_queue = queue.Queue()

        # transmit queues
        self.tx_thread = None
        self.tx_text_queue = queue.Queue()
        self.tx_packet_queue = queue.Queue()      # tuples of (addr, bytes)

        # autoconnect
        if self.port_var.get() != '':
            self.after(100, self.connect)


    @staticmethod
    def add_config_data(config):
        '''
        adds config fields needed by a SerPort object
        should be called before a SerPort is created

        :param config: config object to which fields are added
        '''
        config.data['port']={}
        config.data['port']['port']=''
        config.data['port']['baud']='115.2K'

    def connect(self):
        '''
        attempts to connect to the selected serial port at the
        selected baud rate
        if successfull, kicks off a thread to manage serial
        port data and changes the 'connect' button to 'disconnect'
        '''
        print("SerPort.connect() called")
        if self.connected :
            self.disconnect
        baudstring = self.baud_var.get()
        baudrate = self.validate_baud(baudstring)
        if ( baudrate == 0 ) :
            return
        self.serport.baudrate = baudrate
        self.serport.port = self.port_var.get()
        self.serport.timeout = 0.1
        try :
            self.serport.open()
        except ValueError :
            messagebox.showerror(title="Error", message="ValueError opening port.")
            return
        except SerialException :
            messagebox.showerror(title="Error", message="SerialException opening port.")
            return
        print(f"connected to {self.serport.port} at {self.serport.baudrate}")
        self.port_combobox.config(state="disabled")
        self.baud_combobox.config(state="disabled")
        self.cfgdata['port']['port'] = self.serport.port
        self.cfgdata['port']['baud'] = self.serport.baudrate

        # create threads for Rx and Tx
        self.rx_thread = threading.Thread(target=self._rx_worker)
        self.tx_thread = threading.Thread(target=self._tx_worker)
        print("starting threads")
        self.stop_event.clear()
        self.rx_thread.start()
        self.tx_thread.start()
        self.connect_button['command'] = self.disconnect
        self.connect_button['text'] = 'Disconnect'
        self.connected = True

    def disconnect_ignore_widgets(self):
        '''
        disconnects from the serial port and stops the data
        processing threads, but doesn't touch any TkInter
        widgets; this method can safely be called after
        the main loop exits.
        '''
        print("SerPort.disconnect_ignore_widgets() called")
        # signal threads to exit
        self.stop_event.set()
        if self.rx_thread is not None and self.rx_thread.is_alive():
            print("stopping rx thread")
            self.rx_thread.join()
            print("rx thread stopped")
        if self.tx_thread is not None and self.tx_thread.is_alive():
            print("stopping tx thread")
            self.tx_thread.join()
            print("tx thread stopped")
        if self.serport.is_open :
            print("closing port")
            self.serport.close()
        self.connected = False

    def disconnect(self):
        '''
        disconnects from serial port and changes the
        "disconnect" button to "connect"
        '''
        print("SerPort.disconnect() called")
        self.disconnect_ignore_widgets()
        self.connect_button['command'] = self.connect
        self.connect_button['text'] = 'Connect'
        self.port_combobox.config(state="normal")
        self.baud_combobox.config(state="normal")


    def _rx_worker(self):
        print("start of rx thread")
        rx_buf = bytearray(1024)
        text_buf = bytearray()
        packet_buf = bytearray()
        state = 'text'
        while not self.stop_event.is_set():
            data_len = self.serport.readinto(rx_buf)
            if data_len == 0:
                # timeout with no data; flush partial text
                if len(text_buf) > 0:
                    print(f"{state=} timeout, {len(text_buf)=}")
                    self.rx_text_queue.put((datetime.now(), bytes(text_buf)))
                    text_buf.clear()
                continue
            bp = 0
            print(f"{state=} read {data_len=}")
            while bp < data_len:
                if state == 'text':
                    #print(f"{state=} searching {rx_buf[bp:data_len]=} for newline or packet start")
                    index, char = next(((i, b) for i, b in enumerate(rx_buf[bp:data_len]) if b >= 0x80 or b == ord('\n')), (data_len, None))
                    #print(f"{state=} {index=}, {char=}")
                    if char is None:
                        # no packet start or newline found; treat everything as text for now
                        text_buf.extend(rx_buf[bp:data_len])
                        print(f"{state=} no match, {len(text_buf)=}")
                        bp = data_len
                    elif char == ord('\n'):
                        # newline found; treat everything up to and including the newline as text
                        text_buf.extend(rx_buf[bp:bp+index+1])
                        bp += index + 1
                        # and send it to the text queue with a timestamp
                        print(f"{state=} newline, {len(text_buf)=}")
                        self.rx_text_queue.put((datetime.now(), bytes(text_buf)))
                        text_buf.clear()
                    else:
                        # packet start found; treat everything up to the packet start as text, then switch to packet mode
                        text_buf.extend(rx_buf[bp:bp+index])
                        print(f"{state=} packet start, {len(text_buf)=}")
                        bp += index + 1
                        packet_buf.clear()
                        packet = BinPacket()
                        packet.set_addr(char & 0x7f)
                        state = 'packet'
                else:  # in packet
                    #print(f"{state=} searching {rx_buf[bp:data_len]=} for packet end (0)")
                    index = rx_buf.find(0, bp, data_len)
                    print(f"{state=} {index=}, {rx_buf[index]=}")
                    if index == -1:
                        # no packet terminator found; treat everything as packet data for now
                        packet_buf.extend(rx_buf[bp:data_len])
                        print(f"{state=} no match, {len(packet_buf)=}")
                        bp = data_len
                    else:
                        # packet terminator found; treat everything up to the terminator as packet data, then switch to text mode
                        packet_buf.extend(rx_buf[bp:index])
                        print(f"{state=} end of packet, {len(packet_buf)=}")
                        bp = index + 1
                        if ( len(packet_buf) > 255 ):
                            # packet too long; discard it
                            packet_buf.clear()
                        else:
                            # decode packet and send it to the packet queue with the address and a timestamp
                            packet.cobs_decode_from_bytes(bytes(packet_buf))
                            self.rx_packet_queue.put((datetime.now(), packet))
                        text_buf.clear()
                        state = 'text'
        print("end of rx thread")

    def get_rx_text(self):
        '''Return next received text tuple (timestamp, data) if available, else None.'''
        try :
            return self.rx_text_queue.get_nowait()
        except queue.Empty :
            return None

    def get_rx_packet(self):
        '''Return next received packet tuple (timestamp, data) if available, else None.'''
        try :
            return self.rx_packet_queue.get_nowait()
        except queue.Empty :
            return None

    def validate_baud(self, baud_str):
        baud_str = baud_str.strip()
        suffix = baud_str.lstrip('0123456789.')
        try:
            if ( len(suffix) == 0 ) :
                return int(baud_str)
            elif ( suffix[0] in 'kK' ) :
                return int(1e3*float(baud_str.partition(suffix[0])[0]))
            elif ( suffix[0] in 'mM' ) :
                return int(1e6*float(baud_str.partition(suffix[0])[0]))
            else :
                raise ValueError
        except ValueError :
            messagebox.showerror(title="Error", message="Invalid baud rate.")
            return 0


    def check_ports(self):
        '''
        checks the OS for available serial ports and updates the drop-down list
        '''
        self.port_combobox['values'] = [port.device for port in serial.tools.list_ports.comports()]

    # ------------------------------------------------------------------
    # transmit helpers
    # ------------------------------------------------------------------
    def _tx_worker(self):
        """Thread that handles outgoing text and packet queues."""
        print("start of tx thread")
        while not self.stop_event.is_set():
            try:
                text = self.tx_text_queue.get(timeout=0.1)
            except queue.Empty:
                text = None
            if text is not None:
                self.serport.write(text)
            try:
                pkt = self.tx_packet_queue.get_nowait()
            except queue.Empty:
                pkt = None
            if pkt is not None:
                encoded = pkt.encode_to_bytes()
                header = bytes([0x80 | (pkt.get_addr() & 0x7F)])
                self.serport.write(header + pkt.encode_to_bytes() + b"\x00")
        print("end of tx thread")

    def put_tx_text(self, command):
        '''queue a text command for transmission (will be sent verbatim).'''
        if self.connected:
            data = command.encode('ascii', errors='replace')
            self.tx_text_queue.put(data)

    def put_tx_packet(self, addr:int, data:bytes):
        '''queue a binary packet for transmission using new protocol.'''
        if ( len(data) > 254 ):
            raise ValueError("data length exceeds maximum of 254 bytes")
        if ( addr < 0 or addr > 127 ):
            raise ValueError("address must be between 0 and 127")
        packet = BinPacket()
        packet.set_addr(addr)
        packet.set_raw_bytes(data)
        if self.connected:
            self.tx_packet_queue.put(packet)

class BinPacket:
    '''
    class for managing binary packets
    max packet length is 254 bytes (due to COBS encoding limits)
    as much processing as possible is done in-place to avoid unnecessary copying of data
    '''
    def __init__(self):
        self.addr = 0
        self.cobs_byte = 0
        self.data_len = 0
        self.buf = bytearray(254)

    def get_addr(self):
        return self.addr

    def get_data_len(self):
        return self.data_len

    def set_addr(self, addr):
        self.addr = addr & 0x7F

    def set_data_len(self, length):
        if length < 0 or length > 254:
            raise ValueError("data length must be between 0 and 254")
        self.data_len = length

    def set_raw_bytes(self, data: bytes):
        """Set the packet's buffer to the given raw bytes; updates data_len; resets cobs_byte."""
        if len(data) > 254:
            raise ValueError("data length exceeds maximum of 254 bytes")
        self.buf[:len(data)] = data
        self.data_len = len(data)
        self.cobs_byte = 0

    def get_raw_bytes(self) -> bytes:
        """Return the raw bytes currently in the packet's buffer."""
        return bytes(self.buf[:self.data_len])

    def set_encoded_bytes(self, data: bytes):
        """Store COBS-encoded bytes directly into the buffer; updates data_len and cobs_byte."""
        if not data:
            raise ValueError("encoded data must alwayd be at least 1 byte")
        self.cobs_byte = data[0]
        encoded_payload = data[1:]
        if len(encoded_payload) > 254:
            raise ValueError("encoded payload length exceeds maximum of 254 bytes")
        self.buf[:len(encoded_payload)] = encoded_payload
        self.data_len = len(encoded_payload)

    def get_encoded_bytes(self) -> bytes:
        """Return the COBS-encoded bytes currently in the packet's buffer, including the leading code byte."""
        return bytes([self.cobs_byte]) + bytes(self.buf[:self.data_len])

    def cobs_encode_in_place(self):
        # ensure that data_len is within the allowed bounds
        if self.data_len < 0 or self.data_len > 254:
            raise ValueError("data_len out of range for COBS encode")

        end = self.data_len
        next_zero = self.buf.find(0, 0, end)
        if next_zero == -1:
            self.cobs_byte = self.data_len + 1
            return
        self.cobs_byte = next_zero + 1
        cp = next_zero
        while True:
            next_zero = self.buf.find(0, cp + 1, end)
            if next_zero == -1:
                self.buf[cp] = end - cp
                return
            self.buf[cp] = next_zero - cp
            cp = next_zero

    def cobs_encode_to_bytes(self):
        # ensure that data_len is within the allowed bounds
        if self.data_len < 0 or self.data_len > 254:
            raise ValueError("data_len out of range for COBS encode")

        out = bytearray(self.data_len + 1)
        out[1:] = self.buf[:self.data_len]
        end = self.data_len + 1
        cp = 0
        while True:
            next_zero = out.find(0, cp + 1, end)
            if next_zero == -1:
                out[cp] = end - cp
                return bytes(out)
            out[cp] = next_zero - cp
            cp = next_zero

    def cobs_decode_from_bytes(self, data: bytes):
        if not data:
            raise ValueError("zero length encoded data")
        if len(data) > 255:
            raise ValueError("encoded data exceeds maximum length of 255 bytes")
        # copy encoded data into buffer for in-place decoding
        end = len(data) - 1
        self.buf[:end] = data[1:]
        code = data[0]
        bp = code - 1
        while bp < end:
            code = self.buf[bp]
            self.buf[bp] = 0
            bp += code
        self.data_len = end

    def cobs_decode_in_place(self):
        bp = self.cobs_byte - 1  # index into data
        end = self.data_len
        while bp < end:
            code = self.buf[bp]
            self.buf[bp] = 0
            bp += code


