#! /usr/bin/env python3
# histogram_display.py

import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
from dataclasses import dataclass
import math
from enum import Enum
from value_axis import ValueAxis
from histogram import Histogram
from canvas_events import CanvasBox, CanvasEvents


# screen geometry configuration constants

BORDER = 2            # gap between canvas edge and drawn content
MINOR_TICK_LEN = 3
MAJOR_TICK_LEN = 6  
TICK_LABEL_SPACE = 3  # space between end of major tick and label text

class Axis(Enum):
    X = "X"
    Y = "Y"

class AxisPart(Enum):
    BASELINE = "baseline"
    GRIDLINES = "gridlines"
    CONTENT = "content"   # labels, major ticks, minor ticks

class ChannelPart(Enum):
    FILL = "fill"
    LINE = "line"
    DIVIDERS = "dividers"
    LABELS = "labels"

def axis_tag(axis: Axis, part: AxisPart) -> str:
    """Tag for an axis item, e.g. 'Y_ticks'."""
    return f"{axis.value}_{part.value}"

def channel_tag(channel: int, part: ChannelPart) -> str:
    """Tag for a channel item, e.g. 'Chan02_fill'."""
    if channel < 0:
        raise ValueError("channel number must not be negative")
    return f"Chan{channel:02d}_{part.value}"


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
        if where == "x_axis" or where == "plot":
            self._x_zoom(factor, self.x_axis.p2v(x))
        elif where == "y_axis":
            self._y_zoom(factor)

    def _on_drag(self, x, y, dx, dy):
        if abs(dx) > abs(dy):
            # horizontal drag
            value_dx = -self.x_axis.dp2dv(dx)
            self._x_pan(value_dx)

    def _region_at(self, x, y):
        """Return 'plot', 'x_axis', 'y_axis', or None."""
        if self.plot_box is None:
            return None
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
        zooms out.  Overall range is clamped by self.max_counts and
        self.min_y_span.
        """
        factor = float(factor)
        if not factor > 0.0:
            raise ValueError("zoom factor must be positive")
        if factor > 1.0:
            new_max = math.ceil(self.y_axis.value_max * factor)
        else:
            new_max = math.floor(self.y_axis.value_max * factor)
        new_max = max(min(new_max, self.max_counts), self.min_y_span)
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
        old_span = self.x_axis.value_max - self.x_axis.value_min
        max_span = self.range_max - self.range_min
        new_span = max(min((old_span * factor), max_span), self.min_x_span)
        factor = new_span / old_span
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
        if self.plot_box.width() <= 0 or self.plot_box.height() <= 0:
            return
        self.y_axis.set_location(self.y_axis_box.bottom, self.y_axis_box.top)
        self.x_axis.set_location(self.x_axis_box.left, self.x_axis_box.right)
        self._mark_dirty()

    def _mark_dirty(self):
        if not self.dirty:
            self.dirty = True
            self.after_idle(self.redraw)

    def draw_y_axis(self, axis):
        box = self.y_axis_box
        left = box.left
        right = box.right
        top = box.top
        bottom = box.bottom
        plot_right = self.plot_box.right
        base_tag = axis_tag(Axis.Y, AxisPart.BASELINE)
        body_tag = axis_tag(Axis.Y, AxisPart.CONTENT)
        grid_tag = axis_tag(Axis.Y, AxisPart.GRIDLINES)
        self.canvas.delete(base_tag)
        self.canvas.delete(body_tag)
        self.canvas.delete(grid_tag)
        # draw axis
        self.canvas.create_line(right, top, right, bottom,
                                tags=base_tag, fill="black")
        # draw minor ticks
        for value in axis.get_minor_values():
            y = axis.v2p(value)
            self.canvas.create_line(right-MINOR_TICK_LEN, y, right, y,
                                    tags=body_tag, fill="black")
        # draw major ticks
        for value in axis.get_major_values():
            y = axis.v2p(value)
            self.canvas.create_line(right-MAJOR_TICK_LEN, y, right, y,
                                    tags=body_tag, fill="black")
            self.canvas.create_line(right, y, plot_right, y,
                                    tags=grid_tag, fill="gray85")
            self.canvas.create_text(right-(MAJOR_TICK_LEN+TICK_LABEL_SPACE), y,
                                    anchor="e", angle=0, font=self.axis_font,
                                    tags=body_tag, fill="black", text=str(value))

    def draw_x_axis(self, axis):
        box = self.x_axis_box
        left = box.left
        right = box.right
        top = box.top
        bottom = box.bottom
        base_tag = axis_tag(Axis.X, AxisPart.BASELINE)
        body_tag = axis_tag(Axis.X, AxisPart.CONTENT)
        self.canvas.delete(base_tag)
        self.canvas.delete(body_tag)
        # draw axis
        self.canvas.create_line(left, top, right, top,
                                tags=base_tag, fill="black")
        # draw minor ticks
        for value in axis.get_minor_values():
            x = axis.v2p(value)
            self.canvas.create_line(x, top, x, top+MINOR_TICK_LEN,
                                    tags=body_tag, fill="black")
        # draw major ticks
        for value in axis.get_major_values():
            x = axis.v2p(value)
            self.canvas.create_line(x, top, x, top+MAJOR_TICK_LEN,
                                    tags=body_tag, fill="black")
            self.canvas.create_text(x+TICK_LABEL_SPACE,
                                    top+MAJOR_TICK_LEN+TICK_LABEL_SPACE,
                                    anchor="e", angle=55, font=self.axis_font,
                                    tags=body_tag, fill="black", text=str(value))

    def draw_histogram(self, histo: Histogram, x_axis: ValueAxis, y_axis: ValueAxis):
        if (x_axis.value_max < histo.range_min or
            x_axis.value_min > histo.range_max):
            return  # histogram is entirely off-screen
        if x_axis.value_min <= histo.range_min:
            first_visible_bin = 0
        else:
            first_visible_bin = histo.find_bin(x_axis.value_min)
        if x_axis.value_max >= histo.range_max:
            last_visible_bin = histo.num_bins - 1
        else:
            last_visible_bin = histo.find_bin(x_axis.value_max)
        pixels_per_bin = histo.bin_width / x_axis.dp2dv(1)
        if pixels_per_bin >= 1:
            # integer bins have dividers half-way between
            if histo.value_type is int:
                val_base = histo.range_min - 0.5
            else:
                val_base = histo.range_min
            left_edge_val = val_base + first_visible_bin * histo.bin_width
            left_edge_pix = x_axis.v2p(left_edge_val)
            prev_val = histo.counts[first_visible_bin]
            # loop over bins
            for bin_num in range(first_visible_bin, last_visible_bin+1):
                curr_val = histo.counts[bin_num]
                if curr_val != prev_val:
                    right_edge_val = val_base + (bin_num + 1) * histo.bin_width
                    right_edge_pix = x_axis.v2p(right_edge_val)
                    # do work here
                    left_edge_val = right_edge_val
                    left_edge_pix = right_edge_pix
        else:
            # loop over pixels
            pass



    def redraw(self):
        self.dirty = False
        self.draw_y_axis(self.y_axis)
        self.draw_x_axis(self.x_axis)
        self.canvas.tag_raise(axis_tag(Axis.Y, AxisPart.GRIDLINES))
        self.canvas.tag_raise(axis_tag(Axis.X, AxisPart.CONTENT))
        self.canvas.tag_raise(axis_tag(Axis.Y, AxisPart.CONTENT))
        # channels go here
        self.canvas.tag_raise(axis_tag(Axis.X, AxisPart.BASELINE))
        self.canvas.tag_raise(axis_tag(Axis.Y, AxisPart.BASELINE))


#############################################################

if __name__ == "__main__":
    root = tk.Tk()
    root.title("HistogramDisplay test")
    display = HistogramDisplay(root)
    display.pack(fill="both", expand=True)
    root.geometry("600x400")
    root.mainloop()
