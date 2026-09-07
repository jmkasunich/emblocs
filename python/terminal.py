#!/usr/bin/env python3
"""
terminal.py

Dumb Terminal for TkInter

  TerminalRx: display widget
  TerminalTx: input widget
  Terminal:   combined widget

"""

import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
from datetime import datetime
from config import Config

def _clamp(value, low, high):
    """Clamp a value between low and high."""
    return min(max(low, value), high)

class TerminalRx(ttk.Frame):
    """
    Line-oriented dumb terminal widget.
    Displays incoming lines with optional line numbers and/or timestamps.

    This class handles the display and user interface, not the serial port.
    """

    def __init__(self, parent, config: Config, linenum_len=6, timestamp_len1=8, timestamp_len2=3, **kwargs):
        """
        Initialize the TerminalRx widget.

        Args:
            parent: Tkinter parent widget
            config: Config object with [terminal][rx] settings
            linenum_len: Length of line number field (1-10)
            timestamp_len1: Length of timestamp before decimal (2-19)
            timestamp_len2: Length of fractional seconds (0-6)
        """
        super().__init__(parent, **kwargs)

        self.config = config

        # Line counter and state
        self.linecount = 1
        self.new_line = True

        self.linenum_len = _clamp(linenum_len, 1, 10)
        self.timestamp_len1 = _clamp(timestamp_len1, 2, 19)
        self.timestamp_len2 = _clamp(timestamp_len2, 0, 6)
        if self.timestamp_len2 == 0:
            # No fractional digits; don't display decimal point either
            self.timestamp_len2 = -1

        # Font for text display
        self.font = tkfont.Font(
            family=self.config.get_by_name('terminal.font_family'),
            size=self.config.get_by_name('terminal.rx.font_size'),
            weight="normal"
        )
        self.charwidth = self.font.measure('0')

        # Text widget with scrollbars
        self.text = tk.Text(self, undo=False, state='disabled', font=self.font)
        self.ys = ttk.Scrollbar(self, orient='vertical')
        self.xs = ttk.Scrollbar(self, orient='horizontal')

        # Configure text tags for styling
        self.text.tag_configure("rx_text", foreground='gray')
        self.text.tag_configure("tx_text", foreground='black')
        self.text.tag_configure("rx_linenum", foreground='red')
        self.text.tag_configure("tx_linenum", foreground='red')
        self.text.tag_configure("rx_timestamp", foreground='blue')
        self.text.tag_configure("tx_timestamp", foreground='blue')

        # Connect scrollbars
        self.text.config(yscrollcommand=self.ys.set)
        self.text.config(xscrollcommand=self.xs.set)
        self.ys.config(command=self.text.yview)
        self.xs.config(command=self.text.xview)

        # Replace default copy handler to copy only visible text
        self.text.bind('<Control-c>', self.copy_displayed)

        # Control checkboxes
        self.checkframe = ttk.Frame(self)

        self.show_linenum = tk.BooleanVar(value=self.config.get_by_name('terminal.rx.show_linenum'))
        self.linenum_check = ttk.Checkbutton(
            self.checkframe, text='Line Numbers',
            command=self.show_changed, variable=self.show_linenum
        )
        self.show_timestamp = tk.BooleanVar(value=self.config.get_by_name('terminal.rx.show_timestamp'))
        self.timestamp_check = ttk.Checkbutton(
            self.checkframe, text='Timestamps',
            command=self.show_changed, variable=self.show_timestamp
        )
        self.wrap = tk.BooleanVar(value=self.config.get_by_name('terminal.rx.wrap_lines'))
        self.wrap_check = ttk.Checkbutton(
            self.checkframe, text='Wrap Long Lines',
            command=self.wrap_changed, variable=self.wrap
        )
        self.autoscroll = tk.BooleanVar(value=self.config.get_by_name('terminal.rx.autoscroll'))
        self.autoscroll_check = ttk.Checkbutton(
            self.checkframe, text='Autoscroll',
            command=self.scroll_changed, variable=self.autoscroll
        )
        self.show_rx = tk.BooleanVar(value=self.config.get_by_name('terminal.rx.show_rx_text'))
        self.rx_check = ttk.Checkbutton(
            self.checkframe, text='RX',
            command=self.show_changed, variable=self.show_rx
        )
        self.show_tx = tk.BooleanVar(value=self.config.get_by_name('terminal.rx.show_tx_text'))
        self.tx_check = ttk.Checkbutton(
            self.checkframe, text='TX',
            command=self.show_changed, variable=self.show_tx
        )

        # Configure based on initial checkbox state
        self.show_changed()
        self.wrap_changed()

        # Geometry: checkboxes at top, text in middle, scrollbars on sides
        self.checkframe.grid_columnconfigure(0, weight=3)
        self.checkframe.grid_columnconfigure(1, weight=3)
        self.checkframe.grid_columnconfigure(2, weight=3)
        self.checkframe.grid_columnconfigure(3, weight=3)
        self.checkframe.grid_columnconfigure(4, weight=1)
        self.checkframe.grid_columnconfigure(5, weight=1)
        self.checkframe.grid_rowconfigure(0, weight=0)

        self.linenum_check.grid(row=0, column=0)
        self.timestamp_check.grid(row=0, column=1)
        self.wrap_check.grid(row=0, column=2)
        self.autoscroll_check.grid(row=0, column=3)
        self.rx_check.grid(row=0, column=4)
        self.tx_check.grid(row=0, column=5)

        self.checkframe.grid(row=0, column=0, columnspan=2, sticky='nsew')
        self.text.grid(row=1, column=0, sticky='nsew')
        self.ys.grid(row=1, column=1, sticky='nsew')
        self.xs.grid(row=2, column=0, sticky='nsew')

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

    @staticmethod
    def add_config_data(config: Config):
        config.set_by_name('terminal.font_family','Courier')
        # RX-specific config
        config.set_by_name('terminal.rx.font_size', 10)
        config.set_by_name('terminal.rx.show_linenum', True)
        config.set_by_name('terminal.rx.show_timestamp', True)
        config.set_by_name('terminal.rx.show_rx_text', True)
        config.set_by_name('terminal.rx.show_tx_text', True)
        config.set_by_name('terminal.rx.wrap_lines', False)
        config.set_by_name('terminal.rx.autoscroll', True)

    def make_timestr(self, timestamp):
        """
        Convert datetime object to formatted timestamp string.

        Args:
            timestamp: datetime object (or None for current time)

        Returns:
            Formatted timestamp string
        """
        if timestamp is None:
            timestamp = datetime.now()
        timestr = timestamp.isoformat(timespec='microseconds')
        # Decimal point in ISO format is at index 19
        timestr = timestr[19 - self.timestamp_len1:19 + 1 + self.timestamp_len2]
        return timestr

    def append(self, content, timestamp, is_tx=False):
        """
        Add text to the display.

        Args:
            content: bytes to display
            timestamp: datetime when last char in content was received
            is_tx: if True, mark as transmitted; if False, mark as received
        """
        timestr = self.make_timestr(timestamp)
        textstr = content.decode(errors='replace')
        rxtx = "tx_" if is_tx else "rx_"

        self.text.configure(state='normal')
        if self.new_line:
            self.text.insert('end', f"{self.linecount:0{self.linenum_len}d}:", rxtx + "linenum")
            self.text.insert('end', f"{timestr}:", rxtx + "timestamp")
            self.new_line = False
        self.text.insert('end', textstr, rxtx + "text")
        self.text.configure(state='disabled')

        if textstr and textstr[-1] == '\n':
            self.linecount = self.linecount + 1
            self.new_line = True

        if self.autoscroll.get():
            self.text.see(tk.END)

    def set_lmargin2(self):
        """
        Indent wrapped lines relative to base text to align with content.
        """
        lmargin = 1.5  # Basic indent in characters
        if self.show_linenum.get():
            lmargin = lmargin + self.linenum_len + 1
        if self.show_timestamp.get():
            lmargin = lmargin + self.timestamp_len1 + self.timestamp_len2 + 2
        lmargin = self.charwidth * lmargin

        for tag in self.text.tag_names():
            if 'text' in tag:
                self.text.tag_configure(tag, lmargin2=lmargin)

    def wrap_changed(self):
        """Handle wrap checkbox change."""
        wrap = self.wrap.get()
        self.text.config(wrap='char' if wrap else 'none')
        self.config.set_by_name('terminal.rx.wrap_lines', wrap)

    def scroll_changed(self):
        """Handle autoscroll checkbox change."""
        self.config.set_by_name('terminal.rx.autoscroll', self.autoscroll.get())

    def show_changed(self):
        """Handle show checkboxes (linenum, timestamp, rx, tx)."""
        show_linenum = self.show_linenum.get()
        show_timestamp = self.show_timestamp.get()
        show_rx = self.show_rx.get()
        show_tx = self.show_tx.get()

        # Elide (hide) tags based on checkbox state
        self.text.tag_configure("rx_text", elide=not show_rx)
        self.text.tag_configure("tx_text", elide=not show_tx)
        self.text.tag_configure("rx_linenum", elide=not (show_rx and show_linenum))
        self.text.tag_configure("tx_linenum", elide=not (show_tx and show_linenum))
        self.text.tag_configure("rx_timestamp", elide=not (show_rx and show_timestamp))
        self.text.tag_configure("tx_timestamp", elide=not (show_tx and show_timestamp))

        self.set_lmargin2()

        # Update config
        self.config.set_by_name('terminal.rx.show_timestamp', show_timestamp)
        self.config.set_by_name('terminal.rx.show_linenum', show_linenum)
        self.config.set_by_name('terminal.rx.show_rx_text', show_rx)
        self.config.set_by_name('terminal.rx.show_tx_text', show_tx)

    def copy_displayed(self, event=None):
        """
        Replace default copy handler to copy only displayed characters
        (allows user to copy text with/without line numbers and timestamps).
        """
        ranges = self.text.tag_ranges('sel')
        if ranges:
            start = ranges[0]
            end = ranges[-1]
            curr_index = self.text.index(f"{start}+0 display chars")
            selected = ""
            while self.text.compare(curr_index, "<", end):
                selected = selected + self.text.get(curr_index)
                curr_index = self.text.index(f"{curr_index}+1 display chars")

            # Clipboard access via root window
            toplevel = self.winfo_toplevel()
            toplevel.clipboard_clear()
            toplevel.clipboard_append(selected)
        return 'break'

