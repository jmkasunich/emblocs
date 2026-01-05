#! /usr/bin/env python3
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
from datetime import datetime

def clamp(value, low, high):
    return min(max(low, value), high)


class Command(ttk.Frame):
    '''
    command line widget
     - allows editing of a line before sending it
     - supports command history
     - supports immediate mode (characters sent as typed)

    This class handles the display and user interface, not the serial port
    '''
    def __init__(self, parent, callback=None, fontfamily='Courier', fontsize=12, **kwargs):
        '''
        :param callback: function to be called when user wants to send a command
        :param fontfamily: font name, must be a monospaced font
        :param fontsize: font size in points
        '''
        # Call the parent class (ttk.Frame) constructor
        super().__init__(parent, **kwargs)

        self.callback = callback

        # font for text display
        self.font = tkfont.Font(family=fontfamily, size=fontsize, weight="normal")
#        self.charwidth = self.font.measure('0')

        self.entry_var = tk.StringVar(value='')
#        self.entry_var.trace_add('write', self.entry_changed)

         # entry widget with horizontal scrollbar for main content
        self.entry = tk.Entry(self, textvariable=self.entry_var, state='normal', font=self.font)
        self.xs = ttk.Scrollbar(self, orient='horizontal')

        # connect the scrollbar
        self.entry.config(xscrollcommand=self.xs.set)
        self.xs.config(command = self.entry.xview)

        self.entry.bind("<Return>", self.return_pressed)

        # control checkboxes
#        self.checkframe = ttk.Frame(self)

#        self.show_linenum = tk.BooleanVar(value=True)
#        self.linenum_check = ttk.Checkbutton(self.checkframe, text='Line Numbers',
#            command=self.linenum_changed, variable=self.show_linenum)
#        self.show_timestamp = tk.BooleanVar(value=True)
#        self.timestamp_check = ttk.Checkbutton(self.checkframe, text='Timestamps',
#            command=self.timestamp_changed, variable=self.show_timestamp)
#        self.wrap = tk.BooleanVar(value=False)
#        self.wrap_check = ttk.Checkbutton(self.checkframe, text='Wrap Long Lines',
#            command=self.wrap_changed, variable=self.wrap)
#        self.autoscroll = tk.BooleanVar(value=True)
#        self.autoscroll_check = ttk.Checkbutton(self.checkframe, text='Autoscroll',
#            command=self.wrap_changed, variable=self.autoscroll)
#        self.show_rx = tk.BooleanVar(value=True)
#        self.rx_check = ttk.Checkbutton(self.checkframe, text='RX',
#            command=self.rx_changed, variable=self.show_rx)
#        self.show_tx = tk.BooleanVar(value=True)
#        self.tx_check = ttk.Checkbutton(self.checkframe, text='TX',
#            command=self.tx_changed, variable=self.show_tx)

        # configure based on initial state of checkbox
#        self.linenum_changed()
#        self.timestamp_changed()
#        self.wrap_changed()
#        self.rx_changed()
#        self.tx_changed()

        # geometry
#        self.checkframe.grid_columnconfigure(0, weight=3)
#        self.checkframe.grid_columnconfigure(1, weight=3)
#        self.checkframe.grid_columnconfigure(2, weight=3)
#        self.checkframe.grid_columnconfigure(3, weight=3)
#        self.checkframe.grid_columnconfigure(4, weight=1)
#        self.checkframe.grid_columnconfigure(5, weight=1)
#        self.checkframe.grid_rowconfigure(0, weight=0)

#        self.linenum_check.grid(row=0, column=0)
#        self.timestamp_check.grid(row=0, column=1)
#        self.wrap_check.grid(row=0, column=2)
#        self.autoscroll_check.grid(row=0, column=3)
#        self.rx_check.grid(row=0, column=4)
#        self.tx_check.grid(row=0, column=5)

#        self.checkframe.grid(row=0, column=0, columnspan=2, sticky='nsew')
        self.entry.grid(row=0, column=0, sticky='ew')
        self.xs.grid(row=1, column=0, sticky='ew')

        self.grid_columnconfigure(0, weight=1)
#        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
#        self.grid_rowconfigure(2, weight=0)

    def return_pressed(self, event):
        command = self.entry_var.get() + '\n'
        if self.callback:
            self.callback(command)

    def set_focus(self):
        self.entry.focus_set()


