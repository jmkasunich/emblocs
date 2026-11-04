#! /usr/bin/env python3
# histogram_display.py

import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
from value_axis import ValueAxis
from dataclasses import dataclass
import math

# screen geometry configuration constants

BORDER = 2            # gap between canvas edge and drawn content
MINOR_TICK_LEN = 3
MAJOR_TICK_LEN = 6  
TICK_LABEL_SPACE = 3  # space between end of major tick and label text

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
       on_wheel(x, y, delta)  - mouse wheel or touchpad gesture at 'x, y'
       on_drag(x, y, dx, dy)  - incremental drag of 'dx, dy' ending at 'x, y'

    All callback coordinates are in pixels.  Single and double-click
    are mutually exclusive; a double click does not generate spurious
    single-click events; however, this is gained at the expense of not
    using the OS defined double-click interval and delaying single
    clicks by 'double_click_time_ms'.
    """
    def __init__(self, canvas,
                 hover_time_ms=500,
                 double_click_time_ms=300,
                 drag_threshold_px=5):
        self.canvas = canvas
        # callbacks
        self.on_pointer_move = None
        self.on_hover = None
        self.on_click = None
        self.on_double_click = None
        self.on_wheel = None
        self.on_drag = None
        # internal state
        # self.mouse_x = None
        # self.mouse_y = None
        # self.button1_down = False
        # self.press_x = None
        # self.press_y = None
        # self.release_x = None
        # self.release_y = None
        # self.dragging = False
        # self.drag_start_x = None
        # self.drag_start_y = None
        # self.drag_current_x = None
        # self.drag_current_y = None
        # self.drag_mode = None
        # self.last_wheel_x = None
        # self.last_wheel_y = None
        # self.last_wheel_delta = None
        # bind UI events
        canvas.bind("<Enter>", self._on_enter)
        canvas.bind("<Leave>", self._on_leave)
        canvas.bind("<Motion>", self._on_motion)
        canvas.bind("<ButtonPress-1>", self._on_button1_press)
        canvas.bind("<B1-Motion>", self._on_button1_motion)
        canvas.bind("<ButtonRelease-1>", self._on_button1_release)
        #canvas.bind("<Double-Button-1>", self._on_double_click)
        canvas.bind("<MouseWheel>", self._on_mouse_wheel)

    # event handlers

    def _on_enter(self, event):
        """Mouse entered the canvas."""
        self._emit_pointer_move(event.x, event.y)

    def _on_leave(self, event):
        """Mouse left the canvas."""
        self._emit_pointer_move(None, None)

    def _on_motion(self, event):
        """Pointer moved within the canvas with no buttons pressed."""
        pass

    def _on_button1_press(self, event):
        """Beginning of a click or drag."""
        pass

    def _on_button1_motion(self, event):
        """Mouse movement while button 1 is held."""
        pass

    def _on_button1_release(self, event):
        """End of a click or drag."""
        pass

    def _on_mouse_wheel(self, event):
        """Mouse wheel or touchpad scroll gesture."""
        self._emit_wheel(event.x, event.y, event.delta)

    # def _on_double_click(self, event):
    #     """Button 1 double-click detected."""
    #     pass

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

    def _emit_wheel(self, x, y, delta):
        if self.on_wheel is not None:
            self.on_wheel(x, y, delta)

    def _emit_drag(self, x, y, dx, dy):
        if self.on_drag is not None:
            self.on_drag(x, y, dx, dy)




@dataclass(frozen=True)
class CanvasBox:
    left: int
    top: int
    right: int
    bottom: int

    def as_rect(self):
        """Coordinates for canvas.create_rectangle, in its (x1, y1, x2, y2) order."""
        return (self.left, self.top, self.right, self.bottom)


class HistogramDisplay(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        # widths and heights of the axis label zones; set by set_label_sizes()
        self.axis_font = tkfont.nametofont("TkFixedFont").copy()
        self.axis_font.configure(size=10)
        self.axis_text_height = self.axis_font.metrics("linespace")
        self.axis_text_ascent = self.axis_font.metrics("ascent")
        self.axis_text_y_length = self.axis_font.measure("88888M")
        self.axis_text_x_length = self.axis_font.measure("8.888e88")
        self.plot_box = None      # upper right: histogram
        self.y_axis_box = None    # upper left: Y labels and ticks
        self.x_axis_box = None    # lower right: X labels and ticks
        self.dirty = False
        self.max_counts = 150
        self.min_y_span = 5
        self.range_min = -20.0
        self.range_max =  40.0
        self.min_x_span = 4.0
        self.y_axis = ValueAxis(value_min = 0, value_max = self.max_counts,
                                pixel_min =1, pixel_max = 0,
                                major_spacing = self.axis_text_height*2)
        self.x_axis = ValueAxis(value_min = self.range_min, value_max = self.range_max,
                                pixel_min =1, pixel_max = 0,
                                major_spacing = self.axis_text_height*2)
        self.canvas = tk.Canvas(self, background="white", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.canvas.bind("<Configure>", self._on_resize)

    def _region_at(self, x, y):
        """Return 'plot', 'x_axis', 'y_axis', or None."""
        if self.plot_box.left <= x <= self.plot_box.right and \
           self.plot_box.top <= y <= self.plot_box.bottom:
            return "plot"
        if self.x_axis_box.left <= x <= self.x_axis_box.right and \
           self.x_axis_box.top <= y <= self.x_axis_box.bottom:
            return "x_axis"
        if self.y_axis_box.left <= x <= self.y_axis_box.right and \
           self.y_axis_box.top <= y <= self.y_axis_box.bottom:
            return "y_axis"
        return None

    def _reset_view(self):
        self.y_axis.set_range(0, self.max_counts)
        self.x_axis.set_range(self.range_min, self.range_max)
        self._mark_dirty()

    def _y_zoom(self, factor):
        """ Zoom the Y axis by 'factor'.  Less than 1.0 zooms in, more
        zooms out.  Overall range is clamped by self.counts_max and
        self.min_y_span.
        """
        factor = float(factor)
        if not factor > 0.0:
            raise ValueError("zoom factor must be positive")
        new_max = self.y_axis.value_max * factor
        new_max = round(max(min(new_max, self.max_counts), self.min_y_span))
        self.y_axis.set_range(0, new_max)
        self._mark_dirty()

    def _x_zoom(self, factor, around):
        """ Zoom the X axis by 'factor', centered on 'around', which is
        in value units.  If 'factor' is < 1.0, zooms in, > 1.0 zooms out.
        Overall range is clamped by self.range_min, self.range_max, and
        self.min_x_span.
        """
        factor = float(factor)
        around = float(around)
        if not factor > 0.0:
            raise ValueError("zoom factor must be positive")
        old_span = self.x_axis.value_max - self.x_axis.value_min;
        max_span = self.range_max - self.range_min
        new_span = max(min((old_span * factor), max_span), self.min_x_span)
        factor = new_span / old_span;
        around = max(min(around, self.range_max), self.range_min)
        new_min = around + factor * (self.x_axis.value_min - around)
        new_max = around + factor * (self.x_axis.value_max - around)
        new_min = max(min(new_min, self.range_max), self.range_min)
        new_max = max(min(new_max, self.range_max), self.range_min)
        self.x_axis.set_range(new_min, new_max)
        self._mark_dirty()

    def _x_pan(self, amount):
        """ Pan the X axis by 'amount', which is in value units.
        If 'amount' is positive, pan right, negative left.
        Overall range is clamped by self.range_min and self.range_max.
        """
        if amount > 0:
            amount = min(amount, self.range_max - self.x_axis.value_max)
        elif amount < 0:
            amount = max(amount, self.range_min - self.x_axis.value_min)
        new_min = self.x_axis.value_min + amount
        new_max = self.x_axis.value_max + amount
        self.x_axis.set_range(new_min, new_max)
        self._mark_dirty()


    def _on_resize(self, event):
        self._layout()

    def _layout(self):
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        # space for the Y (left) and X (bottom) axes
        # each contains a label and a major tick
        y_axis_width = BORDER + self.axis_text_y_length + TICK_LABEL_SPACE + MAJOR_TICK_LEN
        x_axis_height = BORDER + self.axis_text_x_length + TICK_LABEL_SPACE + MAJOR_TICK_LEN
        # need to allow for a label printed at the very top or right of the
        # plot space; can stick up beyond the plot itself
        top_border_width = BORDER + self.axis_text_ascent
        right_border_width = BORDER + self.axis_text_ascent
        self.plot_box = CanvasBox(left=y_axis_width, right=width-right_border_width,
                                  top=top_border_width, bottom=height-x_axis_height)
        self.y_axis_box = CanvasBox(left=BORDER, right=self.plot_box.left,
                                    top=self.plot_box.top, bottom=self.plot_box.bottom)
        self.x_axis_box = CanvasBox(left=self.plot_box.left, right=self.plot_box.right,
                                    top=self.plot_box.bottom, bottom=height - BORDER)
        self.y_axis.set_location(self.y_axis_box.bottom, self.y_axis_box.top)
        self.x_axis.set_location(self.x_axis_box.left, self.x_axis_box.right)
        self.canvas.delete("layout")
        self._mark_dirty()

    def _mark_dirty(self):
        if not self.dirty:
            self.dirty = True
            self.after_idle(self.redraw)

    def draw_y_axis(self):
        axis = self.y_axis
        box = self.y_axis_box
        left = box.left
        right = box.right
        top = box.top
        bottom = box.bottom
        plot_right = self.plot_box.right
        # draw axis
        self.canvas.create_line(right, top, right, bottom, fill="black")
        # draw minor ticks
        for value in axis.get_minor_values():
            y = axis.v2p(value)
            self.canvas.create_line(right-MINOR_TICK_LEN, y, right, y, fill="black")
        # draw major ticks
        for value in axis.get_major_values():
            y = axis.v2p(value)
            self.canvas.create_line(right-MAJOR_TICK_LEN, y, right, y, fill="black")
            self.canvas.create_line(right, y, plot_right, y, fill="gray85")
            self.canvas.create_text(right-(MAJOR_TICK_LEN+TICK_LABEL_SPACE), y,
                                    anchor="e", angle=0, font=self.axis_font,
                                    fill="black", text=str(value))

    def draw_x_axis(self):
        axis = self.x_axis
        box = self.x_axis_box
        left = box.left
        right = box.right
        top = box.top
        bottom = box.bottom
        # draw axis
        self.canvas.create_line(left, top, right, top, fill="black")
        # draw minor ticks
        for value in axis.get_minor_values():
            x = axis.v2p(value)
            self.canvas.create_line(x, top, x, top+MINOR_TICK_LEN, fill="black")
        # draw major ticks
        for value in axis.get_major_values():
            x = axis.v2p(value)
            self.canvas.create_line(x, top, x, top+MAJOR_TICK_LEN, fill="black")
            self.canvas.create_text(x+TICK_LABEL_SPACE, top+MAJOR_TICK_LEN+TICK_LABEL_SPACE,
                                    anchor="e", angle=55, font=self.axis_font,
                                    fill="black", text=str(value))
    def redraw(self):
        self.dirty = False
        self.canvas.delete("all")
        if 0:
            self.canvas.create_rectangle(*self.plot_box.as_rect, outline="red", tags="layout")
            self.canvas.create_rectangle(*self.y_axis_box.as_rect, outline="green", tags="layout")
            self.canvas.create_rectangle(*self.x_axis_box.as_rect, outline="blue", tags="layout")
        self.draw_y_axis()
        self.draw_x_axis()

#############################################################

if __name__ == "__main__":
    root = tk.Tk()
    root.title("HistogramDisplay test")
    display = HistogramDisplay(root)
    display.pack(fill="both", expand=True)
    root.geometry("600x400")
    root.mainloop()
