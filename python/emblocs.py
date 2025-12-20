#! /usr/bin/env python3

from tkinter import *
from tkinter import ttk
from datetime import datetime



class MyText(ttk.Frame):
    def __init__(self,master) -> None:
        pass

class MyWidget(ttk.Frame):
    def __init__(self, parent, **kwargs):
        # Call the parent class (ttk.Frame) constructor
        super().__init__(parent, **kwargs)

        self.linecount = 0

        # Create internal widgets, using 'self' as their parent
        self.text = Text(self, undo=False, state='disabled')
        self.ys = ttk.Scrollbar(self, orient='vertical')
        self.xs = ttk.Scrollbar(self, orient='horizontal')

        self.text.tag_configure("text", lmargin2=10)
        self.text.tag_configure("linenum", foreground='red')
        self.text.tag_configure("timestamp", foreground='blue')
       
        self.text.config(yscrollcommand=self.ys.set)
        self.text.config(xscrollcommand=self.xs.set)
        self.ys.config(command = self.text.yview)
        self.xs.config(command = self.text.xview)

        self.text.bind('<Control-c>', self.copy)

        # control buttons
        self.checkframe = ttk.Frame(self)

        self.show_linenum = BooleanVar(value=True)
        self.linenum_check = ttk.Checkbutton(self.checkframe, text='Line Numbers', 
    	    command=self.linenum_changed, variable=self.show_linenum)
        self.show_timestamp = BooleanVar(value=True)
        self.timestamp_check = ttk.Checkbutton(self.checkframe, text='Timestamps', 
    	    command=self.timestamp_changed, variable=self.show_timestamp)
        self.wrap = BooleanVar(value=False)
        self.wrap_check = ttk.Checkbutton(self.checkframe, text='Wrap Text', 
    	    command=self.wrap_changed, variable=self.wrap)

        self.linenum_changed()
        self.timestamp_changed()
        self.wrap_changed()

        # geometry
        self.checkframe.grid_columnconfigure(0, weight=1)
        self.checkframe.grid_columnconfigure(1, weight=1)
        self.checkframe.grid_columnconfigure(2, weight=1)
        self.checkframe.grid_rowconfigure(0, weight=0)

        self.linenum_check.grid(row=0, column=0)
        self.timestamp_check.grid(row=0, column=1)
        self.wrap_check.grid(row=0, column=2)

        self.checkframe.grid(row=0, column=0, columnspan=2, sticky='nsew')
        self.text.grid(row=1, column=0, sticky='nsew')
        self.ys.grid(row=1, column=1, sticky='nsew')
        self.xs.grid(row=2, column=0, sticky='nsew')
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

    def append(self, content):
        self.text.configure(state='normal')
        for line in content.split('\n'):
            now = datetime.now()
            timestr = now.isoformat(timespec='microseconds')
            timestr = timestr[11:24]
            self.linecount = self.linecount + 1
            self.text.insert('end', f"{self.linecount:7d}:", "linenum")
            self.text.insert('end', f"{timestr}:", "timestamp")
            self.text.insert('end', line + '\n', "text")
        self.text.configure(state='disabled')

    def linenum_changed(self):
        self.text.tag_configure("linenum", elide=not self.show_linenum.get())

    def timestamp_changed(self):
        self.text.tag_configure("timestamp", elide=not self.show_timestamp.get())

    def wrap_changed(self):
        if self.wrap.get():
            self.text.config(wrap='char')
            self.text.config(spacing1=3)
        else:
            self.text.config(wrap='none')
            self.text.config(spacing1=0)

    # default copy action gets all selected characters, even elided ones
    # this implementation grabs only displayed characters
    def copy(self, event):
        ranges = self.text.tag_ranges('sel')
        if ranges:
            start = ranges[0]
            end = ranges[-1]
            curr_index = self.text.index(f"{start}+0 display chars")
            selected = ""
            while self.text.compare(curr_index, "<", end):
                selected = selected + self.text.get(curr_index)
                curr_index = self.text.index(f"{curr_index}+1 display chars")
            root.clipboard_clear()
            root.clipboard_append(selected)
        return 'break'




root = Tk()

root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(0, weight=1)

thing = MyWidget(root)
thing.grid(row=0, column=0, sticky='nsew')

try:
    with open('test.txt', 'r') as f:
        content = f.read()
    print("file opened\n")
    thing.append(content)
except FileNotFoundError:
    print("Error: The file was not found.")


print("hello\n")

root.mainloop()

print("goodbye\n");

