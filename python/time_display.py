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
    def __init__(self, parent, font: tkfont = None,
                  initial_mode=TimeDisplayMode.ELAPSED):
        super().__init__(parent, text="Time", padding=(2,0,0,3))
        if font is None:
            self._font = tkfont.nametofont("TkDefaultFont").copy()
            self._font.configure(size=10)
        else:
            self._font = font
        # widgets
        self._mode = tk.StringVar()
        row1 = ttk.Frame(self)
        row2 = ttk.Frame(self)
        self._elapsed_radio = ttk.Radiobutton(row1, text="Elapsed",
                                        variable=self._mode,
                                        value=TimeDisplayMode.ELAPSED.value,
                                        command=self._mode_changed)
        self._reset_button = ttk.Button(row1, text="Reset", width=-1,
                                        command=self.reset_elapsed)
        self._wall_radio = ttk.Radiobutton(row2, text="Wall Clock",
                                        variable=self._mode,
                                        value=TimeDisplayMode.WALL.value,
                                        command=self._mode_changed)
        readout = ttk.Frame(self)
        self._line1_label = tk.Label(readout, text="Elapsed", width=12,
                                background="black", foreground="white",
                                anchor="w", font=self._font)
        self._line2_label = tk.Label(readout, text="00:00:00.000", width=12,
                                background="black", foreground="white",
                                anchor="w", font=self._font)
        self._set_anchor()
        self.reset_elapsed()
        self.set_mode(initial_mode)
        # geometry
        self._elapsed_radio.pack(side="left", anchor="w", padx=2, pady=2)
        self._reset_button.pack(side="right", anchor="e", padx=2, pady=0)
        row1.pack(side="top", anchor="nw", padx=0, pady=0)
        self._wall_radio.pack(side="left", anchor="w", padx=2, pady=2)
        row2.pack(side="top", anchor="nw", padx=0, pady=0)
        self._line1_label.pack(side="top", anchor="nw", fill="x", padx=2, pady=0)
        self._line2_label.pack(side="top", anchor="nw", fill="x", padx=2, pady=0)
        readout.pack(side="top", anchor="n", fill="x", padx=0, pady=0)

    def _set_anchor(self):
        """ Stores two representations of the "same instant", used for
        converting a time.monotonic timestamp to wall time.  There is
        actually a small (probably sub-microsecond) difference between
        the two times, based on the execution time of the first call.
        """
        self._anchor_mono = time.monotonic()
        self._anchor_wall = datetime.now()

    def reset_elapsed(self):
        """ Resets the elapsed time.  While the GUI button is disabled
        when in wall-clock mode, this method can still be called from
        an application if it wants to measure elapsed from some specific
        event rather than leaving it to the user.
        """
        self._elapsed_start = time.monotonic()

    def set_mode(self, mode: TimeDisplayMode):
        """ Changes display mode from the application.
        Normally the user controls the mode with radiobuttons.
        """
        if not isinstance(mode, TimeDisplayMode):
            raise TypeError(f"mode must be a TimeDisplayMode, not {mode!r}")
        self._mode.set(mode.value)
        self._mode_changed()

    def _mode_changed(self):
        if self._mode.get() == TimeDisplayMode.ELAPSED.value:
            self._reset_button.configure(state="normal")
        else:
            # re-sync the monotonic-to-wall offset in case something
            # like a daylight savings time change occurred.
            self._set_anchor()
            self._reset_button.configure(state="disabled")

    def update_time(self, timestamp=None):
        """ Updates the displayed time.  Typically called from an
        application when it redraws a screen.  Displays the time
        at which it was called; the application can override that
        by passing a monotonic time value.
        """
        if self._mode.get() == TimeDisplayMode.ELAPSED.value:
            if timestamp is None:
                timestamp = time.monotonic()
            elapsed = timestamp - self._elapsed_start
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = elapsed % 60
            self._line1_label.configure(text="Elapsed")
            self._line2_label.configure(
                text=f"{hours:02}:{minutes:02}:{seconds:06.3f}")
        else:
            if timestamp is None:
                now = datetime.now()
            else:
                since_anchor = timedelta(seconds=timestamp-self._anchor_mono)
                now = self._anchor_wall + since_anchor
            self._line1_label.configure(text=now.strftime("%Y-%m-%d"))
            self._line2_label.configure(
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

