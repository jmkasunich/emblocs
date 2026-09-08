#!/usr/bin/env python3
"""
serport_tk.py

Tkinter widget for SerPort (port and baud rate selection).
Provides GUI selectors for port, baudrate, and connection/disconnection
When connected passes method calls through to SerPort,
"""

import tkinter as tk
from tkinter import ttk, messagebox
import queue
from config import Config
from serport import SerPort


class SerPortTk(ttk.Frame):
    """
    GUI widget for serial port selection and connection control.
    Displays port and baud rate dropdowns, connect/disconnect button, and status.

    Public API:
      report connection status:
        is_connected()
      pass thru to underlying SerPort when connected,
      raise RuntimeError if called while disconnected:
        send_string(),
        send_packet(),
        listen_on_string_channel(),
        listen_on_packet_channel()
    """

    def __init__(self, parent, config: Config, on_connect=None, on_disconnect=None, **kwargs):
        """
        Initialize the SerPortTk widget.

        Args:
            parent: Tkinter parent widget
            config: Config object with port settings
        """
        super().__init__(parent, **kwargs)

        self.config = config
        self.serport = None
        self.connected = False
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect

        padx = 5
        pady = 5

        # Port selection
        ttk.Label(self, text="Port:").grid(row=0, column=0, padx=padx, pady=pady)
        self.port_var = tk.StringVar(value=self.config.get_by_name('port.port'))
        self.port_combo = ttk.Combobox(self, textvariable=self.port_var, state="normal")
        self.port_combo.grid(row=0, column=1, padx=padx, pady=pady, sticky='ew')

        # Baud rate selection
        ttk.Label(self, text="Baud:").grid(row=0, column=2, padx=padx, pady=pady)
        self.baud_var = tk.StringVar(value=self.config.get_by_name('port.baud'))
        self.baud_combo = ttk.Combobox(
            self, values=('9600', '115200', '230400', '460800', '921600'),
            textvariable=self.baud_var, state="normal"
        )
        self.baud_combo.grid(row=0, column=3, padx=padx, pady=pady, sticky='ew')

        # Connect/Disconnect button
        self.connect_btn = ttk.Button(self, text="Connect", command=self._on_connect_click)
        self.connect_btn.grid(row=0, column=4, padx=padx, pady=pady)

        # Status indicator
        # Status indicator
        self.status_var = tk.StringVar(value="Not connected")
        self.status_label = ttk.Label(self, textvariable=self.status_var, foreground='red')
        self.status_label.grid(row=0, column=5, padx=padx, pady=pady)

        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(3, weight=1)

        # Force layout calculation so we can measure the label width
        self.status_label.update_idletasks()
        # Get the width needed for "Not connected" (including padding)
        needed_width = self.status_label.winfo_reqwidth() + 2 * padx
        # and lock the column to that size
        self.grid_columnconfigure(5, minsize=needed_width)

        # Refresh port list on widget creation
        self._refresh_ports()

    @staticmethod
    def add_config_data(config: Config):
        """
        Add SerPortTk-specific config fields to a Config object.
        Should be called before SerPortTk is instantiated.

        Args:
            config: Config object to update
        """
        config.set_by_name('port.port', '')
        config.set_by_name('port.baud', '115200')

    def _refresh_ports(self):
        """Update port dropdown with available serial ports."""
        ports = SerPort.get_available_ports()
        self.port_combo['values'] = ports

    def _on_connect_click(self):
        """Handle Connect button click."""
        if self.connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        """Attempt to connect to the selected port."""
        port = self.port_var.get().strip()
        baud_str = self.baud_var.get().strip()
        if not port:
            messagebox.showerror("Error", "Please select a port")
            return
        try:
            baud = int(baud_str)
        except ValueError:
            messagebox.showerror("Error", "Invalid baud rate")
            return
        # Disable controls while connecting
        self.port_combo.config(state='disabled')
        self.baud_combo.config(state='disabled')
        try:
            self.serport = SerPort(port, baud, debug=False)
        except Exception as e:
            self.serport = None
            messagebox.showerror("Connection Error", str(e))
            self.port_combo.config(state='normal')
            self.baud_combo.config(state='normal')
            return
        self.connected = True
        self.connect_btn.config(text="Disconnect")
        self.status_var.set("Connected")
        self.status_label.config(foreground='green')
        # Save to config
        self.config.set_by_name('port.port', port)
        self.config.set_by_name('port.baud', baud_str)
        if self.on_connect:
            self.on_connect()

    def _disconnect(self):
        """Disconnect from the serial port."""
        self.serport.close()
        self.serport = None
        self.connected = False
        self.connect_btn.config(text="Connect")
        self.status_var.set("Not connected")
        self.status_label.config(foreground='red')
        self.port_combo.config(state='normal')
        self.baud_combo.config(state='normal')
        if self.on_disconnect:
            self.on_disconnect()

    def is_connected(self) -> bool:
        """
        Check if currently connected to a serial port.

        Returns:
            True if connected, False otherwise
        """
        return self.connected

    def send_string(self, data: str) -> None:
        """
        Queue a string for transmission on the string channel.

        Args:
            data: String to send (ASCII only)

        Raises:
            RuntimeError if not connected
            UnicodeEncodeError if data contains non-ASCII characters
        """
        if not self.connected:
            raise RuntimeError("Not connected to serial port")
        self.serport.send_string(data)

    def send_packet(self, chan: int, data: bytes) -> None:
        """
        Queue a binary packet for transmission.

        Args:
            chan: Packet channel (0-127)
            data: Packet payload (max 252 bytes)

        Raises:
            RuntimeError if not connected
            ValueError if channel or data length is invalid
        """
        if not self.connected:
            raise RuntimeError("Not connected to serial port")
        self.serport.send_packet(chan, data)

    def listen_on_packet_channel(self, chan: int, q: queue.Queue, with_timestamp: bool = False) -> None:
        """
        Register a queue to receive packets on the given channel.

        Args:
            chan: Packet channel (0-127)
            q: Queue to receive data
            with_timestamp: If False (default), queue receives just the payload (bytes).
                           If True, queue receives (timestamp, payload) tuples.

        Raises:
            RuntimeError if not connected
            ValueError if channel is invalid or already has a listener
        """
        if not self.connected:
            raise RuntimeError("Not connected to serial port")
        self.serport.listen_on_packet_channel(chan, q, with_timestamp)

    def listen_on_string_channel(self, q: queue.Queue, with_timestamp: bool = False) -> None:
        """
        Register a queue to receive string channel data.

        Args:
            q: Queue to receive data
            with_timestamp: If False (default), queue receives just the string (str).
                           If True, queue receives (timestamp, string) tuples.

        Raises:
            RuntimeError if not connected
            ValueError if string channel already has a listener
        """
        if not self.connected:
            raise RuntimeError("Not connected to serial port")
        self.serport.listen_on_string_channel(q, with_timestamp)

