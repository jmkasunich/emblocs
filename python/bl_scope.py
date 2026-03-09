#! /usr/bin/env python3
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
from datetime import datetime
from collections import deque

def float_range(start, stop, step):
    current = start
    while current < stop:
        yield current
        current += step

CHANNELS = 4

class Scope(ttk.Frame):
    '''
    oscilloscope widget
     - displays incoming binary data as scope traces

    This class handles the display and user interface, not the serial port
    '''
    def __init__(self, parent, config, **kwargs):
        '''
        :param config: instance of AppConfig with config data
        '''
        # Call the parent class (ttk.Frame) constructor
        super().__init__(parent, **kwargs)

        self.cfgdata = config.data

        self.hdivs = self.cfgdata['scope']['horiz_divs']
        self.vdivs = self.cfgdata['scope']['vert_divs']
        self.time_per_div = self.cfgdata['scope']['time_per_div']
        self.time_per_sample = self.cfgdata['scope']['time_per_sample']
        self.time_at_center = self.cfgdata['scope']['time_at_center']

         # canvas widget for main content
        self.canvas = tk.Canvas(self, background="black", borderwidth=0, highlightthickness=0)

        self.canvas.grid(row=0, column=0, sticky='nsew')

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.data = deque()

        self.canvas.bind("<Configure>", self.on_resize)


    @staticmethod
    def add_config_data(config):
        '''
        adds config fields needed by a Scope object
        should be called before a Scope is created

        :param config: config object to which fields are added
        '''
        config.data['scope']={}
        config.data['scope']['horiz_divs']=10
        config.data['scope']['vert_divs']=8
        config.data['scope']['time_per_div']=0.1
        config.data['scope']['time_per_sample']=0.001
        config.data['scope']['time_at_center']=-0.5
        # for chan in range(0, CHANNELS):
        #     chan_key = f"channel_{chan:02d}"
        #     config.data['scope'][chan_key]={}
        #     config.data['scope'][chan_key]['units_offset']=0.0
        #     config.data['scope'][chan_key]['units_per_div']=1.0
        #     config.data['scope'][chan_key]['divs_offset']=0.0

    def on_resize(self, event):
        self.canvas.delete("all")
        width = event.width
        height = event.height
        xmargin = 10.0
        ymargin = 5.0
        self.xmid = width/2.0
        self.ymid = height/2.0
        self.xhalfsize = self.xmid-xmargin
        self.yhalfsize = self.ymid-ymargin
        self.draw_grid(width, height)

    def draw_x_line(self, x):
        self.canvas.create_line(x, self.ymid-self.yhalfsize, x, self.ymid+self.yhalfsize, state="disabled", tags="grid_line")

    def draw_x_tick(self, x, ticklen):
        self.canvas.create_line(x, self.ymid-ticklen, x, self.ymid+ticklen, state="disabled", tags="grid_tick")
        self.canvas.create_line(x, self.ymid-self.yhalfsize, x, self.ymid-self.yhalfsize+ticklen, state="disabled", tags="grid_tick")
        self.canvas.create_line(x, self.ymid+self.yhalfsize, x, self.ymid+self.yhalfsize-ticklen, state="disabled", tags="grid_tick")

    def draw_y_line(self, y):
        self.canvas.create_line(self.xmid-self.xhalfsize, y, self.xmid+self.xhalfsize, y, state="disabled", tags="grid_line")

    def draw_y_tick(self, y, ticklen):
        self.canvas.create_line(self.xmid-ticklen, y, self.xmid+ticklen, y, state="disabled", tags="grid_tick")
        self.canvas.create_line(self.xmid-self.xhalfsize, y, self.xmid-self.xhalfsize+ticklen, y, state="disabled", tags="grid_tick")
        self.canvas.create_line(self.xmid+self.xhalfsize, y, self.xmid+self.xhalfsize-ticklen, y, state="disabled", tags="grid_tick")

    def draw_grid(self, width, height):
        self.draw_x_line(self.xmid)
        self.draw_y_line(self.ymid)
        xticks = 5 * self.hdivs
        yticks = 5 * self.vdivs
        minticksize = 6.0
        maxticklen = 5.0
        xticksize = self.xhalfsize/xticks
        if xticksize > minticksize:
            xtickmod = 1
        elif xticksize * 2 > minticksize:
            xtickmod = 2
        elif xticksize * 5 > minticksize:
            xtickmod = 5
        else:
            xtickmod = 10
        yticksize = self.yhalfsize/yticks
        if yticksize > minticksize:
            ytickmod = 1
        elif yticksize * 2 > minticksize:
            ytickmod = 2
        elif yticksize * 5 > minticksize:
            ytickmod = 5
        else:
            ytickmod = 10
        xticklen = min(yticksize * min(ytickmod, 6) * 0.5, maxticklen)
        yticklen = min(xticksize * min(xtickmod, 6) * 0.5, maxticklen)
        for xtick in range(1, xticks+1):
            dx = xtick * xticksize
            if xtick % xtickmod == 0:
                if xtick % 10 == 0:
                    self.draw_x_line(self.xmid-dx)
                    self.draw_x_line(self.xmid+dx)
                elif xtickmod == 1 and xtick % 5 == 0:
                    self.draw_x_tick(self.xmid-dx, 1.5*xticklen)
                    self.draw_x_tick(self.xmid+dx, 1.5*xticklen)
                else:
                    self.draw_x_tick(self.xmid-dx, xticklen)
                    self.draw_x_tick(self.xmid+dx, xticklen)
        for ytick in range(1, yticks+1):
            dy = ytick * yticksize
            if ytick % ytickmod == 0:
                if ytick % 10 == 0:
                    self.draw_y_line(self.ymid-dy)
                    self.draw_y_line(self.ymid+dy)
                elif ytickmod == 1 and ytick % 5 == 0:
                    self.draw_y_tick(self.ymid-dy, 1.5*yticklen)
                    self.draw_y_tick(self.ymid+dy, 1.5*yticklen)
                else:
                    self.draw_y_tick(self.ymid-dy, yticklen)
                    self.draw_y_tick(self.ymid+dy, yticklen)
        self.canvas.itemconfigure("grid_line", width=1, fill="gray30")
        self.canvas.itemconfigure("grid_tick", width=1, fill="gray30")

    def data_clear(self):
        self.data.clear()

    def data_append(self, sample):
        if isinstance(sample, tuple) and len(sample) == CHANNELS:
            self.data.append(sample)
        else:
            print(f"{sample=} is not a {CHANNELS}-item tuple")

    def data_plot(self):
        time_left = self.time_at_center - self.time_per_div * self.hdivs/2
        time_right = self.time_at_center + self.time_per_div * self.hdivs/2
        time_newest = 0.0
        # FIXME - there are probably off-by-one or fencepost errors in here
        sample_right = int((time_right - time_newest) / self.time_per_sample)
        sample_right = min(sample_right, -1)
        sample_left = int((time_left - time_newest) / self.time_per_sample)
        sample_left = max(sample_left, -len(self.data))
        samples = self.data[sample_left:sample_right]

