#! /usr/bin/env python3
# histogram_display.py

import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
from dataclasses import dataclass
import math
from enum import Enum
from linear_axis import LinearAxis
from histogram import Histogram
from canvas_events import CanvasBox, CanvasEvents
from channel_controls import Channel, ChannelList, ChannelControls
from display_controls import DisplayControls
from time_display import TimeDisplay
from typing import Optional

import traceback

# screen geometry configuration constants

BORDER = 2            # gap between canvas edge and drawn content
MINOR_TICK_LEN = 3
MAJOR_TICK_LEN = 6  
TICK_LABEL_SPACE = 3  # space between end of major tick and label text

OUTLIER_BAR_WIDTH = 20
DIVIDER_MIN_WIDTH = 15


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

def channel_tag(channel: Channel, part: ChannelPart) -> str:
    """Tag for a channel item, e.g. 'Chan02_fill'."""
    if channel is None:
        raise ValueError("channel does not exist")
    return f"{channel.channel_name}_{part.value}"


@dataclass
class TestSource:
    name: str
    histogram: Histogram


class HistogramDisplay(tk.Frame):
    def __init__(self, parent, num_channels: int,
                 palette: Optional[tuple[tuple[str, str], ...]] = None):
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
        self.range_min = -2000.0
        self.range_max =  2000.0
        self.min_x_span = 4.0
        # data model
        self.channel_list = ChannelList(num_channels, palette)
        self.channel_list.add_observer(self._mark_dirty)
        self.y_axis = LinearAxis(value_min = 0.0,
                                 value_max = float(self.max_counts),
                                 major_spacing = self.axis_text_height*2)
        self.y_axis.add_observer(self._mark_dirty)
        self.x_axis = LinearAxis(value_min = float(self.range_min),
                                 value_max = float(self.range_max),
                                 major_spacing = self.axis_text_height*2)
        self.x_axis.add_observer(self._mark_dirty)
        # view/control of model
        self.controls_frame = tk.Frame(self)
        self.controls_frame.grid(row=0, column=0, sticky="nsew")
        self.canvas = tk.Canvas(self, background="black", highlightthickness=0)
        self.canvas.grid(row=0, column=1, sticky="nsew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        # sub-panels inside controls_frame
        self.channel_controls = ChannelControls(self.controls_frame,
                                                self.channel_list)
        self.channel_controls.pack(side="top", fill="x")
        self.display_controls = DisplayControls(self.controls_frame,
                                                command=self._mark_dirty)
        self.display_controls.pack(side="top", fill="x")
        self.time_display = TimeDisplay(self.controls_frame)
        self.time_display.pack(side="top", fill="x")
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
        print("init complete")

    def _on_pointer_move(self, x, y):
        #print("pointer_move", x, y)
        if x is not None:
            print(f"{x:3}, {y:3}    \r", end="")
        pass

    def _on_pointer_hover(self, x, y):
        #print("pointer_hover", x, y)
        pass

    def _on_single_click(self, x, y):
        print("single_click", x, y)

    def _on_double_click(self, x, y):
        print("double_click", x, y)

    def _on_long_press(self, x, y):
        print("long_press", x, y)

    def _on_wheel(self, x, y, delta):
        where = self._region_at(x, y)
        factor = math.exp(-delta/1000)
        if where == "x_axis" or where == "plot":
            self.x_axis.zoom(factor, self.x_axis.p2v(x),
                             min_span=1, max_span=1000)
        elif where == "y_axis":
            self.y_axis.zoom(factor, 0, min_span=1, max_span=1000)

    def _on_drag(self, x, y, dx, dy):
        if abs(dx) > abs(dy):
            # horizontal drag
            value_dx = -self.x_axis.dp2dv(dx)
            self.x_axis.pan(value_dx, min_value=-1000, max_value=1000)

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
        print("reset view")
        self.y_axis.set_range(0.0, float(self.max_counts))
        self.x_axis.set_range(float(self.range_min), float(self.range_max))

    def _on_resize(self, event):
        print("on resize")
        self._layout()

    def _layout(self):
        print("layout")
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

    def _mark_dirty(self):
        print("mark dirty")
        if not self.dirty:
            if self.plot_box is None:
                return
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
        fg = "white"
        grid = "gray15"
        # draw axis
        self.canvas.create_line(right, top, right, bottom,
                                tags=base_tag, fill=fg)
        # draw minor ticks
        for value in axis.get_minor_values():
            y = axis.v2p(value)
            self.canvas.create_line(right-MINOR_TICK_LEN, y, right, y,
                                    tags=body_tag, fill=fg)
        # draw major ticks
        for value in axis.get_major_values():
            y = axis.v2p(value)
            self.canvas.create_line(right-MAJOR_TICK_LEN, y, right, y,
                                    tags=body_tag, fill=fg)
            self.canvas.create_line(right, y, plot_right, y,
                                    tags=grid_tag, fill=grid)
            self.canvas.create_text(right-(MAJOR_TICK_LEN+TICK_LABEL_SPACE), y,
                                    anchor="e", angle=0, font=self.axis_font,
                                    tags=body_tag, fill=fg, text=str(value))

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
        fg = "white"
        # draw axis
        self.canvas.create_line(left, top, right, top,
                                tags=base_tag, fill=fg)
        # draw minor ticks
        for value in axis.get_minor_values():
            x = axis.v2p(value)
            self.canvas.create_line(x, top, x, top+MINOR_TICK_LEN,
                                    tags=body_tag, fill=fg)
        # draw major ticks
        for value in axis.get_major_values():
            x = axis.v2p(value)
            self.canvas.create_line(x, top, x, top+MAJOR_TICK_LEN,
                                    tags=body_tag, fill=fg)
            self.canvas.create_text(x+TICK_LABEL_SPACE,
                                    top+MAJOR_TICK_LEN+TICK_LABEL_SPACE,
                                    anchor="e", angle=55, font=self.axis_font,
                                    tags=body_tag, fill=fg, text=str(value))

    def draw_histogram(self, chan: Channel,
                       x_axis: LinearAxis, y_axis: LinearAxis):
        line_tag = channel_tag(chan, ChannelPart.LINE)
        fill_tag = channel_tag(chan, ChannelPart.FILL)
        divider_tag = channel_tag(chan, ChannelPart.DIVIDERS)
        self.canvas.delete(line_tag)
        self.canvas.delete(fill_tag)
        self.canvas.delete(divider_tag)
        if not chan.visible or chan.source is None:
            return
        histo = chan.source.histogram
        filled = self.display_controls.filled
        dividers = False
        px_min = x_axis.pixel_min
        px_max = x_axis.pixel_max
        py_min = y_axis.pixel_min
        if chan == self.channel_list.selected:
            color = chan.selected_color
        else:
            color = chan.normal_color
        coords = []
        if histo.value_type is int:
            range_min = histo.range_min - 0.5
            range_max = histo.range_max + 0.5
        else:
            range_min = histo.range_min
            range_max = histo.range_max
        if (x_axis.value_max <= range_min or
            x_axis.value_min >= range_max):
            return  # histogram is entirely off-screen
        pixels_per_bin = histo.bin_width / x_axis.dp2dv(1)
        py = py_min
        vy_old = 0
        py_old = py
        if pixels_per_bin >= 1:
            # loop over bins
            if x_axis.value_min <= range_min:
                first_visible_bin = 0
            else:
                first_visible_bin = histo.find_bin(x_axis.value_min)
            if x_axis.value_max >= range_max:
                last_visible_bin = histo.num_bins - 1
            else:
                last_visible_bin = histo.find_bin(x_axis.value_max)
            if pixels_per_bin > DIVIDER_MIN_WIDTH:
                dividers = True
                divider_coords = []
            for bin_num in range(first_visible_bin, last_visible_bin+1):
                vy = min(histo.counts[bin_num], y_axis.value_max)
                if vy != vy_old:
                    # horizontal segment across previous bin(s)
                    vx = range_min + bin_num * histo.bin_width
                    px = max(x_axis.v2p(vx), px_min)
                    # top right corner of previous bar
                    coords += (px, py_old)
                    py = y_axis.v2p(vy)
                    # top left corner of current bar
                    coords += (px, py)
                    if dividers and py_old != py_min and py != py_min:
                        divider_coords += (px, py_min)
                        divider_coords += (px, max(py, py_old))
                        divider_coords += (px, py_min)
                    vy_old = vy
                    py_old = py
                elif dividers and py != py_min:
                    vx = range_min + bin_num * histo.bin_width
                    px = max(x_axis.v2p(vx), px_min)
                    divider_coords += (px, py_min)
                    divider_coords += (px, py)
                    divider_coords += (px, py_min)
            vx = range_min + (last_visible_bin + 1) * histo.bin_width
            px = min(x_axis.v2p(vx), px_max)
            # top right corner of last bar
            coords += (px, py_old)
            if py_old != py_min:
                # last point on baseline
                coords += (px, py_min)
        else:
            # loop over pixels
            if x_axis.value_min <= range_min:
                px_first = x_axis.v2p(range_min)
            else:
                px_first = x_axis.pixel_min
            if x_axis.value_max >= range_max:
                px_last = x_axis.v2p(range_max)
            else:
                px_last = x_axis.pixel_max
            first_bin = histo.find_bin(x_axis.p2v(px_first - 0.5))
            for px in range(px_first, px_last+1):
                last_bin = histo.find_bin(x_axis.p2v(px + 0.5))
                # slice to get all bins in this pixel, use highest count
                bins = histo.counts[first_bin:last_bin]
                vy = max(bins) if len(bins) > 0 else 0
                vy = min(vy, y_axis.value_max)
                if vy != vy_old:
                    py = y_axis.v2p(vy)
                    coords += (px, py_old)
                    coords += (px, py)
                    vy_old = vy
                    py_old = py
                first_bin = last_bin
            px = px_last
            coords += (px, py_old)
            if py_old != py_min:
                # last point on baseline
                coords += (px, py_min)
        # we now have coordinates, do the drawing
        if filled and len(coords) >= 6:
            self.canvas.create_polygon(*coords, tags=fill_tag, fill=color, outline="")
            if dividers and len(divider_coords) >= 4:
                self.canvas.create_line(*divider_coords, tags=divider_tag, fill="white")
            if dividers:
                self.canvas.create_line(*coords, tags=line_tag, fill="white")
            else:
                self.canvas.create_line(*coords, tags=line_tag, fill=color)
        elif len(coords) >= 4:
            if dividers and len(divider_coords) >= 4:
                self.canvas.create_line(*divider_coords, tags=divider_tag, fill=color)
            self.canvas.create_line(*coords, tags=line_tag, fill=color)


    def redraw(self):
        print("redraw")
        self.dirty = False
        self.draw_y_axis(self.y_axis)
        self.draw_x_axis(self.x_axis)
        self.time_display.update_timestamp()
        self.canvas.tag_raise(axis_tag(Axis.Y, AxisPart.GRIDLINES))
        self.canvas.tag_raise(axis_tag(Axis.X, AxisPart.CONTENT))
        self.canvas.tag_raise(axis_tag(Axis.Y, AxisPart.CONTENT))
        for channel in self.channel_list.channels_back_to_front():
            self.draw_histogram(channel, self.x_axis, self.y_axis)
        self.canvas.tag_raise(axis_tag(Axis.X, AxisPart.BASELINE))
        self.canvas.tag_raise(axis_tag(Axis.Y, AxisPart.BASELINE))


#############################################################

if __name__ == "__main__":
    root = tk.Tk()
    root.title("HistogramDisplay test")
    display = HistogramDisplay(root, num_channels=2)

    histo = Histogram(value_type=int, range_min=0, bin_width=3,
                    counts=(5, 0, 2, 2, 9), above_count=6, below_count=7)
    display.channel_list.set_source(display.channel_list.selected,
                                    TestSource("test", histo))

    display.pack(fill="both", expand=True)
    root.geometry("600x400")
    root.mainloop()
