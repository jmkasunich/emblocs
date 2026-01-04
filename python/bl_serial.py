#! /usr/bin/env python3
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from serial import Serial, SerialException
import serial.tools.list_ports
import threading

import time

class SerPort(ttk.Frame):
    '''
    serial port selection/access widget
    '''
    def __init__(self, parent, port='', baud='115.2K', **kwargs):
        '''
        :param port: desired COM port name
        :param baud: desired baud rate (must appear in list below)
        '''
        # Call the parent class (ttk.Frame) constructor
        super().__init__(parent, **kwargs)

        self.serport = Serial()

        padx=5
        pady=5

        self.port_label = ttk.Label(self, text="Port:")

        self.port_var = tk.StringVar(value=port)
        self.port_old = self.port_var.get()
        self.port_var.trace_add('write', self.port_changed)
        self.port_combobox = ttk.Combobox(self, postcommand=self.check_ports, textvariable=self.port_var, state="readonly")

        self.baud_label = ttk.Label(self, text="Baud Rate:")

        self.baud_var = tk.StringVar(value=baud)
        self.baud_old = self.baud_var.get()
        self.baud_var.trace_add('write', self.baud_changed)
        self.baudrates = ('2400', '4800', '9600', '115.2K', '1.0M')
        self.baud_combobox = ttk.Combobox(self, values=self.baudrates, textvariable=self.baud_var, state="normal")

        self.connect_button = ttk.Button(self, text="Connect", command=self.connect)
        self.connected = False

        self.test_button = ttk.Button(self, text="Test", command=self.test)

        self.port_label.grid(row=0, column=0, padx=padx, pady=pady)
        self.port_combobox.grid(row=0, column=1, padx=padx, pady=pady)
        self.baud_label.grid(row=0, column=2, padx=padx, pady=pady)
        self.baud_combobox.grid(row=0, column=3, padx=padx, pady=pady)
        self.connect_button.grid(row=0, column=4, padx=padx, pady=pady)
        self.test_button.grid(row=0, column=5, padx=padx, pady=pady)

        self.stop_event = threading.Event()
        self.thread = None


    def connect(self):
        print("SerPort.connect() called")
        if self.connected :
            self.disconnect
        baudstring = self.baud_var.get()
        baudrate = self.validate_baud(baudstring)
        if ( baudrate == 0 ) :
            return
        self.serport.baudrate = baudrate
        self.serport.port = self.port_var.get()
        try :
            self.serport.open()
        except ValueError :
            messagebox.showerror(title="Error", message="ValueError opening port.")
            return
        except SerialException :
            messagebox.showerror(title="Error", message="SerialException opening port.")
            return
        print(f"connected to {self.serport.port} at {self.serport.baudrate}")
        self.port_old = self.serport.port
        self.baud_old = baudstring
        # create a thread to monitor the port
        self.thread = threading.Thread(target=self.read_thread)
        print("starting thread")
        self.stop_event.clear()
        self.thread.start()
        self.connect_button['command'] = self.disconnect
        self.connect_button['text'] = 'Disconnect'
        self.connected = True

    def read_thread(self):
        print("start of thread loop")
        while not self.stop_event.is_set() :
            print("read_thread...")
            time.sleep(0.1)
        print("end of thread loop")


    def disconnect_ignore_widgets(self):
        '''
        disconnects from the serial port, but doesn't
        touch any TkInter widgets; this method can safely
        be called after the main loop exits.
        '''
        print("SerPort.disconnect_ignore_widgets() called")
        if self.thread != None and self.thread.is_alive() :
            print("stopping thread")
            self.stop_event.set()
            self.thread.join()
            print("thread stopped")
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

    def port_changed(self, *arg):
        print("port_changed() called")
        if self.connected :
            print("popping dialog")
            if messagebox.askyesno(title="Serial Port", message="Disconnect?") :
                self.disconnect()
            else :
                print("restoring port")
                self.port_var.set(self.port_old)
                print("port restored")

    def baud_changed(self, *arg):
        print("port_changed() called")
        if self.connected :
            print("popping dialog")
            if messagebox.askyesno(title="Serial Port", message="Disconnect?") :
                self.disconnect()
            else :
                print("restoring baud rate")
                self.baud_var.set(self.baud_old)
                print("baud rate restored")

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

    def test(self) :
        print(f"{self.serport.in_waiting=}")

