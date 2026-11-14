#! /usr/bin/env python3
# channel_controls.py

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
from typing import Optional

@dataclass(eq=False)
class Channel:
    channel_name: str
    normal_color: str
    selected_color: str
    source: Optional[str] = None  # none means unconnected
    visible: bool = True

    @property
    def source_name(self):
        return "----" if self.source is None else self.source


class ChannelList:
    def __init__(self, num_channels: int,
                 palette: Optional[tuple[tuple[str, str], ...]] = None):
        if num_channels < 1:
            raise ValueError("num_channels must be positive")
        if palette is None:
            palette = (("dark red", "red"),)
        if not isinstance(palette, tuple):
            raise TypeError("palette must be a tuple of (normal, selected) pairs")
        if len(palette) == 0:
            raise ValueError("palette must not be empty")
        for entry in palette:
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise ValueError("each palette entry must be a (normal, selected) pair")
            if not all(isinstance(color, str) for color in entry):
                raise TypeError("palette colors must be strings")
        self._channels = []    # order is creation order, for stable display
        self._draw_order = []  # order is drawing order, last is in front
        for n in range(num_channels):
            normal, selected = palette[n % len(palette)]
            channel_name = f"Chan{n+1:02d}"
            chan = Channel(channel_name, normal, selected)
            self._channels.append(chan)
            self._draw_order.append(chan)
        self._selected = self._draw_order[-1]  # the selected Channel
        self._observers = []   # callbacks to be invoked on any change

    def select(self, channel: Channel):
        if self._selected is channel:
            return  # already selected
        if channel not in self._channels:
            raise ValueError("channel is not in this list")
        self._selected = channel
        self._draw_order.remove(channel)
        self._draw_order.append(channel)
        self._on_change()

    def set_visible(self, channel: Channel, visible: bool):
        visible = bool(visible)
        if channel.visible == visible:
            return  # already in the requested state
        channel.visible = visible
        self._on_change()

    def add_observer(self, callback):
        self._observers.append(callback)

    def _on_change(self):
        for observer in self._observers:
            observer()

    def draw_position(self, channel: Channel) -> int:
        """1 is the front (drawn last); len(self) is the back."""
        return len(self._draw_order) - self._draw_order.index(channel)

    @property
    def selected(self):
        return self._selected

    def __iter__(self):
        return iter(self._channels)

    def __len__(self):
        return len(self._channels)


class ChannelControls(ttk.LabelFrame):
    def __init__(self, parent, channel_list: ChannelList,
                 font: Optional[tkfont.Font] = None):
        super().__init__(parent, text="Traces", padding=(2,0,0,3))
        self.channel_list = channel_list
        self._selected = tk.StringVar(value="")
        if font is None:
            self.font = tkfont.nametofont("TkDefaultFont").copy()
            self.font.configure(size=10)
        else:
            self.font = font
        self.font_height = self.font.metrics("linespace")
        self.channel_widgets = {}     # Channel -> dict of child widgets
        self.grid_columnconfigure(2, weight=1)
        channel_list.add_observer(self._on_change)
        self._on_change()

    def _create_widgets(self, channel):
        widgets = {}
        font_h = self.font_height | 1 # odd so center pixel is exact
        bdr = max(font_h // 5, 2)
        row_h = font_h + bdr * 2
        # row container, children packed left to right
        row = ttk.Frame(self)
        row.pack(side="top", fill="x", pady=0)
        widgets["row"] = row
        # eye: calculate dimensions
        canv_w = int(row_h * 1.6) | 1  # odd, so center is exact
        cen_x = canv_w // 2
        cen_y = row_h // 2
        minor_r = int(0.25 * row_h)
        major_r = int(3.414 * minor_r)  # sqrt(2) + 2; makes arcs meet at corners
        slash_r = int(0.35 * row_h)
        line_w = int(0.02 * row_h + 1.1)
        slash_w = int(0.025 * row_h + 1.3)
        # eye: create a black canvas
        eye_canvas = tk.Canvas(row, width=canv_w, height=row_h, bd=0,
                               highlightthickness=0, background="black")
        eye_canvas.pack(side="left", padx=0)
        eye_canvas.bind("<Button-1>", lambda e, ch=channel: self._toggle_visible(ch))
        widgets["eye_canvas"] = eye_canvas
        # eye: draw the eye with tag 'eye'
        eye_canvas.create_arc(cen_x-major_r, cen_y-minor_r,
                              cen_x+major_r, cen_y-minor_r+2*major_r,
                              style="arc", start=45, extent=90,
                              tags="eye", width=line_w)
        eye_canvas.create_arc(cen_x-major_r, cen_y+minor_r,
                              cen_x+major_r, cen_y+minor_r-2*major_r,
                              style="arc", start=225, extent=90,
                              tags="eye", width=line_w)
        eye_canvas.create_oval(cen_x-minor_r, cen_y-minor_r,
                               cen_x+minor_r, cen_y+minor_r,
                               tags="eye", width= line_w)
        # eye: draw the slash with tag "slash"
        eye_canvas.create_line(cen_x-slash_r, cen_y+slash_r,
                               cen_x+slash_r, cen_y-slash_r,
                               tags="slash", width=slash_w)
        # hide the slash
        eye_canvas.itemconfig("slash", state="hidden")
        # name: takes the remaining width
        name = ttk.Radiobutton(row, variable=self._selected,
                               value=channel.channel_name, text=channel.source_name,
                               command=lambda ch=channel: self.channel_list.select(ch))
        name.bind("<Key-v>", lambda e, ch=channel: self._toggle_visible(ch))
        name.pack(side="left", fill="x", expand=True, padx=2)
        widgets["name"] = name
        self.channel_widgets[channel] = widgets

    def _update_row(self, channel):
        widgets = self.channel_widgets[channel]
        if self.channel_list.selected is channel:
            swatch_color = channel.selected_color
        else:
            swatch_color = channel.normal_color
        if channel.visible:
            widgets["eye_canvas"].itemconfig("eye", outline=swatch_color)
            widgets["eye_canvas"].itemconfig("slash", state="hidden")
        else:
            widgets["eye_canvas"].itemconfig("eye", outline="gray70")
            widgets["eye_canvas"].itemconfig("slash", state="normal", fill="gray70")
        widgets["name"].configure(text=channel.source_name)

    def _on_change(self):
        selected = self.channel_list.selected
        self._selected.set(selected.channel_name if selected else "")
        current = list(self.channel_list)
        # create rows for channels that are new
        for channel in current:
            if channel not in self.channel_widgets:
                self._create_widgets(channel)
        # update all widgets
        for channel in current:
            self._update_row(channel)

    def _toggle_visible(self, channel):
        self.channel_list.set_visible(channel, not channel.visible)


#############################################################


if __name__ == "__main__":
    root = tk.Tk()
    root.title("ChannelControls test")

    palette = (("dark red", "red"), ("dark green", "green"))

    chan_list = ChannelList(4, palette)

    display = ChannelControls(root, chan_list)
    display.pack()
    root.geometry("600x400")
    root.mainloop()
