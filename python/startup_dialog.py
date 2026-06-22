#! /usr/bin/env python3
# startup_dialog.py
# EMBLOCS Runtime Monitor - startup applet for selecting project

import tkinter as tk
from tkinter import ttk
from datetime import datetime
from pathlib import Path
from emblocs_common import Config


def _make_recent_entry(path: Path) -> dict:
    return {
        'path': str(path),
        'last_opened': datetime.now().isoformat(),
    }

_MAX_RECENT_PROJECTS = 10
_RECENT_KEY_FIELD = 'path'

def update_recents(startup_cfg: Config, project_cfg_file: Path) -> None:
    """Add or refresh project_cfg_file in the recents list, trimmed to max length."""
    this_project = _make_recent_entry(project_cfg_file)
    # manage recents list
    recents = startup_cfg.get_by_name('startup.recent_projects')
    path_str = str(this_project.get(_RECENT_KEY_FIELD))
    # remove existing entry for this path if present
    recents = [r for r in recents if r.get(_RECENT_KEY_FIELD) != path_str]
    # prepend new entry and trim
    recents = [this_project] + recents
    recents = recents[:_MAX_RECENT_PROJECTS]
    startup_cfg.set_by_name('startup.recent_projects', recents)

# ---------------------------------------------------------------------------
# StartupDialog
# ---------------------------------------------------------------------------

class StartupDialog(tk.Toplevel):
    """
    Project-picker dialog shown at startup.
    Displayed as a Toplevel over a hidden root window.
    On completion, populates project_cfg with the selected project path
    and updates startup_cfg with the new recents list.
    Calls root.quit() when done so the startup mainloop() returns.
    """

    def __init__(self, master: tk.Tk, startup_cfg: Config, project_cfg: Config,
                 initial_path: Path | None = None,
                 error_msg:   str  | None = None) -> None:
        super().__init__(master)
        self.startup_cfg  = startup_cfg
        self.project_cfg  = project_cfg
        self.initial_path = initial_path   # pre-fill path when known (e.g. from CLI)
        self.error_msg    = error_msg      # display error from CLI arg processing
        self.result = None    # will be set to project cfg Path on success

        self.title("EMBLOCS - Open Project")
        self.resizable(False, False)
        # center on screen
        self.update_idletasks()
        w, h = 400, 200
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        self._build_widgets()

        # prevent interaction with root while dialog is open
        self.grab_set()
        # closing the dialog window is the same as cancelling
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    @staticmethod
    def register_config(cfg: Config) -> None:
        """Register all config keys owned by the startup dialog."""
        cfg.set_by_name('startup.recent_projects', [])


    def _build_widgets(self) -> None:
        # placeholder content - real project picker UI to follow
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text="EMBLOCS Monitor", font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 4))

        # TODO: display self.error_msg if set (red label)
        # TODO: pre-fill project path field with self.initial_path if set
        ttk.Label(frame, text="(Project picker - stub)").pack(pady=(0, 20))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack()
        ttk.Button(btn_frame, text="Open Project...", command=self._on_open).pack(side='left', padx=4)
        ttk.Button(btn_frame, text="Cancel",          command=self._on_cancel).pack(side='left', padx=4)

    def _on_open(self) -> None:
        # TODO: real project selection logic
        # For now, just proceed with empty project_cfg as a stub
        self.result = None
        self._finish()

    def _on_cancel(self) -> None:
        self.result = None
        self._finish()

    def _finish(self) -> None:
        self.grab_release()
        self.destroy()
        self.master.quit()    # return control to main()

