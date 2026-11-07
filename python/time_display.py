#! /usr/bin/env python3
# time_display.py
""" A small frame that displays elapsed or wall-clock time.
Can be used for instrument designs where screenshots should
show the time.  Can display elapsed or wall-clock time.
"""

import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
import time
from datetime import datetime, timedelta
from enum import Enum

class TimeDisplayMode(Enum):
    ELAPSED = "elapsed"
    WALL = "wall"

class TimeDisplay(ttk.LabelFrame):
    def __init__(self, parent, initial_mode=TimeDisplayMode.ELAPSED):
        super().__init__(parent, text="Time")
        fixed_font = tkfont.nametofont("TkFixedFont").copy()
        fixed_font.configure(weight="bold", size=11)
        # widgets
        self.mode = tk.StringVar()
        top_row = ttk.Frame(self)
        self.elapsed_radio = ttk.Radiobutton(
            top_row, text="Elapsed", variable=self.mode,
            value="elapsed", command=self._mode_changed
            )
        self.wall_radio = ttk.Radiobutton(
            self, text="Wall Clock", variable=self.mode,
            value="wall", command=self._mode_changed
            )
        self.reset_button = tk.Button(
            top_row, text="Reset", command=self.reset_elapsed
            )
        readout = tk.Frame(self, relief="sunken", borderwidth=2, background="white")
        self.line1_label = ttk.Label(
            readout, text="Elapsed", width=12,
            background="white", font=fixed_font
            )
        self.line2_label = ttk.Label(
            readout, text="00:00:00.000", width=12,
            background="white", font=fixed_font
            )
        self._set_anchor()
        self.reset_elapsed()
        self.set_mode(initial_mode)
        # geometry
        self.elapsed_radio.grid(row=0, column=0, sticky="w", padx=2, pady=2)
        self.reset_button.grid(row=0, column=1, sticky="ew", padx=(4,0), pady=2)
        top_row.grid_columnconfigure(1, weight=1)
        self.line1_label.grid(row=0, column=0, columnspan=2, sticky="w",
                              padx=2, pady=(2,0))
        self.line2_label.grid(row=1, column=0, columnspan=2, sticky="w",
                              padx=2, pady=(0,2))
        top_row.grid(row=0, column=0, sticky="ew")
        self.wall_radio.grid(row=1, column=0, columnspan=2, sticky="w",
                             padx=2, pady=2)
        readout.grid(row=2, column=0, sticky="ew")

    def _set_anchor(self):
        """ Stores two representations of the "same instant", used for
        converting a time.monotonic timestamp to wall time.  There is
        actually a small (probably sub-microsecond) difference between
        the two times, based on the execution time of the first call.
        """
        self.anchor_mono = time.monotonic()
        self.anchor_wall = datetime.now()

    def reset_elapsed(self):
        """ Resets the elapsed time.  While the GUI button is disabled
        when in wall-clock mode, this method can still be called from
        an application if it wants to measure elapsed from some specific
        event rather than leaving it to the user.
        """
        self.elapsed_start = time.monotonic()

    def set_mode(self, mode: TimeDisplayMode):
        """ Changes display mode from the application.
        Normally the user controls the mode with radiobuttons.
        """
        if not isinstance(mode, TimeDisplayMode):
            raise TypeError(f"mode must be a TimeDisplayMode, not {mode!r}")
        self.mode.set(mode.value)
        self._mode_changed()

    def _mode_changed(self):
        if self.mode.get() == "elapsed":
            self.reset_button.configure(state="normal")
        else:
            # re-sync the monotonic-to-wall offset in case something
            # like a daylight savings time change occurred.
            self._set_anchor()
            self.reset_button.configure(state="disabled")

    def update_time(self, timestamp=None):
        """ Updates the displayed time.  Typically called from an
        application when it redraws a screen.  Displays the time
        at which it was called; the application can override that
        by passing a monotonic time value.
        """
        if self.mode.get() == "elapsed":
            if timestamp is None:
                timestamp = time.monotonic()
            elapsed = timestamp - self.elapsed_start
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = elapsed % 60
            self.line1_label.configure(text="Elapsed")
            self.line2_label.configure(
                text=f"{hours:02}:{minutes:02}:{seconds:06.3f}")
        else:
            if timestamp is None:
                now = datetime.now()
            else:
                since_anchor = timedelta(seconds=timestamp-self.anchor_mono)
                now = self.anchor_wall + since_anchor
            self.line1_label.configure(text=now.strftime("%Y-%m-%d"))
            self.line2_label.configure(
                text=now.strftime("%H:%M:%S.%f")[:-3])


#############################################################

if __name__ == "__main__":
    # define update function
    def _update(widget):
        widget.update_time()
        widget.after(100, _update, widget)
    # create the main application
    root = tk.Tk()
    root.title("TimeDisplay test")
    display = TimeDisplay(root)
    display.pack()
    root.geometry("600x400")
    root.update_idletasks()
    root.minsize(display.winfo_reqwidth(), display.winfo_reqheight())
    # kick off periodic update
    root.after(100, _update, display)
    root.mainloop()

