#! /usr/bin/env python3
# emblocs_gui.py
# EMBLOCS Runtime Monitor - main GUI entry point

import tkinter as tk
from pathlib import Path
import platform
import sys
from emblocs_common import Config
from monitor_app import MonitorApp
from startup_dialog import StartupDialog, update_recents


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

# Valid suffixes for --project argument; anything else is a user error
_VALID_PROJECT_SUFFIXES = {'.json', '.blocs', ''}


def main() -> None:
    # --- startup config: user-level, load immediately ---
    startup_cfg = Config()
    StartupDialog.register_config(startup_cfg)

    if platform.system() == "Windows":
        user_config_dir = Path.home() / "AppData" / "Local" / "emblocs"
    else:  # Linux, macOS, etc.
        user_config_dir = Path.home() / ".config" / "emblocs"

    user_config_dir.mkdir(parents=True, exist_ok=True)
    startup_cfg_file = user_config_dir / "recents.json"
    if startup_cfg_file.exists():
        startup_cfg.load_file(startup_cfg_file)

    # --- project config: registered now, loaded after project is chosen ---
    project_cfg = Config()
    MonitorApp.register_config(project_cfg)

    # --project is an unmapped arg: we resolve it manually below
    project_cfg.add_cli_arg('--project', '-p',
                            help='Path to project (e.g. ~/work/foo/bar or bar.blocs)')
    args = project_cfg.parse_cli()

    # --- resolve --project argument if supplied ---
    # policy:
    #   valid suffix + parent dir exists + .json exists -> skip dialog, load directly
    #   valid suffix + parent dir exists + .json missing -> dialog with path pre-filled
    #   valid suffix + parent dir missing               -> dialog with error message
    #   invalid suffix                                  -> dialog with error message
    #   no --project arg                                -> dialog normally
    project_cfg_file  = None   # Path to .json if known
    project_blocs_file = None  # Path to .blocs if known (optional)
    dialog_initial_path = None
    dialog_error_msg    = None
    skip_dialog = False

    if args.project:
        project_arg  = Path(args.project).expanduser().resolve()
        project_stem = project_arg.stem
        project_dir  = project_arg.parent

        if project_arg.suffix not in _VALID_PROJECT_SUFFIXES:
            dialog_error_msg = (f"Unrecognised file type '{project_arg.suffix}'; "
                                f"expected .blocs, .json, or no suffix")
        elif not project_dir.is_dir():
            dialog_error_msg = f"Directory not found: {project_dir}"
        else:
            # directory exists; derive canonical file paths
            project_cfg_file   = project_dir / f"{project_stem}.json"
            project_blocs_file = project_dir / f"{project_stem}.blocs"
            if project_cfg_file.exists():
                # project config exists - full fast path, skip dialog
                skip_dialog = True
            else:
                # no .json yet - new or partial project, confirm via dialog
                dialog_initial_path = project_cfg_file

    # --- root window: hidden until project is chosen ---
    root = tk.Tk()
    root.withdraw()

    if not skip_dialog:
        dialog = StartupDialog(root, startup_cfg, project_cfg,
                               initial_path=dialog_initial_path,
                               error_msg=dialog_error_msg)
        root.mainloop()    # runs until dialog calls root.quit()

        if dialog.result is None:
            # user cancelled - exit cleanly
            root.destroy()
            return 1

        # dialog sets project_cfg_file and project_blocs_file
        # TODO: extract these from dialog.result once dialog is fully implemented
        project_cfg_file = dialog.result

    # --- update and save recents regardless of how project was chosen ---
    if project_cfg_file:
        update_recents(startup_cfg, project_cfg_file)
        startup_cfg.save_file(startup_cfg_file)

    # --- load project config if it exists ---
    if project_cfg_file and Path(project_cfg_file).exists():
        project_cfg.load_file(project_cfg_file)
    # --- merge command line options last so they overrule file values
    project_cfg.merge_cli()

    # --- build and run main application ---
    app = MonitorApp(root, project_cfg)
    root.deiconify()
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()    # runs until main window is closed

    # --- save configs on exit ---
    if project_cfg_file:
        project_cfg.save_file(project_cfg_file)


if __name__ == '__main__':
    sys.exit(main())