# ============================================================================
# Test harness: Simple dumb-terminal application
# ============================================================================

if __name__ == '__main__':
    from terminal import Terminal
    from datetime import datetime
    import queue

    # Create config and register all config keys
    config = Config()
    SerPortTk.add_config_data(config)
    Terminal.add_config_data(config)
    config.set_by_name('app.geometry', '800x600')

    # Create main window
    root = tk.Tk()
    root.title("SerPort Dumb Terminal")
    root.geometry(config.get_by_name('app.geometry'))

    # Configure grid for expansion
    root.grid_rowconfigure(1, weight=1)
    root.grid_columnconfigure(0, weight=1)

    # Create Terminal widget (will hold both RX display and TX input)
    terminal = Terminal(root, config)
    terminal.grid(row=1, column=0, sticky='nsew', padx=2, pady=2)

    # String receive queue - persistent
    string_queue = queue.Queue()

    def poll_rx():
        """Continuously poll for incoming string data and display."""
        while True:
            try:
                timestamp, data = string_queue.get_nowait()
                terminal.append(data.encode(), timestamp, is_tx=False)
            except queue.Empty:
                break
        root.after(100, poll_rx)

    def on_connect():
        """Called when SerPortTk successfully connects."""
        serport_tk.listen_on_string_channel(string_queue, with_timestamp=True)

    def on_terminal_command(cmd):
        """Called when user types in terminal TX."""
        if serport_tk.is_connected():
            serport_tk.send_string(cmd)
            terminal.append(cmd.encode(), datetime.now(), is_tx=True)

    # Create SerPortTk widget at top with callbacks
    serport_tk = SerPortTk(root, config, on_connect=on_connect)
    serport_tk.grid(row=0, column=0, sticky='ew', padx=2, pady=2)

    # Wire terminal TX callback to send via SerPortTk
    terminal.tx.command = on_terminal_command
    # start polling RX queue
    poll_rx()

    root.mainloop()
