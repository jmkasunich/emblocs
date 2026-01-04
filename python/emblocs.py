#! /usr/bin/env python3

import tkinter as tk
from tkinter import ttk
#import tkinter.font as tkfont


#from datetime import datetime

#import threading

from bl_console import Console
from bl_serial import SerPort


class EmblocsGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("EMBLOCS")
        #self.master.geometry("800x600")

        self.port_ctrl = SerPort(master, port="COM3", baud="115200")
        self.notebook = ttk.Notebook(master)
        self.cmd_frame = ttk.Label(master, text='command frame')

        self.port_ctrl.grid(row=0, column=0, sticky='ew')
        self.notebook.grid(row=1, column=0, sticky='nsew')
        self.cmd_frame.grid(row=2, column=0, sticky='ew')

        self.master.grid_rowconfigure(0, weight=0)
        self.master.grid_rowconfigure(1, weight=1)
        self.master.grid_rowconfigure(0, weight=0)
        self.master.grid_columnconfigure(0, weight=1)

        self.tab_console = Console(self.notebook, fontfamily="Consolas", fontsize=10)
        self.tab_scope = ttk.Label(self.notebook, text="Scope")
        self.tab_meters = ttk.Label(self.notebook, text="Meters")

        self.tab_console.pack(fill='both', expand=True)
        self.tab_scope.pack(fill='both', expand=True)
        self.tab_meters.pack(fill='both', expand=True)

        self.notebook.add(self.tab_console, text="Console")
        self.notebook.add(self.tab_scope, text="Scope")
        self.notebook.add(self.tab_meters, text="Meters")


if __name__ == "__main__":
    print("hello\n")
    root = tk.Tk()
    app = EmblocsGUI(root)
    app.tab_console.rx_append("this is content!")
    root.mainloop()
    print("cleanup\n")
    app.port_ctrl.disconnect_ignore_widgets()
    print("goodbye\n")