class TerminalTx(ttk.Frame):
    """
    Text input widget for sending commands.
    Displays an Entry widget with horizontal scrollbar.
    Callback fires when user presses Return.
    TODO: history buffer
    TODO: immediate mode
    """

    def __init__(self, parent, config: Config, command=None, **kwargs):
        """
        Initialize the TerminalTx widget.

        Args:
            parent:  Tkinter parent widget
            config:  Config object with terminal settings
            command: Function to call when user presses Return
                     Receives command text (including newline)
        """
        super().__init__(parent, **kwargs)

        self.config = config
        self.command = command

        # Font for text input
        self.font = tkfont.Font(
            family=self.config.get_by_name('terminal.font_family'),
            size=self.config.get_by_name('terminal.tx.font_size'),
            weight="normal"
        )

        # Entry widget with horizontal scrollbar
        self.entry_var = tk.StringVar(value='')
        self.entry = tk.Entry(self, textvariable=self.entry_var, state='normal', font=self.font)
        self.xs = ttk.Scrollbar(self, orient='horizontal')

        # Connect scrollbar
        self.entry.config(xscrollcommand=self.xs.set)
        self.xs.config(command=self.entry.xview)

        # Bind Return key
        self.entry.bind("<Return>", self._on_return)

        # Geometry
        self.entry.grid(row=0, column=0, sticky='ew', ipadx=5, ipady=3)
        self.xs.grid(row=1, column=0, sticky='ew')
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)

    @staticmethod
    def add_config_data(config: Config):
        """
        Add TerminalTx-specific config fields to a Config object.
        Also initializes shared terminal config if not present.
        Should be called before TerminalTx is instantiated.

        Args:
            config: Config object to update
        """
        config.set_by_name('terminal.font_family', 'Courier')
        config.set_by_name('terminal.tx.font_size', 10)

    def _on_return(self, event):
        """Handle Return key press."""
        command = self.entry_var.get() + '\n'
        if self.command:
            self.command(command)
        self.entry_var.set('')

    def set_focus(self):
        """Set keyboard focus to the entry widget."""
        self.entry.focus_set()

