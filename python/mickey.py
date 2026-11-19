#! /usr/bin/env python3
# mickey.py
#
# Convenience classes to handle:
#  * Windows/Linux/Mac platform differeces in mouse-wheel handling
#  * Mouse gesture detection
#

import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass
from collections.abc import Callable, Iterable


@dataclass(frozen=True)
class ModifierKeys:
    shift: bool = False
    ctrl: bool = False
    alt: bool = False
    cmd: bool = False

    @property
    def ctrl_or_cmd(self) -> bool:
        return self.ctrl or self.cmd


@dataclass(frozen=True)
class MouseWheelEvent:
    x: int
    y: int
    steps: float
    modifiers: ModifierKeys

class MouseWheel:
    def __init__(self, widget: tk.Misc,
                 handler: Callable[[MouseWheelEvent], None]) -> None:
        self._widget = widget
        self._handler = handler


class EventLogger:
    def __init__(self, widget: tk.Misc, events: Iterable[str]) -> None:
        self._widget = widget
        self._need_newline = False
        self._prev_event_name = ""
        self._verbose = False
        for event_name in events:
            self._widget.bind(event_name,
                              lambda e, event_name=event_name:
                              self._on_event_generic(event_name, e),
                              add="+")

    def _on_event_generic(self, event_name: str, event: tk.Event):
        if self._need_newline and event_name != self._prev_event_name:
            print()
            self._need_newline = False
    
        print(f"{event_name:20}: type={event.type:3}", end="")
        if "Motion" in event_name:
            print(f"state={getattr(event, 'state'):8} x={getattr(event, 'x', None)} y={getattr(event, 'y', None)}", end="\r")
            self._need_newline = True
        elif self._verbose:
            print()
            for key, value in sorted(event.__dict__.items()):
                print(f"    {key}={value!r}")
        elif event_name.startswith("<Key"):
            print(f"state={getattr(event, 'state'):8} keysym='{getattr(event, 'keysym', None)}' ")
        else:
            print()
        self._prev_event_name = event_name

    def _on_event_specific(self, event_name: str, event: tk.Event):
        print(
            f"{event_name}: "
            f"type={event.type} "
            f"num={getattr(event, 'num', None)} "
            f"x={getattr(event, 'x', None)} "
            f"x={getattr(event, 'x', None)} "
            f"x_root={getattr(event, 'x_root', None)} "
            f"y_root={getattr(event, 'y_root', None)} "
            f"keysym={getattr(event, 'keysym', None)} "
            f"delta={getattr(event, 'delta', None)} "
            f"state=0x{getattr(event, 'state', 0):x}"
        )


################################################

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Event Logger")
    root.geometry("800x600")

    frame = ttk.Frame(root, padding=20)
    frame.pack(fill="both", expand=True)

    label = ttk.Label(
        frame,
        text=(
            "Move the mouse, click buttons, use the wheel,\n"
            "try side buttons, touchpad gestures, and touchscreen gestures.\n"
            "Watch the terminal output."
        ),
        justify="center",
    )
    label.pack(pady=10)

    button1 = ttk.Button(frame, text="Button1")
    button1.pack()

    canvas = tk.Canvas(
        frame,
        background="white",
        highlightthickness=1,
        highlightbackground="black",
    )
    canvas.pack(fill="both", expand=True)

    button2 = ttk.Button(frame, text="Button2")
    button2.pack()

    events = [
        # pointer movement
        "<Enter>",
        "<Leave>",
        "<Motion>",

        # button activity
        "<ButtonPress>",
        "<ButtonRelease>",
        "<Double-Button-1>",
        "<Double-Button-2>",
        "<Double-Button-3>",

        "<Any-ButtonPress>",
        "<Any-ButtonRelease>",

        # drag activity
        "<B1-Motion>",
        "<B2-Motion>",
        "<B3-Motion>",

        # wheel activity
        "<MouseWheel>",
        "<Button-4>",
        "<Button-5>",

        # keyboard
        "<KeyPress>",
        "<KeyRelease>",

        # focus
        "<FocusIn>",
        "<FocusOut>",
    ]

    logger = EventLogger(canvas, events)

    #canvas.focus_set()

    root.mainloop()
