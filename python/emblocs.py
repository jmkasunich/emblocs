#! /usr/bin/env python3

import tkinter as tk
from tkinter import ttk
import argparse
import json
#import tkinter.font as tkfont

from bl_console import Console
from bl_command import Command
from bl_serial import SerPort


class EmblocsGUI:
    def __init__(self, master, config):
        self.master = master
        self.master.title("EMBLOCS")

        self.cfgdata = config.data
        g = self.cfgdata['app']['geometry']
        if g != '':
            self.master.geometry(g)

        self.port_ctrl = SerPort(master, config)
        self.notebook = ttk.Notebook(master)
        self.cmd_frame = Command(master, config, callback=self.command_callback)

        self.port_ctrl.grid(row=0, column=0, sticky='ew')
        self.notebook.grid(row=1, column=0, sticky='nsew')
        self.cmd_frame.grid(row=2, column=0, sticky='ew')

        self.master.grid_rowconfigure(0, weight=0)
        self.master.grid_rowconfigure(1, weight=1)
        self.master.grid_rowconfigure(0, weight=0)
        self.master.grid_columnconfigure(0, weight=1)

        self.tab_console = Console(self.notebook, config)
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

        self.port_ctrl.after(100, self.update_console)

    def on_close(self):
        # capture window geometry
        self.cfgdata['app']['geometry'] = self.master.geometry()
        self.master.destroy()

    def update_console(self) :
        while True :
            text_tuple = self.port_ctrl.get_text_tuple()
            if text_tuple :
                text, timestamp = text_tuple
                self.tab_console.rx_append(text, timestamp)
            else :
                partial = self.port_ctrl.get_partial_text()
                if partial :
                    print(f"{partial=}")
                self.port_ctrl.after(100, self.update_console)
                break

    def command_callback(self, command):
        print(f"command_callback called with {command=}")
        self.tab_console.tx_append(command)
        self.port_ctrl.send_text(command)


class AppConfig:
    """Class for managing application config (args and JSON config file)"""

    def __init__(self):
        self.data={}
        # define fields that will be in the config file, and their default values
        self.data['app']={}
        self.data['app']['geometry']=''
        self.data['port']={}
        self.data['port']['port']=''
        self.data['port']['baud']='115.2K'
        self.data['text']={}
        self.data['text']['font_family']='courier'
        self.data['text']['font_size']=12
        self.data['console']={}
        self.data['console']['show_linenum']=True
        self.data['console']['show_timestamp']=True
        self.data['console']['show_rx_text']=True
        self.data['console']['show_tx_text']=True
        self.data['console']['wrap_lines']=False
        self.data['console']['autoscroll']=True
        # other class members
        self.cfgfile='emblocs.json'

    def read(self):
        # parse command line first in case it calls out a non-standard config file
        arg_parser = argparse.ArgumentParser(description="emblocs dev tool")
        # define the command line arguments
        arg_parser.add_argument('-c', '--cfgfile', help=f"use CFGFILE instead of {self.cfgfile}")
        arg_parser.add_argument('-p', '--port', help="serial port name")
        arg_parser.add_argument('-b', '--baud', help=f"baud rate, default {self.data['port']['baud']}")
        args = arg_parser.parse_args()
        if args.cfgfile:
            self.cfgfile = args.cfgfile
        # parse the config file
        filedata = {}
        try:
            with open(self.cfgfile, 'r', encoding='utf-8') as cfgfile:
                filedata = json.load(cfgfile)
        except FileNotFoundError:
            print(f"Warning: config file '{self.cfgfile}' was not found.")
        except OSError as e:
            print(f"Error reading config file '{self.cfgfile}': {e}")
        except json.JSONDecodeError as e:
            print(f"Error decoding config file '{self.cfgfile}': {e}")
        self.copy_matching_keys(filedata, self.data)
        # apply the command line args last so they override config file values
        if args.port:
            self.data['port']['port'] = args.port
        if args.baud:
            self.data['port']['baud'] = args.baud

    def write(self):
        try:
            with open(self.cfgfile, 'w') as json_file:
                json.dump(self.data, json_file, indent=4)
        except OSError as e:
            print(f"Error writing to config file '{self.cfgfile}': {e}")

    def copy_matching_keys(self, source :dict, dest :dict):
        '''
        source and dest are both dicts (maybe nested)
        for each key that exists in both dicts, copy
        the value from source to dest, recursing if
        the values are also dicts
        '''
        for key in dest.keys():
            if isinstance(dest[key], dict):
                if key in source and isinstance(source[key], dict):
                    self.copy_matching_keys(source[key], dest[key])
            else:
                if key in source:
                    dest[key] = source[key]


if __name__ == "__main__":
    config = AppConfig()
    config.read()
    root = tk.Tk()
    app = EmblocsGUI(root, config)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
    app.port_ctrl.disconnect_ignore_widgets()
    config.write()

