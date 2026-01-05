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

        tab_padding=(3,0,3,3)

        self.notebook.add(self.tab_console, text="Console", padding=tab_padding)
        self.notebook.add(self.tab_scope, text="Scope", padding=tab_padding)
        self.notebook.add(self.tab_meters, text="Meters", padding=tab_padding)

        # this is purely personal preference
        self.style = ttk.Style()
        self.style.theme_use("clam")
#        self.style.theme_use("alt")

        self.port_ctrl.after(100, self.transfer_console_data)

    def transfer_console_data(self) :
        while True :
            text_tuple = self.port_ctrl.get_text_tuple()
            if text_tuple :
                text, timestamp = text_tuple
                self.tab_console.rx_append(text, timestamp)
            else :
                partial = self.port_ctrl.get_partial_text()
                if partial :
                    print(f"{partial=}")
                self.port_ctrl.after(100, self.transfer_console_data)
                break


if __name__ == "__main__":
    print("hello\n")
    root = tk.Tk()
    app = EmblocsGUI(root)
    app.tab_console.rx_append("this is content!")
    root.mainloop()
    print("cleanup\n")
    app.port_ctrl.disconnect_ignore_widgets()
    print("goodbye\n")



