from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont

@dataclass(eq=False)
class Channel:
    name: str
    normal_color: str
    selected_color: str
    visible: bool = True

class ChannelList:
    def __init__(self):
        self._channels = []    # order is creation order, for stable display
        self._draw_order = []  # order is drawing order, last is in front
        self._selected = None  # the selected Channel, or None
        self._observers = []   # callbacks to be invoked on any change

    def add_channel(self, channel: Channel):
        if any(c is channel for c in self._channels):
            raise ValueError("channel is already in this list")
        self._channels.append(channel)
        self._draw_order.append(channel)
        if self._selected is None:
            self._selected = channel
        self._on_change()
        return channel

    def delete_channel(self, channel: Channel):
        self._channels.remove(channel)   # raises ValueError if absent
        self._draw_order.remove(channel)
        if self._selected is channel:
            self._selected = self._draw_order[-1] if self._draw_order else None
        self._on_change()

    def select(self, channel: Channel):
        if self._selected is channel:
            return  # already selected
        if channel not in self._channels:
            raise ValueError("channel is not in this list")
        self._selected = channel
        self._on_change()

    def bring_to_front(self, channel: Channel):
        if self._draw_order and self._draw_order[-1] is channel:
            return  # already in front
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
    def __init__(self, parent, channel_list: ChannelList):
        super().__init__(parent, text="Traces")
        self.channel_list = channel_list
        self.channel_widgets = {}     # Channel -> dict of child widgets
        self.visible_font = tkfont.nametofont("TkDefaultFont").copy()
        self.visible_font.configure(weight="bold", size=10)
        self.hidden_font = tkfont.nametofont("TkDefaultFont").copy()
        self.hidden_font.configure(slant="italic")
        self.font_height = self.visible_font.metrics("linespace")
        self.grid_columnconfigure(2, weight=1)
        channel_list.add_observer(self._on_change)
        self._on_change()

    @property
    def has_order_controls(self):
        return len(self.channel_list) > 1

    def _bind_select(self, widget, channel):
        widget.bind("<Button-1>", lambda e, ch=channel: self.channel_list.select(ch))

    def _create_widgets(self, channel):
        widgets = {}
        height = self.font_height
        border = max(height // 4, 2)
        # row container, children packed left to right
        row = tk.Frame(self)
        row.pack(side="top", fill="x", pady=0)
        widgets["row"] = row
        # marker: fixed width in characters
        widgets["marker"] = tk.Label(row, font=self.visible_font, width=3)
        widgets["marker"].pack(side="left")
        # swatch: black border around a square color patch
        swatch_box = tk.Frame(row, background="black")
        swatch_box.pack(side="left", padx=(2, 4))
        widgets["swatch_box"] = swatch_box
        widgets["swatch"] = tk.Frame(swatch_box, background=channel.normal_color,
                                     width=height, height=height)
        widgets["swatch"].pack(padx=border, pady=border)
        # eye: will be drawn on a canvas
        eye_canvas_height = height
        eye_canvas_width = 2 * height
        eye_canvas = tk.Canvas(row, width=eye_canvas_width, height=eye_canvas_height)
        eye_canvas.pack(side="left")
        eye_canvas.bind("<Button-1>", lambda e, ch=channel: self._on_eye_click(e, ch))
        # eye dimensions
        center_x = 0.5 * eye_canvas_width
        center_y = 0.5 * eye_canvas_height
        minor_rad = 0.3 * eye_canvas_height
        major_rad = 3.414 * minor_rad  # sqrt(2) + 2; makes arcs meet at corners
        line_wid = 0.02*eye_canvas_height + 1.1
        # draw the eye with tag 'eye'
        eye_canvas.create_arc(center_x-major_rad, center_y-minor_rad,
                              center_x+major_rad, center_y-minor_rad+2*major_rad,
                              style="arc", start=45, extent=90,
                              tags="eye", width=line_wid)
        eye_canvas.create_arc(center_x-major_rad, center_y+minor_rad,
                              center_x+major_rad, center_y+minor_rad-2*major_rad,
                              style="arc", start=225, extent=90,
                              tags="eye", width=line_wid)
        eye_canvas.create_oval(center_x-minor_rad, center_y-minor_rad,
                               center_x+minor_rad, center_y+minor_rad,
                               tags="eye", width= line_wid)
        # draw the slash through the eye with tag "slash"
        eye_canvas.create_line(center_x-0.5*eye_canvas_height, eye_canvas_height,
                               center_x+0.5*eye_canvas_height, 0,
                               tags="slash", width=line_wid*1.5)
        # hide the slash
        eye_canvas.itemconfig("slash", state="hidden")
        widgets["eye_canvas"] = eye_canvas
        # name: takes the remaining width
        widgets["name"] = tk.Label(row, font=self.visible_font, anchor="w")
        widgets["name"].pack(side="left", fill="x", expand=True, padx=2)
        # selection: every child except the eye selects this channel
        for name in ("marker", "swatch_box", "swatch", "name"):
            self._bind_select(widgets[name], channel)
        self.channel_widgets[channel] = widgets

    def _destroy_widgets(self, channel):
        for widget in self.channel_widgets.pop(channel).values():
            widget.destroy()

    def _update_row(self, channel):
        widgets = self.channel_widgets[channel]
        if self.channel_list.selected is channel:
            marker_text = ">"
            swatch_color = channel.selected_color
        else:
            marker_text = ""
            swatch_color = channel.normal_color
        widgets["marker"].configure(text=marker_text)
        if channel.visible:
            widgets["eye_canvas"].itemconfig("eye", outline="black")
            widgets["eye_canvas"].itemconfig("slash", state="hidden")
        else:
            widgets["eye_canvas"].itemconfig("eye", outline="gray70")
            widgets["eye_canvas"].itemconfig("slash", state="normal", fill="gray70")
        widgets["swatch"].configure(background=swatch_color)
        widgets["name"].configure(text=channel.name)

    def _on_change(self):
        current = list(self.channel_list)
        # destroy rows for channels that left the list
        current_set = set(current)
        for channel in list(self.channel_widgets):
            if channel not in current_set:
                self._destroy_widgets(channel)
        # create rows for channels that are new
        for channel in current:
            if channel not in self.channel_widgets:
                self._create_widgets(channel)
        # update all widgets
        for channel in current:
            self._update_row(channel)

    def _on_eye_click(self, evetn, channel):
        self.channel_list.set_visible(channel, not channel.visible)



#############################################################


if __name__ == "__main__":
    root = tk.Tk()
    root.title("ChannelControls test")

    chan_list = ChannelList()

    chan1 = Channel("chan 1", "dark red", "red")
    chan_list.add_channel(chan1)

    chan2 = Channel("chan 2", "dark green", "green")
    chan_list.add_channel(chan2)

    display = ChannelControls(root, chan_list)
    display.pack(fill="both", expand=True)
    root.geometry("600x400")
    root.mainloop()
