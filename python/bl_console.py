#! /usr/bin/env python3
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
from datetime import datetime

def clamp(value, low, high):
    return min(max(low, value), high)


class Console(ttk.Frame):
    '''
    line-oriented dumb terminal widget
     - displays incoming lines with optional line numbers and/or timestamps

    This class handles the display and user interface, not the serial port
    '''
    def __init__(self, parent, config, linenum_len=6, timestamp_len1=8, timestamp_len2=3, **kwargs):
        '''
        :param config: instance of AppConfig with config data
        :param linenum_len: length of line number field
        :param timestamp_len1: length of timestamp field before seconds decimal point
            (base format is yyyy-mm-ddThh:mm:ss.ffffff; 19 shows all, 8 shows time only, etc.)
        :param timestamp_len2: length of fractional second part of timestamp (3 = milliseconds)
        '''
        # Call the parent class (ttk.Frame) constructor
        super().__init__(parent, **kwargs)

        self.cfgdata = config.data

        # init line counter
        self.linecount = 1
        self.new_line = True

        self.linenum_len = clamp(linenum_len, 1, 10)
        self.timestamp_len1 = clamp(timestamp_len1, 2, 19)
        self.timestamp_len2 = clamp(timestamp_len2, 0, 6)
        if self.timestamp_len2 == 0 :
            # if no digits after the decimal we don't want to display the decimal either
            self.timestamp_len2 = -1
        # font for text display
        self.font = tkfont.Font(family=self.cfgdata['text']['font_family'],
                                 size=self.cfgdata['text']['font_size'], weight="normal")
        self.charwidth = self.font.measure('0')

         # text widget with scrollbars for main content
        self.text = tk.Text(self, undo=False, state='disabled', font=self.font)
        self.ys = ttk.Scrollbar(self, orient='vertical')
        self.xs = ttk.Scrollbar(self, orient='horizontal')

        # tags used to classify the text in the main widget
        self.text.tag_configure("rx_text", foreground='gray')
        self.text.tag_configure("tx_text", foreground='black')
        self.text.tag_configure("rx_linenum", foreground='red')
        self.text.tag_configure("tx_linenum", foreground='red')
        self.text.tag_configure("rx_timestamp", foreground='blue')
        self.text.tag_configure("tx_timestamp", foreground='blue')

        # connect the scrollbars
        self.text.config(yscrollcommand=self.ys.set)
        self.text.config(xscrollcommand=self.xs.set)
        self.ys.config(command = self.text.yview)
        self.xs.config(command = self.text.xview)

        # replace default copy handler
        self.text.bind('<Control-c>', self.copy_displayed)

        # control checkboxes
        self.checkframe = ttk.Frame(self)

        self.show_linenum = tk.BooleanVar(value=self.cfgdata['console']['show_linenum'])
        self.linenum_check = ttk.Checkbutton(self.checkframe, text='Line Numbers',
            command=self.show_changed, variable=self.show_linenum)
        self.show_timestamp = tk.BooleanVar(value=self.cfgdata['console']['show_timestamp'])
        self.timestamp_check = ttk.Checkbutton(self.checkframe, text='Timestamps',
            command=self.show_changed, variable=self.show_timestamp)
        self.wrap = tk.BooleanVar(value=self.cfgdata['console']['wrap_lines'])
        self.wrap_check = ttk.Checkbutton(self.checkframe, text='Wrap Long Lines',
            command=self.wrap_changed, variable=self.wrap)
        self.autoscroll = tk.BooleanVar(value=self.cfgdata['console']['autoscroll'])
        self.autoscroll_check = ttk.Checkbutton(self.checkframe, text='Autoscroll',
            command=self.scroll_changed, variable=self.autoscroll)
        self.show_rx = tk.BooleanVar(value=self.cfgdata['console']['show_rx_text'])
        self.rx_check = ttk.Checkbutton(self.checkframe, text='RX',
            command=self.show_changed, variable=self.show_rx)
        self.show_tx = tk.BooleanVar(value=self.cfgdata['console']['show_tx_text'])
        self.tx_check = ttk.Checkbutton(self.checkframe, text='TX',
            command=self.show_changed, variable=self.show_tx)

        # configure based on initial state of checkbox
        self.show_changed()
        self.wrap_changed()

        # geometry
        self.checkframe.grid_columnconfigure(0, weight=3)
        self.checkframe.grid_columnconfigure(1, weight=3)
        self.checkframe.grid_columnconfigure(2, weight=3)
        self.checkframe.grid_columnconfigure(3, weight=3)
        self.checkframe.grid_columnconfigure(4, weight=1)
        self.checkframe.grid_columnconfigure(5, weight=1)
        self.checkframe.grid_rowconfigure(0, weight=0)

        self.linenum_check.grid(row=0, column=0)
        self.timestamp_check.grid(row=0, column=1)
        self.wrap_check.grid(row=0, column=2)
        self.autoscroll_check.grid(row=0, column=3)
        self.rx_check.grid(row=0, column=4)
        self.tx_check.grid(row=0, column=5)

        self.checkframe.grid(row=0, column=0, columnspan=2, sticky='nsew')
        self.text.grid(row=1, column=0, sticky='nsew')
        self.ys.grid(row=1, column=1, sticky='nsew')
        self.xs.grid(row=2, column=0, sticky='nsew')

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

    @staticmethod
    def add_config_data(config):
        '''
        adds config fields needed by a Console object
        should be called before a Console is created

        :param config: config object to which fields are added
        '''
        config.data['console']={}
        config.data['console']['show_linenum']=True
        config.data['console']['show_timestamp']=True
        config.data['console']['show_rx_text']=True
        config.data['console']['show_tx_text']=True
        config.data['console']['wrap_lines']=False
        config.data['console']['autoscroll']=True

    def make_timestr(self, timestamp) :
        '''
        convert datetime object to string
         '''
        if timestamp == None:
            timestamp = datetime.now()
        timestr = timestamp.isoformat(timespec='microseconds')
        # decimal point in an isoformat time string is at index 19
        timestr = timestr[19-self.timestamp_len1:19+1+self.timestamp_len2]
        return timestr

    def append(self, content, timestamp, is_tx=False):
        '''
        add text to the display

        :param content: byte string to display
        :param timestamp: datetime object when last char in content was received
        '''
        timestr = self.make_timestr(timestamp)
        textstr = content.decode()
        if is_tx :
            rxtx = "tx_"
        else :
            rxtx = "rx_"
        self.text.configure(state='normal')
        if self.new_line :
            self.text.insert('end', f"{self.linecount:0{self.linenum_len}d}:", rxtx+"linenum" )
            self.text.insert('end', f"{timestr}:", rxtx+"timestamp" )
            self.new_line = False
        self.text.insert('end', textstr, rxtx+"text" )
        self.text.configure(state='disabled')
        if textstr[-1] == '\n' :
            self.linecount = self.linecount + 1
            self.new_line = True
        if self.autoscroll.get() :
            self.text.see(tk.END)


    def set_lmargin2(self):
        '''
        indent wrapped lines relative to base text
        '''
        lmargin = 1.5 # basic indent
        if self.show_linenum.get() :
            lmargin = lmargin + self.linenum_len + 1
        if self.show_timestamp.get() :
            lmargin = lmargin + self.timestamp_len1 + self.timestamp_len2 + 2
        lmargin = self.charwidth * lmargin
        for tag in self.text.tag_names() :
            if 'text' in tag :
                self.text.tag_configure(tag, lmargin2=lmargin)

    def wrap_changed(self):
        '''
        turns wrapping on or off based on checkbox
        '''
        wrap = self.wrap.get()
        if wrap:
            self.text.config(wrap='char')
        else:
            self.text.config(wrap='none')
        self.cfgdata['console']['wrap_lines'] = wrap

    def scroll_changed(self):
        self.cfgdata['console']['autoscroll'] = self.autoscroll.get()

    def show_changed(self):
        show_linenum = self.show_linenum.get()
        show_timestamp = self.show_timestamp.get()
        show_rx = self.show_rx.get()
        show_tx = self.show_tx.get()
        self.text.tag_configure("rx_text", elide=not (show_rx) )
        self.text.tag_configure("tx_text", elide=not (show_tx) )
        self.text.tag_configure("rx_linenum", elide=not (show_rx and show_linenum) )
        self.text.tag_configure("tx_linenum", elide=not (show_tx and show_linenum) )
        self.text.tag_configure("rx_timestamp", elide=not (show_rx and show_timestamp) )
        self.text.tag_configure("tx_timestamp", elide=not (show_tx and show_timestamp) )
        self.set_lmargin2()
        self.cfgdata['console']['show_timestamp'] = show_linenum
        self.cfgdata['console']['show_linenum'] = show_timestamp
        self.cfgdata['console']['show_rx_text'] = show_rx
        self.cfgdata['console']['show_tx_text'] = show_tx

    def copy_displayed(self):
        '''
        replaces default copy action; copies only displayed characters
        (allows user to copy text with or without line numbers & timestamps)
        '''
        ranges = self.text.tag_ranges('sel')
        if ranges:
            start = ranges[0]
            end = ranges[-1]
            curr_index = self.text.index(f"{start}+0 display chars")
            selected = ""
            while self.text.compare(curr_index, "<", end):
                selected = selected + self.text.get(curr_index)
                curr_index = self.text.index(f"{curr_index}+1 display chars")
            # clipboard needs access to root window
            toplevel = self.winfo_toplevel()
            toplevel.clipboard_clear()
            toplevel.clipboard_append(selected)
        return 'break'

