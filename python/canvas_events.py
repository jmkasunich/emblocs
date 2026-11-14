#! /usr/bin/env python3
# canvas_events.py

from enum import Enum
from dataclasses import dataclass

# this class doesn't stricly belong here, but it is a helper
# used in more than one place, and it is related to Canvas
# so it can live here for now

@dataclass(frozen=True)
class CanvasBox:
    left: int
    top: int
    right: int
    bottom: int

    def as_rect(self):
        """Coordinates for canvas.create_rectangle, in its (x1, y1, x2, y2) order."""
        return (self.left, self.top, self.right, self.bottom)

    def width(self):
        return self.right - self.left

    def height(self):
        return self.bottom - self.top


class CanvasEventState(Enum):
    IDLE = 1
    PRESSED = 2
    WAIT_FOR_RELEASE = 3
    DOUBLE_CLICK_WAIT = 4
    DRAGGING = 5

class CanvasEvents:
    """ Class to manage user input for a Canvas
    Binds to TkInter events from the canvas and emits a smaller
    set of application-oriented callback events, as follows:

       on_pointer_move(x, y)  - pointer position changed to 'x, y';
                                if the pointer leaves the canvas,
                                x & y are both None
       on_pointer_hover(x, y) - pointer remained at 'x, y' for 'hover_time_ms'
       on_single_click(x, y)  - single-clicked at 'x, y'
       on_double_click(x, y)  - double-clicked at 'x, y'
       on_long_press(x, y)    - long button press at 'x, y'
       on_wheel(x, y, delta)  - mouse wheel or touchpad gesture at 'x, y'
       on_drag(x, y, dx, dy)  - incremental drag of 'dx, dy' ending at 'x, y'

    All callback coordinates are in pixels.  Single and double-click
    are mutually exclusive; a double click does not generate spurious
    single-click events; however, this is gained at the expense of not
    using the OS defined double-click interval and delaying single
    clicks until 'double_click_time_ms' after button release.
    """
    def __init__(self, canvas,
                 hover_time_ms=1500,
                 double_click_time_ms=250,
                 long_press_time_ms=1500,
                 drag_threshold_px=5):
        self.canvas = canvas
        self.hover_time_ms = hover_time_ms
        self.double_click_time_ms = double_click_time_ms
        self.long_press_time_ms = long_press_time_ms
        self.drag_threshold_px = drag_threshold_px
        # callbacks
        self.on_pointer_move = None
        self.on_pointer_hover = None
        self.on_single_click = None
        self.on_double_click = None
        self.on_long_press = None
        self.on_wheel = None
        self.on_drag = None
        # internal state
        self.state = CanvasEventState.IDLE
        self.mouse_x = None
        self.mouse_y = None
        self.press_timer = None
        self.hover_timer = None
        # bind UI events
        canvas.bind("<Enter>", self._on_enter)
        canvas.bind("<Leave>", self._on_leave)
        canvas.bind("<Motion>", self._on_motion)
        canvas.bind("<ButtonPress-1>", self._on_button1_press)
        canvas.bind("<B1-Motion>", self._on_button1_motion)
        canvas.bind("<ButtonRelease-1>", self._on_button1_release)
        canvas.bind("<MouseWheel>", self._on_mouse_wheel)

    # helper functions

    def _emit_pointer_move(self, x, y):
        if self.on_pointer_move is not None:
            self.on_pointer_move(x, y)

    def _emit_pointer_hover(self, x, y):
        if self.on_pointer_hover is not None:
            self.on_pointer_hover(x, y)

    def _emit_single_click(self, x, y):
        if self.on_single_click is not None:
            self.on_single_click(x, y)

    def _emit_double_click(self, x, y):
        if self.on_double_click is not None:
            self.on_double_click(x, y)

    def _emit_long_press(self, x, y):
        if self.on_long_press is not None:
            self.on_long_press(x, y)

    def _emit_wheel(self, x, y, delta):
        if self.on_wheel is not None:
            self.on_wheel(x, y, delta)

    def _emit_drag(self, x, y, dx, dy):
        if self.on_drag is not None:
            self.on_drag(x, y, dx, dy)

    def _cancel_hover_timeout(self):
        if self.hover_timer is not None:
            self.canvas.after_cancel(self.hover_timer)
            self.hover_timer = None

    def _cancel_press_timeout(self):
        if self.press_timer is not None:
            self.canvas.after_cancel(self.press_timer)
            self.press_timer = None

    # event handlers - these also implement the state machine logic

    def _on_enter(self, event):
        """Mouse entered the canvas.
        No drag or click can be in progress at this point
        """
        self.mouse_x = event.x
        self.mouse_y = event.y
        self.state = CanvasEventState.IDLE
        self._emit_pointer_move(event.x, event.y)

    def _on_leave(self, event):
        """Mouse left the canvas.
        Any pending clicks or drags are canceled.
        """
        self._cancel_press_timeout()
        self._cancel_hover_timeout()
        self.state = CanvasEventState.IDLE
        self._emit_pointer_move(None, None)

    def _on_motion(self, event):
        """Pointer moved within the canvas with no buttons pressed."""
        self._cancel_hover_timeout()
        self.mouse_x = event.x
        self.mouse_y = event.y
        self._emit_pointer_move(event.x, event.y)
        self.hover_timer = self.canvas.after(self.hover_time_ms,
                                             self._on_hover_timeout)

    def _on_hover_timeout(self):
        self.hover_timer = None
        if self.state is CanvasEventState.IDLE:
            self._emit_pointer_hover(self.mouse_x, self.mouse_y)

    def _on_button1_press(self, event):
        """Beginning of a click or drag."""
        self._cancel_hover_timeout()
        self.mouse_x = event.x
        self.mouse_y = event.y
        if self.state is CanvasEventState.IDLE:
            self.state = CanvasEventState.PRESSED
            self.press_timer = self.canvas.after(self.long_press_time_ms,
                                                self._on_long_press_timeout)
        elif self.state is CanvasEventState.DOUBLE_CLICK_WAIT:
            self._cancel_press_timeout()
            self.state = CanvasEventState.WAIT_FOR_RELEASE
            self._emit_double_click(event.x, event.y)

    def _on_long_press_timeout(self):
        self.press_timer = None
        self.state = CanvasEventState.WAIT_FOR_RELEASE
        self._emit_long_press(self.mouse_x, self.mouse_y)

    def _on_button1_motion(self, event):
        """Mouse movement while button 1 is held."""
        dx = event.x - self.mouse_x
        dy = event.y - self.mouse_y
        if self.state is CanvasEventState.PRESSED:
            if abs(dx) + abs(dy) >= self.drag_threshold_px:
                self.state = CanvasEventState.DRAGGING
                self._cancel_press_timeout()
                self._cancel_hover_timeout()
        if self.state is CanvasEventState.DRAGGING:
            self.mouse_x = event.x
            self.mouse_y = event.y
            self._emit_drag(event.x, event.y, dx, dy)

    def _on_button1_release(self, event):
        """End of a click or drag."""
        self._cancel_press_timeout()
        if self.state is CanvasEventState.WAIT_FOR_RELEASE:
            self.state = CanvasEventState.IDLE
        elif self.state is CanvasEventState.PRESSED:
            self.state = CanvasEventState.DOUBLE_CLICK_WAIT
            self.press_timer = self.canvas.after(self.double_click_time_ms,
                                                 self._on_double_click_timeout)
        elif self.state is CanvasEventState.DRAGGING:
            dx = event.x - self.mouse_x
            dy = event.y - self.mouse_y
            self.mouse_x = event.x
            self.mouse_y = event.y
            self.state = CanvasEventState.IDLE
            if dx != 0 or dy != 0:
                self._emit_drag(event.x, event.y, dx, dy)

    def _on_double_click_timeout(self):
        self.press_timer = None
        if self.state is CanvasEventState.DOUBLE_CLICK_WAIT:
            self._emit_single_click(self.mouse_x, self.mouse_y)
            self.state = CanvasEventState.IDLE

    def _on_mouse_wheel(self, event):
        """Mouse wheel or touchpad scroll gesture."""
        self._emit_wheel(event.x, event.y, event.delta)


