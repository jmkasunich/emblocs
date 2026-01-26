#! /usr/bin/env python3
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
from datetime import datetime

def float_range(start, stop, step):
    current = start
    while current < stop:
        yield current
        current += step


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

         # canvas widget for main content
        self.canvas = tk.Canvas(self, background="black", borderwidth=0, highlightthickness=0)

        self.canvas.grid(row=0, column=0, sticky='nsew')

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.canvas.bind("<Configure>", self.on_resize)


    @staticmethod
    def add_config_data(config):
        '''
        adds config fields needed by a Console object
        should be called before a Console is created

        :param config: config object to which fields are added
        '''
        config.data['scope']={}
        config.data['scope']['hdivs']=10
        config.data['scope']['vdivs']=8

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
        self.canvas.create_line(x, self.ymid-self.yhalfsize, x, self.ymid+self.yhalfsize, width=1, fill="gray40", state="disabled")

    def draw_x_tick(self, x, ticklen):
        self.canvas.create_line(x, self.ymid-ticklen, x, self.ymid+ticklen, width=1, fill="gray30", state="disabled")
        self.canvas.create_line(x, self.ymid-self.yhalfsize, x, self.ymid-self.yhalfsize+ticklen, width=1, fill="gray30", state="disabled")
        self.canvas.create_line(x, self.ymid+self.yhalfsize, x, self.ymid+self.yhalfsize-ticklen, width=1, fill="gray30", state="disabled")

    def draw_y_line(self, y):
        self.canvas.create_line(self.xmid-self.xhalfsize, y, self.xmid+self.xhalfsize, y, width=1, fill="gray40", state="disabled")

    def draw_y_tick(self, y, ticklen):
        self.canvas.create_line(self.xmid-ticklen, y, self.xmid+ticklen, y, width=1, fill="gray30", state="disabled")
        self.canvas.create_line(self.xmid-self.xhalfsize, y, self.xmid-self.xhalfsize+ticklen, y, width=1, fill="gray30", state="disabled")
        self.canvas.create_line(self.xmid+self.xhalfsize, y, self.xmid+self.xhalfsize-ticklen, y, width=1, fill="gray30", state="disabled")

    def draw_grid(self, width, height):
        self.draw_x_line(self.xmid)
        self.draw_y_line(self.ymid)
        xticks = 5 * self.cfgdata['scope']['hdivs']
        yticks = 5 * self.cfgdata['scope']['vdivs']
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
