#! /usr/bin/env python3
# monitor_app.py
# EMBLOCS Runtime Monitor - main application class

import tkinter as tk
from tkinter import ttk
from emblocs_common import Config


# ---------------------------------------------------------------------------
# MonitorApp - main application content
# ---------------------------------------------------------------------------

class MonitorApp:
    """
    Main application UI.  Owns the notebook and all tabs.
    Receives a fully loaded project_cfg.
    """

    def __init__(self, master: tk.Tk, project_cfg: Config) -> None:
        self.master = master
        self.project_cfg = project_cfg

        self.master.title("EMBLOCS Monitor")

        # restore window geometry from project config
        g = project_cfg.get_by_name('app.geometry')
        if g:
            self.master.geometry(g)

        self._build_widgets()

    @staticmethod
    def register_config(cfg: Config) -> None:
        """Register all keys owned by the main application layer."""
        cfg.set_by_name('app.geometry', '')               # main window geometry string
        cfg.set_by_name('app.active_tab', 'Console')      # which tab was active on last exit
        cfg.set_by_name('project.name', '')               # project name (from .blocs basename)
        cfg.set_by_name('project.hash', '')               # hash of .blocs content
        # register the rest of the widget hierarchy
        # SerPort.register_config(cfg)
        # and so on...


    def _build_widgets(self) -> None:
        # --- top bar: serial port controls (stub) ---
        self.port_bar = ttk.Label(self.master, text="[ Port controls ]",
                                  relief='sunken', padding=4)

        # --- center: tabbed notebook ---
        self.notebook = ttk.Notebook(self.master)

        # tab stubs - real content classes to be substituted later
        self.tab_console = ttk.Label(self.notebook, text="Console tab (stub)")
        self.tab_scope   = ttk.Label(self.notebook, text="Scope tab (stub)")
        self.tab_meters  = ttk.Label(self.notebook, text="Meters tab (stub)")

        tab_padding = (3, 0, 3, 3)
        self.notebook.add(self.tab_console, text="Console", padding=tab_padding)
        self.notebook.add(self.tab_scope,   text="Scope",   padding=tab_padding)
        self.notebook.add(self.tab_meters,  text="Meters",  padding=tab_padding)

        # restore active tab
        active = self.project_cfg.get_by_name('app.active_tab')
        for i, tab_name in enumerate(['Console', 'Scope', 'Meters']):
            if tab_name == active:
                self.notebook.select(i)
                break

        # --- bottom bar: command entry (stub) ---
        self.cmd_bar = ttk.Label(self.master, text="[ Command bar ]",
                                 relief='sunken', padding=4)

        # --- grid layout ---
        self.port_bar.grid(row=0, column=0, sticky='ew', padx=2, pady=(2, 0))
        self.notebook.grid(row=1, column=0, sticky='nsew', padx=2, pady=2)
        self.cmd_bar.grid( row=2, column=0, sticky='ew', padx=2, pady=(0, 2))

        self.master.grid_rowconfigure(0, weight=0)
        self.master.grid_rowconfigure(1, weight=1)
        self.master.grid_rowconfigure(2, weight=0)
        self.master.grid_columnconfigure(0, weight=1)

        # apply theme
        style = ttk.Style()
        style.theme_use('clam')

    def on_close(self) -> None:
        """Called by root's WM_DELETE_WINDOW protocol."""
        # capture current state back into project_cfg before saving
        self.project_cfg.set_by_name('app.geometry', self.master.geometry())
        # capture active tab name
        active_idx = self.notebook.index('current')
        tab_names = ['Console', 'Scope', 'Meters']
        if 0 <= active_idx < len(tab_names):
            self.project_cfg.set_by_name('app.active_tab', tab_names[active_idx])
        self.master.destroy()

