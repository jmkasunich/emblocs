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
        self.y_axis = ValueAxis(value_min = 0, value_max = 10,
                                pixel_min =1, pixel_max = 0,
                                major_spacing = self.axis_text_height*2)
        self.x_axis = ValueAxis(value_min = -23.0, value_max = 17.5,
                                pixel_min =1, pixel_max = 0,
                                major_spacing = self.axis_text_height*2)
        self.canvas = tk.Canvas(self, background="white", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.canvas.bind("<Configure>", self._on_resize)

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
            self.canvas.create_text(right-MAJOR_TICK_LEN+TICK_LABEL_SPACE, y,
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
            self.canvas.create_rectangle(self.plot_box.as_rect, outline="red", tags="layout")
            self.canvas.create_rectangle(self.y_axis_box.as_rect, outline="green", tags="layout")
            self.canvas.create_rectangle(self.x_axis_box.as_rect, outline="blue", tags="layout")
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