class Terminal(ttk.Frame):
    """
    Complete terminal widget combining display and input.
    TerminalRx shows received text, TerminalTx accepts user commands.
    """

    def __init__(self, parent, config: Config, command=None, **kwargs):
        """
        Initialize the Terminal widget.

        Args:
            parent:  Tkinter parent widget
            config:  Config object with terminal settings
            command: Function to call when user sends a command
                     Receives command text (including newline)
        """
        super().__init__(parent, **kwargs)

        self.config = config

        # Create RX display and TX input
        self.rx = TerminalRx(self, config)
        self.tx = TerminalTx(self, config, command=command)

        # Layout: RX takes most space, TX at bottom
        self.rx.grid(row=0, column=0, sticky='nsew')
        self.tx.grid(row=1, column=0, sticky='ew')
        self.grid_rowconfigure(0, weight=1)  # RX gets extra vertical space
        self.grid_columnconfigure(0, weight=1) # everybody expands horizonally

    @staticmethod
    def add_config_data(config: Config):
        """
        Add Terminal config to a Config object.
        Initializes both RX and TX config.

        Args:
            config: Config object to update
        """
        TerminalRx.add_config_data(config)
        TerminalTx.add_config_data(config)

    def append(self, content: bytes, timestamp, is_tx: bool = False):
        """
        Append text to the display (forward to TerminalRx).

        Args:
            content: bytes to display
            timestamp: datetime when received
            is_tx: if True, mark as transmitted; if False, received
        """
        self.rx.append(content, timestamp, is_tx)

    def set_focus(self):
        """Set keyboard focus to the command input."""
        self.tx.set_focus()

# ------------------------------------------------------------------

if __name__ == '__main__':
    root = tk.Tk()
    root.title("Terminal Test")
    root.geometry("800x400")
    
    config = Config()
    Terminal.add_config_data(config)
    
    def on_command(cmd):
        # Echo command back as TX
        terminal.append(cmd.encode(), datetime.now(), is_tx=True)
        # Echo back as RX (uppercased to prove it's working)
        terminal.append(cmd.upper().encode(), datetime.now(), is_tx=False)
    
    terminal = Terminal(root, config, command=on_command)
    terminal.grid(row=0, column=0, sticky='nsew')
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)

    # Send some startup text
    terminal.append(b"Terminal Test - type and press Return\n", datetime.now())
    
    root.mainloop()
