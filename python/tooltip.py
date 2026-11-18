#! /usr/bin/env python3
# tooltip.py
"""
Tooltip is attached to 'widget' and pops up a
window with 'text' if the mouse hovers over the
widget for at least 'delay' milliseconds.
"""

import tkinter as tk
from tkinter import ttk

class Tooltip:
    def __init__(self, widget, text, delay=600):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._tip = None
        self._job = None
        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self.hide)
        widget.bind("<ButtonPress>", self.hide)
        widget.bind("<FocusIn>", self.hide)
        widget.bind("<Destroy>", self.hide)

    def _schedule(self, event=None):
        self.hide()
        self._job = self.widget.after(self.delay, self._display)

    def _display(self):
        self._job = None
        x, y = self.widget.winfo_pointerxy()
        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x + 16}+{y + 16}")
        ttk.Label(self._tip, text=self.text,
                  relief="solid", borderwidth=1).pack()

    def hide(self, event=None):
        if self._job is not None:
            self.widget.after_cancel(self._job)
            self._job = None
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None
