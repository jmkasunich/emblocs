#! /usr/bin/env python3
# display_controls.py

import tkinter as tk
from tkinter import ttk

class DisplayControls(ttk.LabelFrame):
    def __init__(self, parent, *, filled=True, command=None):
        super().__init__(parent, text="Display", padding=(2,0,0,3))
        self._command = command
        self._filled = tk.BooleanVar(value=filled)
        self._filled_check = ttk.Checkbutton(
            self,
            text="Filled",
            variable=self._filled,
            command=self._changed
        )
        self._filled_check.pack(anchor="nw")

    @property
    def filled(self) -> bool:
        return self._filled.get()

    def set_filled(self, value: bool):
        value = bool(value)
        if value != self._filled.get():
            self._filled.set(value)
            self._changed()

    def _changed(self):
        if self._command is not None:
            self._command()
