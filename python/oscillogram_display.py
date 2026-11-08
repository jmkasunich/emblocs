#! /usr/bin/env python3
# oscillogram_display.py

import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
from value_axis import ValueAxis
from dataclasses import dataclass
import math
from enum import Enum
from canvas_events import CanvasBox, CanvasEvents


# screen geometry configuration constants

BORDER = 2            # gap between canvas edge and drawn content
MINOR_TICK_LEN = 3
MAJOR_TICK_LEN = 6  
TICK_LABEL_SPACE = 3  # space between end of major tick and label text


class OscillogramDisplay(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        # widths and heights of the axis label zones; set by set_label_sizes()
        self.axis_font = tkfont.nametofont("TkFixedFont").copy()
        self.axis_font.configure(size=10)
        self.axis_text_height = self.axis_font.metrics("linespace")
        self.axis_text_ascent = self.axis_font.metrics("ascent")
        self.axis_text_y_length = self.axis_font.measure("8.888e88")
        self.axis_text_x_length = self.axis_font.measure("8.888e88")
        self.plot_box = None      # upper right: traces
        self.y_axis_box = None    # upper left: Y labels and ticks
        self.x_axis_box = None    # lower right: X labels and ticks
        self.dirty = False
        self.y_range_min = -20.0
        self.y_range_max =  40.0
        self.min_y_span = 4.0
        self.x_range_min = -20.0
        self.x_range_max =  40.0
        self.min_x_span = 4.0
        self.y_axis = ValueAxis(value_min = self.y_range_min, value_max = self.y_range_max,
                                pixel_min =1, pixel_max = 0,
                                major_spacing = self.axis_text_height*2)
        self.x_axis = ValueAxis(value_min = self.x_range_min, value_max = self.x_range_max,
                                pixel_min =1, pixel_max = 0,
                                major_spacing = self.axis_text_height*2)
        self.canvas = tk.Canvas(self, background="white", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.canvas.bind("<Configure>", self._on_resize)
        # application-level events built from raw Tk events
        self.events = CanvasEvents(self.canvas)
        self.events.on_pointer_move = self._on_pointer_move
        self.events.on_pointer_hover = self._on_pointer_hover
        self.events.on_single_click = self._on_single_click
        self.events.on_double_click = self._on_double_click
        self.events.on_long_press = self._on_long_press
        self.events.on_wheel = self._on_wheel
        self.events.on_drag = self._on_drag

    def _on_pointer_move(self, x, y):
        print("pointer_move", x, y)

    def _on_pointer_hover(self, x, y):
        print("pointer_hover", x, y)

    def _on_single_click(self, x, y):
        print("single_click", x, y)

    def _on_double_click(self, x, y):
        print("double_click", x, y)

    def _on_long_press(self, x, y):
        print("long_press", x, y)

    def _on_wheel(self, x, y, delta):
        where = self._region_at(x, y)
        factor = math.exp(delta/1000)
        if where == "x_axis":
            self._x_zoom(factor, self.x_axis.p2v(x))
        elif where == "y_axis":
            self._y_zoom(factor, self.y_axis.p2v(y))

    def _on_drag(self, x, y, dx, dy):
        if abs(dx) > 2 * abs(dy):
            # horizontal drag
            dy = 0
        elif abs(dy) > 2 * abs(dx):
            # vertical drag
            dx = 0
        value_dx = -self.x_axis.dp2dv(dx)
        value_dy = -self.y_axis.dp2dv(dy)
        self._x_pan(value_dx)
        self._y_pan(value_dy)

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
        self.y_axis.set_range(self.y_range_min, self.y_range_max)
        self.x_axis.set_range(self.x_range_min, self.x_range_max)
        self._mark_dirty()

    def _y_zoom(self, factor, around):
        """ Zoom the Y axis by 'factor', centered on 'around', which is
        in value units.  If 'factor' is < 1.0, zooms in, > 1.0 zooms out.
        Overall range is clamped by self.y_range_min, self.y_range_max, and
        self.min_y_span.
        """
        factor = float(factor)
        around = float(around)
        if not factor > 0.0:
            raise ValueError("zoom factor must be positive")
        old_span = self.y_axis.value_max - self.y_axis.value_min;
        max_span = self.y_range_max - self.y_range_min
        new_span = max(min((old_span * factor), max_span), self.min_y_span)
        factor = new_span / old_span;
        around = max(min(around, self.y_range_max), self.y_range_min)
        new_min = around + factor * (self.y_axis.value_min - around)
        new_max = around + factor * (self.y_axis.value_max - around)
        new_min = max(min(new_min, self.y_range_max), self.y_range_min)
        new_max = max(min(new_max, self.y_range_max), self.y_range_min)
        self.y_axis.set_range(new_min, new_max)
        self._mark_dirty()

    def _x_zoom(self, factor, around):
        """ Zoom the X axis by 'factor', centered on 'around', which is
        in value units.  If 'factor' is < 1.0, zooms in, > 1.0 zooms out.
        Overall range is clamped by self.x_range_min, self.x_range_max, and
        self.min_x_span.
        """
        factor = float(factor)
        around = float(around)
        if not factor > 0.0:
            raise ValueError("zoom factor must be positive")
        old_span = self.x_axis.value_max - self.x_axis.value_min;
        max_span = self.x_range_max - self.x_range_min
        new_span = max(min((old_span * factor), max_span), self.min_x_span)
        factor = new_span / old_span;
        around = max(min(around, self.x_range_max), self.x_range_min)
        new_min = around + factor * (self.x_axis.value_min - around)
        new_max = around + factor * (self.x_axis.value_max - around)
        new_min = max(min(new_min, self.x_range_max), self.x_range_min)
        new_max = max(min(new_max, self.x_range_max), self.x_range_min)
        self.x_axis.set_range(new_min, new_max)
        self._mark_dirty()

    def _y_pan(self, amount):
        """ Pan the Y axis by 'amount', which is in value units.
        If 'amount' is positive, pan up, negative down.
        Overall range is clamped by self.y_range_min and self.y_range_max.
        """
        if amount > 0:
            amount = min(amount, self.y_range_max - self.y_axis.value_max)
        elif amount < 0:
            amount = max(amount, self.y_range_min - self.y_axis.value_min)
        new_min = self.y_axis.value_min + amount
        new_max = self.y_axis.value_max + amount
        self.y_axis.set_range(new_min, new_max)
        self._mark_dirty()

    def _x_pan(self, amount):
        """ Pan the X axis by 'amount', which is in value units.
        If 'amount' is positive, pan right, negative left.
        Overall range is clamped by self.x_range_min and self.x_range_max.
        """
        if amount > 0:
            amount = min(amount, self.x_range_max - self.x_axis.value_max)
        elif amount < 0:
            amount = max(amount, self.x_range_min - self.x_axis.value_min)
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
        plot_top = self.plot_box.top
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
            self.canvas.create_line(x, top, x, plot_top, fill="gray85")
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
    root.title("OscillogramDisplay test")
    display = OscillogramDisplay(root)
    display.pack(fill="both", expand=True)
    root.geometry("600x400")
    root.mainloop()
