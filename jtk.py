#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
An enhancement to Tkinter.
"""
import base64

import jex

if jex.isPython3():
    import tkinter as tk
    from tkinter import ttk
    import tkinter.messagebox as tkMessageBox
    import tkinter.filedialog as tkFileDialog
    import tkinter.font as tkFont
else:
    import Tkinter as tk
    import ttk
    import tkFileDialog
    import tkFont

import calendar
import datetime
import math

from PIL import Image, ImageSequence, ImageTk
from sys import platform

import json


curr_os = jex.PLATFORM.Darwin if platform.startswith('darwin') else jex.PLATFORM.Win

'''
It's a magic number.
But canvas paint everything from this coordinate, not zero!
I don't know why. Maybe someone can tell me.
'''
CANVAS_BIAS = 3


class CreateToolTip:
    """
    Gives a Tkinter widget a tooltip when mouse is hovering upon it.
    Usage:
      CreateToolTip(a_widget, 'some hint\nOther hint')
    """
    def __init__(self, widget, text):
        self._wait_time = 1000  # milliseconds
        self._widget = widget
        self._text = text
        self._widget.bind("<Enter>", lambda evt: self.schedule_())
        self._widget.bind("<Leave>", self.leave_)
        self._widget.bind("<ButtonPress>", self.leave_)
        self._job = None
        self._tip = None

    def leave_(self, event=None):
        self.unschedule_()
        self.hidetip_()

    def schedule_(self):
        self.unschedule_()
        self._job = self._widget.after(self._wait_time, self.showtip_)

    def unschedule_(self):
        if self._job is None:
            return
        self._widget.after_cancel(self._job)
        self._job = None

    def showtip_(self):
        self._tip = tk.Toplevel(self._widget)
        self._tip.wm_overrideredirect(True)  # remove window title bar
        label = tk.Label(self._tip, text=self._text, justify=tk.LEFT)
        label.pack(ipadx=5)
        x, y = self._widget.winfo_rootx(), self._widget.winfo_rooty()
        w, h = label.winfo_reqwidth(), label.winfo_reqheight()
        sw, sh = label.winfo_screenwidth(), label.winfo_screenheight()
        offset = 20
        if x + w + offset > sw:
            x -= w + offset*2
        if y + h + offset > sh:
            y -= h + offset*2
        self._tip.wm_geometry("+%d+%d" % (x+offset, y+offset))

    def hidetip_(self):
        if self._tip is None:
            return
        self._tip.destroy()
        self._tip = None


def MessageBubble(widget, text):
    tip = tk.Toplevel(widget)
    tip.wm_overrideredirect(True)
    label = tk.Label(tip, text=text, bg='yellow')
    label.pack(ipadx=5)
    x, y = widget.winfo_rootx(), widget.winfo_rooty()
    w, h = label.winfo_reqwidth(), label.winfo_reqheight()
    sw, sh = label.winfo_screenwidth(), label.winfo_screenheight()
    offset = 20
    if x + w + offset > sw:
        x -= w + offset*2
    if y + h + offset > sh:
        y -= h + offset*2
    tip.wm_geometry("+%d+%d" % (x+offset, y+offset))
    widget.after(2000, tip.destroy)


class MakePlaceHolder:
    """
    For tk.Entry, ttk.Combobox,
    add a place holder to input area to make it more noticeable.
    """
    _placeholder = '<Empty>'

    def __init__(self, w, placeholder=None):
        self._widget = w
        if len(w.get()) > 0:  # user assigned a predefined value
            self._placeholder = w.get()
        else:
            if placeholder is not None:
                self._placeholder = placeholder
            self.toggle_placeholder_(True)
        #
        w.bind('<FocusIn>', self.hide_placeholder_)
        w.bind('<FocusOut>', self.show_placeholder_)

    def toggle_placeholder_(self, display):
        if isinstance(self._widget, tk.Entry):
            if display:
                self._widget.insert(0, self._placeholder)
            else:
                self._widget.delete(0, tk.END)
        elif isinstance(self._widget, ttk.Combobox):
            if display:
                self._widget.set(self._placeholder)
            else:
                self._widget.set('')

    def hide_placeholder_(self, evt):
        if self._widget.get() == self._placeholder:
            self.toggle_placeholder_(False)

    def show_placeholder_(self, evt):
        if len(self._widget.get()) == 0:
            self.toggle_placeholder_(True)


class CalendarDlg(tk.Toplevel):
    """
    A modal dialog by which you can choose a date.
    @return a datetime.date object: self.date
    """
    YEAR_FROM = 2000  # Ignore why it starts here
    YEAR_TO = 2050    # I'm too old to use computer

    def __init__(self, parent, *a, **kw):
        title = kw.pop('title', 'Pick Up One Date')
        first_weekday = kw.pop('firstweekday', calendar.SUNDAY)
        self.date = kw.pop('date', datetime.date.today())
        self._calendar = calendar.TextCalendar(first_weekday)
        #
        tk.Toplevel.__init__(self, *a, **kw)
        self.title(title)
        self.transient(parent)  # when parent minimizes to an icon, it hides too.

        body = tk.Frame(self)
        self.body_(body)
        body.pack(padx=5, pady=5, expand=tk.YES, fill=tk.BOTH)
        body.bind('<Map>', self.min_size_)
        #
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.geometry("+%d+%d" % (parent.winfo_rootx()+50,
                                  parent.winfo_rooty()+50))
        self.bind('<Escape>', lambda evt: self.destroy())
        self.bind('<Left>', self.arrow_key_)
        self.bind('<Right>', self.arrow_key_)
        self.bind('<Up>', self.arrow_key_)
        self.bind('<Down>', self.arrow_key_)
        # move to front as a modal dialog
        self.lift()
        self.focus_force()
        self.grab_set()

    def show(self):
        self.wait_window(self)  # enter a local event loop until dialog is destroyed.

    def body_(self, master):
        frm = tk.Frame(master)
        frm.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        self._year_selected = tk.StringVar(value=str(self.date.year))
        tk.Spinbox(frm, from_=CalendarDlg.YEAR_FROM, to=CalendarDlg.YEAR_TO,
                   width=5, textvariable=self._year_selected).pack(side=tk.LEFT)
        self._month_selected = tk.StringVar(value=calendar.month_name[self.date.month])
        tk.OptionMenu(frm, self._month_selected, *calendar.month_name[1:]).pack(side=tk.LEFT)
        self._year_selected.trace('w', self.date_changed_)
        self._month_selected.trace('w', self.date_changed_)
        tk.Button(frm, text='Today', command=self.jump_today_).pack(side=tk.RIGHT)
        #
        # monthly calendar: draw 6 rows (weeks) on tree-view widget
        cols = self._calendar.formatweekheader(3).split()
        self._month_days = ttk.Treeview(master, show='headings',  # hide first icon column
                                        height=6, columns=cols,   # a month strides over 6 weeks at most
                                        selectmode='none')        # disable row-selection
        self._month_days.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        self._month_days.bind('<1>', self.on_day_click_)
        font = tkFont.Font()
        max_width = max(font.measure(col) for col in cols)
        for col in cols:
            self._month_days.column(col, width=max_width, minwidth=max_width, anchor=tk.CENTER)
            self._month_days.heading(col, text=col)
        self.month_weeks_ = [self._month_days.insert('', 'end', values='') for i in range(6)]
        self._canvas = tk.Canvas(self._month_days, background='#ecffc4')
        self._day_selected = self._canvas.create_text(0, 0, fill='#05640e', anchor=tk.CENTER)
        self._month_days.bind('<Configure>', self.auto_resize_)
        self.refresh_weeks_()

    def min_size_(self, evt):
        """
        @note automatically called to decide the min size of top-level dialog
        """
        w, h = self.geometry().split('x')
        h = h[:h.index('+')]
        self.minsize(w, h)

    def refresh_weeks_(self):
        self._canvas.place_forget()
        cal = self._calendar.monthdayscalendar(self.date.year, self.date.month)
        for idx, item in enumerate(self.month_weeks_):
            week = cal[idx] if idx < len(cal) else []
            fmt_week = [('%02d' % day) if day else '' for day in week]
            self._month_days.item(item, values=fmt_week)

    def date_changed_(self, name, index, mode):
        try:
            new_year = self._year_selected.get()
            new_year = int(new_year)
            if new_year < 1900:
                return
            new_month = self._month_selected.get()
            new_month = calendar.month_name[:].index(new_month)
            old_day = self._canvas.itemcget(self._day_selected, 'text')
            old_day = int(old_day)
            new_day = max(self._calendar.itermonthdays(new_year, new_month))
            new_day = min(old_day, new_day)
            new_date = datetime.date(new_year, new_month, new_day)
            if self.date != new_date:
                self.date = new_date
                self.refresh_weeks_()
                self.after(100, self.highlight_today_)
        except ValueError:
            return

    def on_day_click_(self, evt):
        w = evt.widget
        row = w.identify_row(evt.y)
        col = w.identify_column(evt.x)
        text = w.set(row, col)
        if text is '':
            return
        self.draw_highlight_(row, col, text)
        self.date = datetime.date(self.date.year, self.date.month, int(text))

    def auto_resize_(self, evt):
        if self._canvas.itemcget(self._day_selected, 'text') is '':
            self.after(100, self.highlight_today_)
            return
        x, y = self._canvas.coords(self._day_selected)
        row = self._month_days.identify_row(int(y)+self._canvas.winfo_y())
        col = self._month_days.identify_column(int(x) + self._canvas.winfo_x())
        if row is '' or col is '':
            return
        text = self._month_days.set(row, col)
        if text is '':
            return
        self.draw_highlight_(row, col, text)

    def highlight_today_(self):
        today = '%02d' % self.date.day
        for i in self.month_weeks_:
            values = self._month_days.item(i, 'values')
            if today in values:
                self.draw_highlight_(i, values.index(today), today)
                return

    def draw_highlight_(self, row, col, day):
        x, y, w, h = self._month_days.bbox(row, col)
        self._canvas.config(width=w, height=h)
        self._canvas.coords(self._day_selected, w/2, h/2)
        self._canvas.itemconfig(self._day_selected, text=day)
        self._canvas.place(x=x, y=y)

    def jump_today_(self):
        today = datetime.date.today()
        self._canvas.itemconfig(self._day_selected, text='%02d' % today.day)
        self._year_selected.set(today.year)
        self._month_selected.set(calendar.month_name[today.month])

    def arrow_key_(self, evt):
        try:
            year = int(self._year_selected.get())
            month = self._month_selected.get()
            month = calendar.month_name[:].index(month)
            if evt.keysym == 'Up':
                if year < CalendarDlg.YEAR_TO:
                    self._year_selected.set(str(year+1))
            elif evt.keysym == 'Down':
                if year > CalendarDlg.YEAR_FROM:
                    self._year_selected.set(str(year-1))
            elif evt.keysym == 'Left':
                if month > 1:
                    self._month_selected.set(calendar.month_name[month-1])
                elif year > CalendarDlg.YEAR_FROM:
                    self._month_selected.set(calendar.month_name[12])
                    self._year_selected.set(str(year-1))
            else:  # Right Arrow key
                if month < 12:
                    self._month_selected.set(calendar.month_name[month+1])
                elif year < CalendarDlg.YEAR_TO:
                    self._month_selected.set(calendar.month_name[1])
                    self._year_selected.set(str(year+1))
        except ValueError:
            pass


#-----------------------------
# A series of enhancements:  |
#       Tkinter Text         |
#                            V
class ModifiedMixin:
    """
    Tkinter Text has a method 'edit_modified' by which you can get/set 'Modified' state.
    But its firing mechanism has 2 features:
      1. Once fired, it won't fire again until manually call 'Text.edit_modified(False)'
      2. If you call 'Text.edit_modified(False)', it fires on that call.

    Therefore, another scheme comes out: fire only on content changed.

    To use this mixin:
      1. subclass from Tkinter.Text and the mixin, then write
      an __init__() method for the new class that calls __init__().

      2. Then override the been_modified() method to implement the behavior
      that you want to happen when the Text is modified.
    """

    def __init__(self):
        self.clear_modified_flag_()
        self.ignoreNextEvent = True # force to ignore 1st <<Modified>> event fired by below binding
        self.bind('<<Modified>>', self.event_fired_)  # this "binding" will fire a <<Modified>> event. What an ugly bug!

    def been_modified(self, event=None):
        """
        Override this method in your own class
        """
        pass

    def event_fired_(self, event=None):
        if self.ignoreNextEvent:
            if self.edit_modified():
                self.edit_modified(False)
            else:
                self.ignoreNextEvent = False
            return # ignore this event

        # normal <<Modified>> event
        self.been_modified(event)
        #
        # if no manual resetting, <<Modified>> event won't fire again
        self.clear_modified_flag_()

    def clear_modified_flag_(self):
        if self.edit_modified():
            self.edit_modified(False)
            self.ignoreNextEvent = True


class NotifiedText(tk.Text, ModifiedMixin):
    EVENT_MODIFIED = '<<Changed>>'
    EVENT_VIEW_CHG = '<<ViewChanged>>'

    def __init__(self, *a, **b):
        tk.Text.__init__(self, *a, **b)
        ModifiedMixin.__init__(self)
        self._event_listeners = {}
        #self._event_count = {}  # debug

    def add_listener(self, event, listener):
        """
        @param listener is tkInter widget, which support method .event_generate()
        """
        if event in self._event_listeners:
            self._event_listeners[event].append(listener)
        else:
            self._event_listeners[event] = [listener]
            # debug
            #self._event_count[event] = 0

    def notify_listener_(self, event):
        if event not in self._event_listeners:
            return
        for listener in self._event_listeners[event]:
            listener.event_generate(event, when='tail')
            # debug
            #print('Fire event (%s: %s)' % (event, self._event_count[event]))
            #self._event_count[event] += 1

    def been_modified(self, event=None):
        """
        will be called automatically by base ModifiedMixin.
        """
        self.notify_listener_(self.EVENT_MODIFIED)

    """
    When user is dragging scrollbar, it uses this method to adjust text view.
    But on MacOS, we don't need override it to send event.
    Because after view is adjusted, text will notify scrollbar to change its position.
    This behavior will also send <<ViewChanged>> event.
    """
    """
    def yview(self, *a):
        self.notify_listener_(self.EVENT_VIEW_CHG)
        return tk.Text.yview(self, *a)
    """

    def view_changed(self):
        """
        [MacOS] called when text view is changed
        """
        self.notify_listener_(self.EVENT_VIEW_CHG)


class NotifiedScrollBar(tk.Scrollbar):
    def __init__(self, *a, **kw):
        tk.Scrollbar.__init__(self, *a, **kw)
        self._host = kw['command'].__self__ if 'command' in kw else None

    def set(self, *args):
        """
        [MacOS] called when its host's view is changed. Arguments is new
        position for scrollbar.
        """
        tk.Scrollbar.set(self, *args)
        if self._host:
            self._host.view_changed()


class LineNumberBar(tk.Canvas):
    DIGIT_WIDTH = 0

    def __init__(self, master, text, **kwargs):
        """
        Display line number and bookmarks.
        @param text: is instance of NotifiedText
        """
        tk.Canvas.__init__(self, master, **kwargs)
        self._text = text
        self._old = (None, -1, -1)  # tuple(line_start, line_end, line_pos)
        self.binding_keys_()

        # text should notify canvas when event is fired
        self._text.add_listener(NotifiedText.EVENT_MODIFIED, self)
        self._text.add_listener(NotifiedText.EVENT_VIEW_CHG, self)

        # use a font to measure the width of canvas required to hold digits
        if LineNumberBar.DIGIT_WIDTH == 0:
            dummy = self.create_text(0, 0, text='0')
            font = tkFont.nametofont(self.itemcget(dummy, 'font'))
            self.delete(dummy)
            LineNumberBar.DIGIT_WIDTH = max(font.measure(str(i)) for i in range(10))

    def redraw_(self):
        positions = []
        idx = self._text.index("@0,0")  # coordinates --> 'line.char'
        start = int(idx.split(".")[0])
        info = self._text.dlineinfo(idx)
        while info is not None:
            positions.append(info[1])
            idx = self._text.index("%s+1line" % idx)
            info = self._text.dlineinfo(idx)
        end = int(idx.split(".")[0]) - 1
        # if no change, don't redraw
        if not self._old[0] is None and len(self._old[0]) == len(positions):
            if self._old[1:] == (start, end):
                if all(i==j for i,j in zip(self._old[0], positions)):
                    return
        self._old = (positions, start, end)
        self.delete(tk.ALL)
        width = self.resize_width_(end)
        for line_num, y in enumerate(positions, start=end-len(positions)+1):
            self.create_text(width / 2, y, anchor=tk.N, text=line_num)

    def binding_keys_(self):
        for event in ['<Configure>', NotifiedText.EVENT_MODIFIED, NotifiedText.EVENT_VIEW_CHG]:
            self.bind(event, self.on_changed_)

    def on_changed_(self, event):
        self.redraw_()
        # debug
        #print 'Canvas event. No:%s, Type:%s' % (event.serial, event.type)

    def resize_width_(self, line_num):
        """
        resize canvas width to properly hold digits
        @param line_num: last line number
        """
        required = LineNumberBar.DIGIT_WIDTH * (int(math.log10(line_num))+1)
        if required != int(self.cget('width')):
            self.configure(width=required)
        return self.winfo_reqwidth()
#                            ^
#          end here          |
# Tkinter Text enhancements  |
#-----------------------------


class TextOperationSet:
    def __init__(self, text):
        """
        @param text is Tkinter.Text instance
        """
        self._txt = text
        self._ops = {}
        self.default_bindings_()
        self.default_ops_()
        self.custom_ops_()

    def __getitem__(self, key):
        return self._ops[key]

    def default_bindings_(self):
        for i in ['Cut',            # Mod1-x, F2, Ctrl-Lock-X
                  'Copy',           # Mod1-c, F3, Ctrl-Lock-C (while Caps-Lock on, press Ctrl-Sft-c)
                  'Paste',          # Mod1-v, F4, Ctrl-Lock-V
                  'Undo',           # Mod1-z, Ctrl-Lock-Z
                  'Redo']:           # Mod1-y, Ctrl-Lock-Y
            # About parameters of lambda expression:
            # e for event (but not necessary, only placeholder), i for immediate parameter passing
            self._ops[i] = lambda e=None, i=i: self.complement_('<<%s>>' % i)
        #
        # bind capital key, too
        self._txt.bind('<Control-X>', self._ops['Cut'])
        self._txt.bind('<Control-x>', self._ops['Cut'])
        self._txt.bind('<Control-C>', self._ops['Copy'])
        self._txt.bind('<Control-c>', self._ops['Copy'])
        self._txt.bind('<Control-V>', self._ops['Paste'])
        self._txt.bind('<Control-v>', self._ops['Paste'])
        self._txt.bind('<Control-Z>', self._ops['Undo'])
        self._txt.bind('<Control-z>', self._ops['Undo'])
        self._txt.bind('<Control-Y>', self._ops['Redo'])
        self._txt.bind('<Control-y>', self._ops['Redo'])

    def complement_(self, op):
        self._txt.event_generate(op)
        self._txt.see(tk.INSERT)
        return 'break'

    def default_ops_(self):
        """
        Text widget has these builtin hot-key operations on Mac, but does not define virtual events.
        """
        operations = [('LineStart',    '<Control-a>', self.line_start),
                      ('LineEnd',      '<Control-e>', self.line_end),
                      ('NextLine',     '<Control-n>', self.next_line),
                      ('PrevLine',     '<Control-p>', self.prev_line),
                      ('NextChar',     '<Control-f>', self.next_char),
                      ('PrevChar',     '<Control-b>', self.prev_char),
                      ('FlipAdjChars', '<Control-t>', self.flip_adj_chars),
                      ('OpenNewLine',  '<Control-o>', self.open_new_line),
                      ('DelToLineEnd', '<Control-k>', self.del_to_line_end),
                      ('DelNextChar',  '<Control-d>', self.del_next_char),
                      ('DelPrevChar',  '<Control-h>', self.del_prev_char)]
        for evt, key, hdl in operations:
            self._txt.event_add('<<%s>>' % evt, key)
            self._ops[evt] = hdl

    def custom_ops_(self):
        bindings = ['<Command-a>', '<Control-a>']
        self._ops['SelectAll'] = self.select_all
        index = curr_os.value if jex.isPython3() else curr_os
        self._txt.bind(bindings[index], self.select_all)
        #
        bindings = ['<Command-Up>', '<Control-Up>']
        self._ops['Top'] = self.jump_top
        self._txt.bind(bindings[index], self.jump_top)
        #
        bindings = ['<Command-Down>', '<Control-Down>']
        self._ops['Bottom'] = self.jump_bottom
        self._txt.bind(bindings[index], self.jump_bottom)
        #
        bindings = ['<Command-Left>', '<Control-Left>']
        self._txt.bind(bindings[index], self._ops['LineStart'])

        bindings = ['<Command-Right>', '<Control-Right>']
        self._txt.bind(bindings[index], self._ops['LineEnd'])

    def line_start(self, evt=None):
        curr = self._txt.index(tk.INSERT)
        start = '%s linestart' % curr
        sel = self.selection_()
        if evt and (evt.state & 0x0001):  # shift pressed
            end = sel[1] if len(sel) else curr
            self._txt.tag_add(tk.SEL, start, end)
        elif len(sel) > 0:
            self._txt.tag_remove(tk.SEL, tk.SEL_FIRST, tk.SEL_LAST)
        #
        self._txt.mark_set(tk.INSERT, start)  # move cursor to line start
        self._txt.see(start)                  # scroll to line start
        return 'break'                        # avoid the extra 'key handler'

    def line_end(self, evt=None):
        curr = self._txt.index(tk.INSERT)
        end = '%s lineend' % curr
        sel = self.selection_()
        if evt and (evt.state & 0x0001):  # shift pressed
            start = sel[0] if len(sel) else curr
            self._txt.tag_add(tk.SEL, start, end)
        elif len(sel) > 0:
            self._txt.tag_remove(tk.SEL, tk.SEL_FIRST, tk.SEL_LAST)
        #
        self._txt.mark_set(tk.INSERT, end)  # move cursor to line end
        self._txt.see(end)                  # scroll to line end
        return 'break'                        # avoid the extra 'key handler'

    def next_line(self, evt=None):
        self._txt.mark_set(tk.INSERT, tk.INSERT + ' +1line')

    def prev_line(self, evt=None):
        self._txt.mark_set(tk.INSERT, tk.INSERT + ' -1line')

    def next_char(self, evt=None):
        self._txt.mark_set(tk.INSERT, tk.INSERT + ' +1c')

    def prev_char(self, evt=None):
        self._txt.mark_set(tk.INSERT, tk.INSERT + ' -1c')

    def flip_adj_chars(self, evt=None):
        pass

    def open_new_line(self, evt=None):
        self._txt.insert('%s lineend' % tk.INSERT, '\n')

    def del_to_line_end(self, evt=None):
        self._txt.delete(tk.INSERT, '%s lineend' % tk.INSERT)

    def del_next_char(self, evt=None):
        self._txt.delete(tk.INSERT)

    def del_prev_char(self, evt=None):
        self._txt.delete('%s-1c' % tk.INSERT)

    def select_all(self, evt=None):
        self._txt.tag_add(tk.SEL, '1.0', tk.END)

    def selection_(self):
        try:
            return self._txt.tag_ranges(tk.SEL)
        except tk.TclError:
            return None

    def jump_top(self, evt=None):
        curr = self._txt.index(tk.INSERT)
        sel = self.selection_()
        if evt and (evt.state & 0x0001):  # shift pressed
            end = sel[1] if len(sel) else curr
            self._txt.tag_add(tk.SEL, '1.0', end)
        elif len(sel) > 0:
            self._txt.tag_remove(tk.SEL, tk.SEL_FIRST, tk.SEL_LAST)
        #
        self._txt.mark_set(tk.INSERT, '1.0')  # move cursor to top
        self._txt.see('1.0')                  # scroll to top
        return 'break'                        # avoid the extra 'key handler'

    def jump_bottom(self, evt=None):
        curr = self._txt.index(tk.INSERT)
        sel = self.selection_()
        if evt and (evt.state & 0x0001):  # shift pressed
            start = sel[0] if len(sel) else curr
            self._txt.tag_add(tk.SEL, start, tk.END)
        elif len(sel) > 0:
            self._txt.tag_remove(tk.SEL, tk.SEL_FIRST, tk.SEL_LAST)
        #
        self._txt.mark_set(tk.INSERT, tk.END)  # move cursor to bottom
        self._txt.see(tk.END)                  # scroll to bottom
        return 'break'                        # avoid the extra 'key handler'


class TextEditor(tk.Frame):
    """
    widget layout:
    ---------------------
    | |               | |
    | |               | |
    |1| text widget   |2|
    | |               | |
    |_|_______________|_|
    1. The left area (No.1) is for line numbers.
    2. Area No.2 is a vertical scrollbar.
    """
    EVENT_CLEAN = '<<Clean>>'
    EVENT_DIRTY = '<<Dirty>>'

    def __init__(self, master, *a, **kw):
        core_options = kw.pop('core', {})
        has_ops = kw.pop('ops', False)
        tk.Frame.__init__(self, master, *a, **kw)
        #
        txt = NotifiedText(self, undo=True, autoseparators=True, maxundo=-1,
                           highlightbackground='gray', **core_options)
        lnb = LineNumberBar(self, txt)
        scb = NotifiedScrollBar(self, orient=tk.VERTICAL, command=txt.yview)
        txt.configure(yscrollcommand=scb.set)
        lnb.pack(side=tk.LEFT, fill=tk.Y, expand=tk.NO)   # pay ATTENTION to expand!
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=tk.YES)
        scb.pack(side=tk.RIGHT, fill=tk.Y, expand=tk.NO)  # pay ATTENTION to expand!
        #
        self._modified = False
        self._ops = TextOperationSet(txt) if has_ops else None
        self._txt = txt

    def core(self):
        return self._txt

    def modified(self):
        return self._modified

    def on_modified(self, evt=None):
        if not self._modified:
            self._modified = True
            self.notify_(TextEditor.EVENT_DIRTY)

    def on_saved(self):
        self._modified = False
        self.notify_(TextEditor.EVENT_CLEAN)

    def notify_(self, evt):
        self.event_generate(evt, when='tail')

    def monitor_change(self):
        self._txt.add_listener(NotifiedText.EVENT_MODIFIED, self)
        self.bind(NotifiedText.EVENT_MODIFIED, self.on_modified, True)

    def operation(self, index):
        return self._ops[index]


class TabBarTab:
    def __init__(self, caption, frame, has_close_button=False):
        self.caption = caption  # text of caption
        self.caption_id = 0     # text id in canvas. "0" means invalid id.
        self.shape_id = 0       # shape id in canvas. Shape can be rectangle or polygon.
        self.frame = frame
        # you can enable this feature
        self.close_btn = 0 if has_close_button else -1

    def has_close_button(self):
        return self.close_btn != -1

    def need_button(self):
        return self.close_btn == 0


class TabBarFrame(tk.Frame):
    BAR_H = 30         # width of whole tab-bar
    TAB_W = 120        # width of tab-button
    TAB_H = BAR_H - 8  # height of tab-button. "8" is a magic number.
    CLOSE_W = 25       # width fo "close" button
    MARGIN = 3         # margin to borders
    FOOTER_H = 7       # height of white ribbon at bottom
    PADDING = 8        # left/right padding for "X" (close button)s
    text_font = None

    EVENT_TAB_PLACEMENT = '<<TabBarPlacement>>'
    EVENT_TAB_SWITCH = '<<TabBarSwitch>>'

    def __init__(self, master=None, *a, **kw):
        self.has_exit = kw.pop('close', False)
        self.TAB_W = kw.pop('width', 120)
        tk.Frame.__init__(self, master, *a, **kw)
        self.tabs = []
        self.active = None
        self.bar = tk.Canvas(self, height=TabBarFrame.BAR_H)
        self.bar.pack(side=tk.TOP, anchor=tk.W, fill=tk.X, expand=tk.NO)
        self.bar.bind('<ButtonPress-1>', self.on_clicked)
        #
        if TabBarFrame.text_font is None:
            TabBarFrame.text_font = tkFont.Font()
        #
        self.bind('<Map>', self.on_widget_placed)        # event: widget placement
        self.bind('<Configure>', self.on_resize)  # event: resize

    def on_widget_placed(self, evt):
        self.switch_tab(self.active)
        self.event_generate(TabBarFrame.EVENT_TAB_PLACEMENT, when='tail')

    def on_resize(self, evt):
        if self.active is None:
            if len(self.tabs) > 0 and self.tabs[0].shape_id == 0:
                self.switch_tab(self.tabs[0].frame)
        else:
            current_active_frame = self.active
            self.active = None  # clear it to force redrawing of active tab
            self.switch_tab(current_active_frame)

    def add(self, frame, caption):
        """
        @param frame is an instance of tk.Frame class
        """
        frame.pack_forget()  # hide on init
        self.tabs.append(TabBarTab(caption, frame, self.has_exit))
        if len(self.tabs) == 1:
            self.event_generate('<Map>')
        else:
            self.draw_tab(len(self.tabs)-1, False)

    def remove(self, frame):
        """
        @param frame is tk.Frame instance
        @param caption is str instance
        """
        index, tab = self.tab_by_frame(frame)
        #
        for i, t in enumerate(self.tabs[index+1:]):
            if t.frame == self.active:
                self.draw_tab(i, True)
            else:
                self.bar.move(t.shape_id, -self.TAB_W, 0)
                self.bar.move(t.caption_id, -self.TAB_W, 0)
                self.bar.move(t.close_btn, -self.TAB_W, 0)
        #
        self.bar.delete(tab.caption_id, tab.shape_id, tab.close_btn)
        self.tabs.remove(tab)
        frame.pack_forget()
        #
        if frame == self.active:
            self.active = None
            self.switch_tab()
            self.event_generate(TabBarFrame.EVENT_TAB_SWITCH, when='tail')

    def tab_by_frame(self, frame):
        """
        @return tuple(index, tab)
        """
        for i, t in enumerate(self.tabs):
            if t.frame == frame:
                return i, t
        raise Exception("The specified frame doesn't exist.")

    def switch_tab(self, frame=None):
        """
        @param frame is tk.Frame instance
        """
        if frame is None:
            if len(self.tabs) > 0:
                frame = self.tabs[-1].frame
            else:
                return

        # draw previous active as grey rectangle
        if self.active:
            if self.active == frame:
                return
            index, _ = self.tab_by_frame(self.active)
            self.draw_tab(index, False)
            self.active.pack_forget()
        frame.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)
        self.active = frame
        # draw current active as white button
        index, _ = self.tab_by_frame(frame)
        self.draw_tab(index, True)

    def on_clicked(self, evt):
        clicked = self.bar.find_closest(evt.x, evt.y)
        for t in self.tabs:
            shapes = [t.caption_id, t.shape_id]
            if any(i in shapes for i in clicked):
                self.switch_tab(t.frame)
                self.event_generate(TabBarFrame.EVENT_TAB_SWITCH, when='tail')
                return

    def draw_tab(self, index, is_active):
        # draw shape
        tab = self.tabs[index]
        self.bar.delete(tab.shape_id)  # delete old shape
        if is_active:
            # create new shape
            if index == 0:
                x0 = TabBarFrame.MARGIN
                y0 = TabBarFrame.MARGIN
                points = [(x0, y0)]      # point 1 (top-left corner)
                x0 += self.TAB_W
                points.append((x0, y0))  # point 2
                y0 += TabBarFrame.TAB_H
                points.append((x0, y0))  # point 3
                x0 = self.winfo_width() - TabBarFrame.MARGIN - 1  # can't be used in __init__()
                points.append((x0, y0))  # point 4
                y0 += TabBarFrame.FOOTER_H
                points.append((x0, y0))  # point 5
                x0 = TabBarFrame.MARGIN
                points.append((x0, y0))  # point 6
                tab.shape_id = self.bar.create_polygon(*points, outline='black', fill='')
            else:
                x0 = TabBarFrame.MARGIN + index * self.TAB_W
                y0 = TabBarFrame.MARGIN
                points = [(x0, y0)]      # point 1 (top-left corner)
                x0 += self.TAB_W
                points.append((x0, y0))  # point 2
                y0 += TabBarFrame.TAB_H
                points.append((x0, y0))  # point
                x0 = self.winfo_width() - TabBarFrame.MARGIN - 1
                points.append((x0, y0))  # point
                y0 += TabBarFrame.FOOTER_H
                points.append((x0, y0))  # point
                x0 = TabBarFrame.MARGIN
                points.append((x0, y0))  # point
                y0 -= TabBarFrame.FOOTER_H
                points.append((x0, y0))  # point
                x0 = TabBarFrame.MARGIN + index * self.TAB_W
                points.append((x0, y0))  # point
                tab.shape_id = self.bar.create_polygon(*points, outline='black', fill='')
        else:
            x0 = TabBarFrame.MARGIN + index * self.TAB_W
            y0 = TabBarFrame.MARGIN
            x1 = x0 + self.TAB_W
            y1 = y0 + TabBarFrame.TAB_H
            tab.shape_id = self.bar.create_rectangle(x0, y0, x1, y1, fill='grey')
        # draw text
        if tab.caption_id == 0:
            btn_width = self.TAB_W - TabBarFrame.PADDING * 2
            if tab.has_close_button():
                btn_width -= TabBarFrame.CLOSE_W
            req_width = TabBarFrame.text_font.measure(tab.caption)
            x = TabBarFrame.MARGIN + index * self.TAB_W
            y = TabBarFrame.MARGIN
            center_pos = (x+btn_width/2+TabBarFrame.PADDING, y+TabBarFrame.TAB_H/2)
            if req_width > btn_width:
                caption = '%s...' % self.sub_str_by_width(tab.caption, btn_width)
                tab.caption_id = self.bar.create_text(*center_pos, text=caption)
                self.enable_tip(tab)
            else:
                tab.caption_id = self.bar.create_text(*center_pos, text=tab.caption)
        else:
            self.bar.tag_lower(tab.shape_id, tab.caption_id)
        # draw close button
        if tab.need_button():
            x = TabBarFrame.MARGIN + (index+1) * self.TAB_W
            y = TabBarFrame.MARGIN
            center_pos = (x-TabBarFrame.CLOSE_W/2, y+TabBarFrame.TAB_H/2)
            tab.close_btn = self.bar.create_text(*center_pos, text='X')
            self.bar.tag_bind(tab.close_btn, '<ButtonPress>', lambda e: self.remove(tab.frame))

    def sub_str_by_width(self, text, width):
        width -= self.text_font.measure('...')  # subtract "..." in advance
        for i in range(len(text), 0, -1):
            w = self.text_font.measure(text[:i])
            if width > w:
                return text[:i]
        return ''

    def enable_tip(self, tab):
        self.tip_wnd = None
        def show_tip(evt):
            self.tip_wnd = tk.Toplevel(self.bar)
            self.tip_wnd.wm_overrideredirect(True)  # remove window title bar
            label = tk.Label(self.tip_wnd, text=tab.caption, justify=tk.LEFT)
            label.pack(ipadx=5)
            x, y = evt.x_root, evt.y_root
            w, h = label.winfo_reqwidth(), label.winfo_reqheight()
            sw, sh = label.winfo_screenwidth(), label.winfo_screenheight()
            offset = 20
            if x + w + offset > sw:  # if reach beyond the right border
                x -= w + offset*2    # place tip to the left of widget
            if y + h + offset > sh:  # if reach beyond the bottom border
                y -= h + offset*2    # place tip to the top of widget
            self.tip_wnd.wm_geometry("+%d+%d" % (x+offset, y+offset))
        def hide_tip(evt):
            if self.tip_wnd:
                self.tip_wnd.destroy()
        self.bar.tag_bind(tab.caption_id, "<Enter>", show_tip)
        self.bar.tag_bind(tab.caption_id, "<Leave>", hide_tip)

    def count(self):
        return len(self.tabs)


class MultiTabEditor(TabBarFrame):
    def __init__(self, master, *a, **kw):
        self._font = kw.pop('font', None)
        TabBarFrame.__init__(self, master, *a, **kw)

    def add(self, editor, caption):
        """
        Do NOT use this method!
        It's used internally through overriding.
        Use below new_editor instead.
        """
        TabBarFrame.add(self, editor, caption)
        #
        editor.bind(TextEditor.EVENT_CLEAN, self.event_caption_)
        editor.bind(TextEditor.EVENT_DIRTY, self.event_caption_)

    def exists(self, caption):
        return any(t.caption == caption for t in self.tabs)

    def set_caption(self, editor, caption):
        index, tab = self.tab_by_frame(editor)
        assert isinstance(tab, TabBarTab)
        tab.caption = caption
        self.refresh_caption_(tab, editor.modified())

    def get_caption(self, editor):
        index, tab = self.tab_by_frame(editor)
        return tab.caption

    def refresh_caption_(self, tab, modified):
        if modified:
            caption = '* %s' % tab.caption
        else:
            caption = tab.caption
        #
        btn_width = self.TAB_W - TabBarFrame.PADDING * 2
        if tab.has_close_button():
            btn_width -= TabBarFrame.CLOSE_W
        req_width = TabBarFrame.text_font.measure(caption)
        if req_width > btn_width:
            caption = '%s...' % self.sub_str_by_width(caption, btn_width)
            self.enable_tip(tab)
        self.bar.itemconfig(tab.caption_id, text=caption)

    def event_caption_(self, evt):
        editor = evt.widget
        index, tab = self.tab_by_frame(editor)
        self.refresh_caption_(tab, editor.modified())

    def new_editor(self, caption):
        number = 1
        new_name = caption
        while self.exists(new_name):
            new_name = '%s_%d' % (caption, number)
            number += 1
        #
        options = {'ops': True}
        text = {'width': 0, 'height': 0}  # avoid Text auto-resizing when change font.
        if not self._font is None:
            text['font'] = self._font
        options['core'] = text
        editor = TextEditor(self, **options)
        self.add(editor, new_name)
        return editor

    def iter_tabs(self):
        """
        easier than iterator protocol
        """
        for t in self.tabs:
            yield t.frame

    def close_all(self):
        frames = [i for i in self.iter_tabs()]
        #map(lambda i: self.remove(i), frames)
        for i in frames:
            self.remove(i)

    def set_active(self, tab):
        self.switch_tab(tab)
        self.event_generate(TabBarFrame.EVENT_TAB_SWITCH, when='tail')


class ModalDialog(tk.Toplevel):
    """
    modal dialog should inherit from this class and override:
    1. body(): required: place your widgets
    2. apply(): required: calculate returning value
    3. buttonbox(): optional: omit it if you like standard buttons (OK and cancel)
    4. validate(): optional: you may need to check if input is valid.

    Dialog support keyword argument: title=...
    Place your widgets on method body()
    Get return value from method apply()
    """
    def __init__(self, parent, *a, **kw):
        title = kw.pop('title', None)

        tk.Toplevel.__init__(self, parent, *a, **kw)
        self.transient(parent)  # when parent minimizes to an icon, it hides too.

        if title:  # dialog title
            self.title(title)

        self.parent = parent
        self.result = None

        body = tk.Frame(self)
        self.initial_focus = self.body(body)
        body.pack(padx=5, pady=5, expand=tk.YES, fill=tk.BOTH)
        self.buttonbox()

        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.geometry("+%d+%d" % (parent.winfo_rootx()+50,
                                  parent.winfo_rooty()+50))

        if not self.initial_focus:
            self.initial_focus = self
        self.initial_focus.focus_set()

        self.lift()
        self.focus_force()
        self.grab_set()
        self.grab_release()

    def show(self):
        """
        enter a local event loop until dialog is destroyed.
        """
        self.wait_window(self)

    #
    # construction hooks

    def body(self, master):
        """
        Create dialog body.
        @param master: passed-in argument
        @return widget that should have initial focus.
        @note: must be overridden
        """
        return None

    def buttonbox(self):
        """
        Add standard button box (OK and cancel).
        @note: Override if you don't want the standard buttons
        """
        box = tk.Frame(self)

        w = tk.Button(box, text="OK", width=10, command=self.ok, default=tk.ACTIVE)
        w.pack(side=tk.LEFT, padx=5, pady=5)
        w = tk.Button(box, text="Cancel", width=10, command=self.cancel)
        w.pack(side=tk.LEFT, padx=5, pady=5)

        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)

        box.pack()
        return box

    #
    # standard button semantics

    def ok(self, event=None):
        if not self.validate():
            if self.initial_focus:
                self.initial_focus.focus_set()
            return

        self.withdraw()
        self.update_idletasks()

        self.apply()
        self.cancel()

    def cancel(self, event=None):
        self.parent.focus_set()
        self.destroy()

    #
    # command hooks

    def validate(self):
        """
        @note: override if needed
        """
        return True

    def apply(self):
        """
        @note: must be overridden
        """
        pass


class SearchBar(tk.Frame):
    HIT = 'sb.hit'
    CUR = 'sb.cur'
    """
    Incremental Search (searching when typing pattern).
    """

    def __init__(self, master=None, *a, **kw):
        tk.Frame.__init__(self, master, *a, bg='gray', **kw)
        #
        frm = tk.Frame(self)
        self._pattern = tk.StringVar()
        self._pattern.trace('w', lambda name, index, mode: self.keyword_changed_())
        e = tk.Entry(frm, textvariable=self._pattern)
        e.pack(side=tk.LEFT)
        e.bind('<Return>', self.force_search_)
        btn = tk.Button(frm, text=u'\u2191', command=self.search_backwards_)
        btn.pack(side=tk.LEFT)
        self._btn_back = btn
        btn = tk.Button(frm, text=u'\u2193', command=self.search_forwards_)
        btn.pack(side=tk.LEFT)
        self._btn_next = btn
        self._case = tk.IntVar()
        tk.Checkbutton(frm, variable=self._case, text='Match Case').pack(side=tk.LEFT)
        self._regex = tk.IntVar()
        tk.Checkbutton(frm, variable=self._regex, text='Regex').pack(side=tk.LEFT)
        self._loop = tk.IntVar(value=0)
        tk.Checkbutton(frm, variable=self._loop, text='Loop').pack(side=tk.LEFT)
        #
        tk.Button(frm, text='R', command=self.toggle_replace_).pack(side=tk.RIGHT)
        self._progress = tk.StringVar()
        tk.Label(frm, textvariable=self._progress).pack(side=tk.RIGHT)
        frm.pack(side=tk.TOP, fill=tk.X)
        #
        frm = tk.Frame(self)
        self._substitution = tk.StringVar()
        tk.Entry(frm, textvariable=self._substitution).pack(side=tk.LEFT)
        tk.Button(frm, text='Replace', command=self.replace_next_).pack(side=tk.LEFT)
        btn = tk.Button(frm, text='Replace All', command=self.replace_all_)
        btn.pack(side=tk.LEFT)
        self._btn_repl = btn
        self._replace_frm = frm
        #
        self._count = tk.IntVar()
        self._txt = None
        self._last = None  # a tuple (start, end)

    def search_backwards_(self):
        pos = self._txt.tag_prevrange(SearchBar.HIT, tk.INSERT)
        if len(pos) > 0:
            self._txt.mark_set(tk.INSERT, pos[0])
            self._txt.see(pos[0])
            self.highlight_current_(pos)
        elif len(self._txt.tag_nextrange(SearchBar.HIT, tk.INSERT)) == 0:
            MessageBubble(self._btn_back, 'No more matching backwards.')
        elif self._loop.get():
            self._txt.mark_set(tk.INSERT, tk.END)
            self.search_backwards_()
        else:
            MessageBubble(self._btn_back, 'No more matching backwards.')

    def search_forwards_(self):
        pos = self._txt.tag_nextrange(SearchBar.HIT, tk.INSERT)
        if len(pos) > 0:
            self._txt.mark_set(tk.INSERT, pos[0])
            self._txt.see(pos[0])
            self.highlight_current_(pos)
        elif len(self._txt.tag_prevrange(SearchBar.HIT, tk.INSERT)) == 0:
            MessageBubble(self._btn_next, 'No more matching forwards.')
        elif self._loop.get():
            self._txt.mark_set(tk.INSERT, '1.0')
            self.search_forwards_()
        else:
            MessageBubble(self._btn_next, 'No more matching forwards.')

    def attach(self, text, replace=0):
        """
        @note:
        when replace = 1, below decisions
           if replace is True  <-- not hit
           if replace          <-- hit
        are different.
        """
        self._txt = text
        self._txt.tag_config(SearchBar.HIT, background='yellow')
        self._txt.tag_config(SearchBar.CUR, background='sky blue')
        # automatic extract selection as keyword
        sel = text.tag_ranges(tk.SEL)
        if len(sel) > 0:
            self._pattern.set(text.get(sel[0], sel[1]))
        # automatic search if pattern isn't empty
        if self._pattern.get() != '':
            self.keyword_changed_()
        if replace and not self._replace_frm.winfo_ismapped():
            self._replace_frm.pack(side=tk.TOP, fill=tk.X)

    def detach(self):
        self._txt.tag_delete(SearchBar.HIT)
        self._txt.tag_delete(SearchBar.CUR)
        self._txt = None
        self._last = None

    def get_options_(self):
        options = {'count': self._count}
        # 1. match case
        if self._case.get():
            options['nocase'] = tk.NO
        else:
            options['nocase'] = tk.YES
        # 2. regular expression
        if self._regex.get():
            options['regexp'] = True
        else:
            options['exact'] = True
        return options

    def keyword_changed_(self):
        try:
            # remove old matches at first
            self._txt.tag_remove(SearchBar.HIT, '1.0', tk.END)
            # then launch a new search
            keyword = self._pattern.get()
            if keyword == '':
                raise Exception('no pattern provided')
            options = self.get_options_()
            pos = '1.0'
            index = self._txt.search(keyword, pos, forwards=True, **options)
            if index == '':
                raise Exception('no matching found!')
            while self._txt.compare(pos, '<', index):
                end = '%s+%dc' %(index, self._count.get())
                self._txt.tag_add(SearchBar.HIT, index, end)
                pos = end
                index = self._txt.search(keyword, pos, forwards=True, **options)
                if index == '':
                    raise Exception('never happen on Mac, what about Windows?')
        except:
            pass
        finally:
            items = len(self._txt.tag_ranges(SearchBar.HIT)) / 2
            if items > 0:
                self._progress.set('%d found' % items)
                self.see_first_match_()
            else:
                self._progress.set('')

    def toggle_replace_(self):
        if self._replace_frm.winfo_ismapped():
            self._replace_frm.pack_forget()
        else:
            self._replace_frm.pack(side=tk.TOP, fill=tk.X)

    def replace_next_(self):
        keyword = self._pattern.get()
        substitution = self._substitution.get()
        if keyword == substitution:
            return
        self.reset_current_()
        pos = self._txt.tag_nextrange(SearchBar.HIT, tk.INSERT)
        if len(pos) > 0:
            self._txt.mark_set(tk.INSERT, pos[1])
            self._txt.see(pos[0])
            self._txt.delete(pos[0], pos[1])
            self._txt.insert(pos[0], substitution)
        elif len(self._txt.tag_prevrange(SearchBar.HIT, tk.END)) == 0:
            MessageBubble(self._btn_repl, 'No more matching')
        elif self._loop.get():
            self._txt.mark_set(tk.INSERT, '1.0')
            self.replace_next_()
        else:
            MessageBubble(self._btn_repl, 'No more matching')

    def replace_all_(self):
        keyword = self._pattern.get()
        substitution = self._substitution.get()
        if keyword == substitution:
            return
        self.reset_current_()
        pos = self._txt.tag_nextrange(SearchBar.HIT, '1.0')
        while len(pos) > 0:
            self._txt.delete(pos[0], pos[1])
            self._txt.insert(pos[0], substitution)
            pos = self._txt.tag_nextrange(SearchBar.HIT, pos[0])
        MessageBubble(self._btn_repl, 'Substitution finished')

    def force_search_(self, evt=None):
        self.keyword_changed_()
        return 'break'

    def see_first_match_(self):
        pos = self._txt.tag_nextrange(SearchBar.HIT, tk.INSERT)
        if len(pos) == 0:
            pos = self._txt.tag_nextrange(SearchBar.HIT, '1.0')
        self._txt.see(pos[0])

    def highlight_current_(self, pos):
        self._txt.tag_remove(SearchBar.HIT, *pos)
        self._txt.tag_add(SearchBar.CUR, *pos)
        if not self._last is None:
            self._txt.tag_remove(SearchBar.CUR, *self._last)
            self._txt.tag_add(SearchBar.HIT, *self._last)
        self._last = pos

    def reset_current_(self):
        if not self._last is None:
            self._txt.tag_remove(SearchBar.CUR, *self._last)
            self._txt.tag_add(SearchBar.HIT, *self._last)
            self._last = None


class StorageMixin:
    """
    @note: a pure interface for the widget that can be embedded in tk.Text.
    """
    def output(self):
        return None


class ImageBox(tk.Canvas, StorageMixin):
    def __init__(self, master, *a, **kw):
        """
        keyword arguments:
          image: file object. Required.
          ext: str, filename extension. Required.
          scale: integer, 0~100. Optional. 100 is default value.
        @note: keep file object alive while ImageBox alive except you don't use 'export_to_file' method
        """
        self._bak = kw.pop('image')
        self._ext = kw.pop('ext')
        self._src = Image.open(self._bak)
        self._dst = None  # PhotoImage reference to keep it alive on widget
        self._iid = 0     # image ID on canvas
        self._info = tk.StringVar()  # image info like WxH, format and so on
        self._scale = tk.IntVar(value=kw.pop('scale', 100))
        self._scb = None  # trace-variable callback 'scale'
        tk.Canvas.__init__(self, master, *a, **kw)
        #
        self.bind('<Map>', self.adjust_size_)
        self.bind('<Enter>', self.hud_on_)
        self.bind('<Leave>', self.hud_off_)
        self.bind('<MouseWheel>', self.on_scroll_)  # tk.Text need it to scroll across canvas.
        self.bind('<Double-Button-1>', self.serialize_to_clipboard)
        # For GIF
        self._gif_task = None
        self._gif_buff = None
        self._gif_curr = -1
        self._gif_dura = 0
        if self._src.format == 'GIF':
            self._gif_curr = 0
            self._gif_buff = ImageSequence.Iterator(self._src)
            self._gif_dura = min(self._src.info['duration'], 200)
            self.bind('<1>', self.toggle_)
        #
        self._hudw = tk.Frame(self, bd=1, relief=tk.RAISED)
        self._hudw.pack()
        row1 = tk.Frame(self._hudw)
        row1.pack(side=tk.TOP, anchor=tk.W)
        tk.Label(row1, textvariable=self._info).pack(side=tk.LEFT)
        if self.is_gif():
            self._loop = tk.IntVar(value=self._src.info.get('loop', 0))
            tk.Checkbutton(row1, text='loop', variable=self._loop).pack(side=tk.LEFT)
        row2 = tk.Frame(self._hudw)
        row2.pack(side=tk.TOP)
        tk.Scale(row2, orient=tk.HORIZONTAL, variable=self._scale, from_=1).pack(side=tk.LEFT)
        tk.Button(row2, text='Export', command=self.export_to_file).pack(side=tk.LEFT, anchor=tk.S)
        self._hud = self.create_window(CANVAS_BIAS, CANVAS_BIAS, anchor=tk.NW, window=self._hudw, state=tk.HIDDEN)
        #
        self.display_()

    def is_gif(self):
        return self._gif_curr > -1

    def resize_(self):
        if self._gif_task is not None:  # GIF is playing
            self.after_cancel(self._gif_task)
            self._gif_task = None
        self.after(100, self.display_)
        self.on_modified_()

    def toggle_(self, evt):
        if not self.is_gif():
            return
        if self._gif_task is not None:
            self.after_cancel(self._gif_task)
            self._gif_task = None
        else:
            self._gif_task = self.after(self._gif_dura, self.display_)

    def display_(self, evt=None):
        scale = self._scale.get()
        if jex.isPython3():
            new_w, new_h = self._src.width*scale//100, self._src.height*scale//100
        else:
            new_w, new_h = self._src.width*scale/100, self._src.height*scale/100
        # resize canvas to accommodate image
        if self._dst is None:
            self.config(width=new_w, height=new_h)
        elif self._dst.width() != new_w:
            # impose a restriction upon canvas to avoid it's too small.
            canvas_w = max(new_w, self._hudw.winfo_width())
            if self.winfo_width() != canvas_w+CANVAS_BIAS*2:
                canvas_h = int(self._src.height * canvas_w / self._src.width)
                self.config(width=canvas_w, height=canvas_h)
        # display image properties
        ifo = [self._src.format, '%dx%d' % (self._src.width, self._src.height)]
        if self.is_gif():
            ifo.append('%d/%d' % (self._gif_curr+1, self._src.n_frames))
        self._info.set(', '.join(ifo))
        # display image and schedule next frame if loop is on
        if self.is_gif():
            src = self._gif_buff[self._gif_curr]
            if self._gif_task is not None:
                self._gif_curr = (self._gif_curr+1) % self._src.n_frames
                if self._gif_curr == 0 and self._loop.get() == 0:
                    self._gif_task = None
                else:
                    self._gif_task = self.after(self._gif_dura, self.display_)
        else:
            src = self._src
        src = src.resize((new_w, new_h))
        # [bug-fix] Mac tkinter Canvas doesn't support RGBA image.
        if 'A' in Image.getmodebandnames(src.mode) and jex.is_macos():
            bg_color = self.winfo_rgb(self.cget('background'))
            bg_color = tuple([i * 255 / 65535 for i in bg_color])
            bg_image = Image.new('RGB', src.size, color=bg_color)
            bg_image.paste(src, mask=src)
            src = bg_image
        self._dst = ImageTk.PhotoImage(image=src)
        if self._iid == 0:
            self._iid = self.create_image(CANVAS_BIAS, CANVAS_BIAS, anchor=tk.NW, image=self._dst)
        else:
            self.itemconfig(self._iid, image=self._dst)

    def hud_on_(self, evt):
        self.itemconfig(self._hud, state=tk.NORMAL)
        self._scb = self._scale.trace('w', lambda n, i, m: self.resize_())

    def hud_off_(self, evt):
        self.itemconfig(self._hud, state=tk.HIDDEN)
        self._scale.trace_vdelete('w', self._scb)
        self._scb = None

    def export_to_file(self):
        filename = tkFileDialog.asksaveasfilename(defaultextension=self._ext)
        if filename == '':
            return
        with open(filename, 'wb') as fo:
            self._bak.seek(0)
            fo.write(self._bak.read())

    def output(self):
        self._bak.seek(0)
        return self._bak.read(), self._scale.get(), self._ext

    def on_scroll_(self, evt):
        """
        @note:
          delta is the scrolling distance
          state is direction: horizontal(1) or vertical(0)
          On Mac, tk.Text supports vertical and horizontal scroll by itself.
          Therefore, it's enough for tk.Canvas to only pass event info.
        """
        self.master.event_generate('<MouseWheel>', delta=evt.delta, state=evt.state)

    def on_modified_(self):
        """
        notify the TextEditor that it may wants a saving.
        """
        w = self.master.master
        if isinstance(w, TextEditor):
            w.on_modified()

    def adjust_size_(self, evt):
        min_width = self._hudw.winfo_reqwidth()
        if self.winfo_width() < min_width+CANVAS_BIAS*2:
            min_height = int(self._src.height * min_width / self._src.width)
            self.config(width=min_width, height=min_height)

    def serialize_to_clipboard(self, evt=None):
        self._bak.seek(0)
        content = self._bak.read()
        text = base64.urlsafe_b64encode(content).decode('utf8')
        serialized = json.dumps({'jxd_bitty': {'format': 'image', 'data': text, 'ext': self._ext}})
        self.clipboard_clear()
        self.clipboard_append(serialized)


class TextTableBox(tk.Canvas, StorageMixin):
    class Cell:
        def __init__(self, grid_index, text, row_span=1, col_span=1):
            self.grid = grid_index
            self.text = text
            self.rows = row_span
            self.cols = col_span
            self.rid = 0
            self.tid = 0

        def set_id(self, rect, text):
            self.rid = rect
            self.tid = text

        def to_dict(self):
            d = {"from": 0, "to": 0}
            if self.rows > 1:
                d["rows"] = self.rows
            if self.cols > 1:
                d["cols"] = self.cols
            return d

        def to_dict(self):
            d = {"text": self.text}
            if self.rows > 1:
                d["rows"] = self.rows
            if self.cols > 1:
                d["cols"] = self.cols
            return d

    class Popup(tk.Menu):
        def __init__(self, master):
            tk.Menu.__init__(self, master, tearoff=0)
            #
            cascade = tk.Menu(self)
            cascade.add_command(label='up', command=master.add_row_up)
            cascade.add_command(label='down', command=master.add_row_down)
            self.add_cascade(label='add row', menu=cascade)
            #
            cascade = tk.Menu(self)
            cascade.add_command(label='left', command=master.add_col_left)
            cascade.add_command(label='right', command=master.add_col_right)
            self.add_cascade(label='add column', menu=cascade)
            #
            self.add_command(label='delete row', command=master.del_row)
            self.add_command(label='delete column', command=master.del_col)
            #
            cascade = tk.Menu(self)
            cascade.add_command(label='up', command=master.merge_up)
            cascade.add_command(label='down', command=master.merge_down)
            cascade.add_command(label='left', command=master.merge_left)
            cascade.add_command(label='right', command=master.merge_right)
            self.add_cascade(label='merge cell', menu=cascade)
            #
            cascade = tk.Menu(self)
            cascade.add_command(label='horizontal', command=master.split_horizontal)
            cascade.add_command(label='vertical', command=master.split_vertical)
            self.add_cascade(label='split cell', menu=cascade)
            #
            self.add_command(label='JSON to clipboard', command=lambda: self.json_to_clipboard(master))

        def json_to_clipboard(self, table):
            self.clipboard_clear()
            json_str = json.dumps(table.output())
            self.clipboard_append(json_str)

    HEIGHT = 0
    PADDING = 0

    def __init__(self, master, *a, **kw):
        self._table = None
        self.grid_ws = None  # width of columns
        self.grid_hs = None  # height of rows
        #
        self._font = kw.pop('font')
        TextTableBox.HEIGHT = self._font.metrics("linespace")
        TextTableBox.PADDING = TextTableBox.HEIGHT / 4
        rows, cols = self.specs_to_table(kw.pop('table'))
        #
        tk.Canvas.__init__(self, master, *a, **kw)
        self.draw_table(rows, cols)
        #
        self.bind('<MouseWheel>', self.on_scroll_)  # tk.Text need it to scroll across canvas.
        self.bind('<1>', lambda evt: self.select_cell(evt.x, evt.y))
        self.bind('<Double-1>', self.edit_)
        self._selected = None
        self._edited = tk.Text(self, font=self._font)
        self._edited.bind('<Control-Return>', self.finish_edit_)
        self._edited.bind('<Escape>', self.hide_input_)
        self._edited.bind('<Leave>', self.finish_edit_)
        if jex.is_macos():
            self._edited.bind('<Command-a>', self.edit_select_all_)
        else:
            self._edited.bind('<Control-a>', self.edit_select_all_)
        #
        self.bind(jex.mouse_right_button(), self.on_popup_menu_)
        self._menu = TextTableBox.Popup(self)

    def draw_table(self, rows, cols):
        self.delete(tk.ALL)
        #
        self.reset_cowh_(rows, cols)
        for row in self._table:
            for cell in row:
                i, j = divmod(cell.grid, cols)
                w, h = self.cell_size(cell)
                top = sum(self.grid_hs[:i], CANVAS_BIAS)
                left = sum(self.grid_ws[:j], CANVAS_BIAS)
                bottom = top + h
                right = left + w
                #
                rid = self.create_rectangle(left, top, right, bottom)
                x = (left + right) / 2
                y = (top + bottom) / 2
                tid = self.create_text(x, y, anchor=tk.CENTER, text=cell.text, font=self._font)
                cell.set_id(rid, tid)
        #
        # update canvas size; no need to add BIAS
        self.config(width=sum(self.grid_ws, CANVAS_BIAS), height=sum(self.grid_hs, CANVAS_BIAS))

    def specs_to_table(self, config):
        """
        turn a dictionary of specifications to an array of table cell objects.
        @param config: a dict, describing the table data and structure.
        """
        cells = []
        matrix = [[] for i in range(len(config))]
        grid_columns = 0
        for i, row in enumerate(config):
            row_data = []
            j = 0  # grid index, starts from zero, ends when it reaches row's ending.
            for cell in row:
                while j < len(matrix[i]) and matrix[i][j] == 1:
                    j += 1
                t = cell.get('text', '')
                r = cell.get('rows', 1)
                c = cell.get('cols', 1)
                row_data.append(TextTableBox.Cell(i*grid_columns+j, t, r, c))
                #
                for m in range(i, i+r):
                    for n in range(j, j+c):
                        if n >= len(matrix[m]):
                            matrix[m].extend([0] * (n-len(matrix[m])+1))
                        matrix[m][n] = 1
                j += c
            if grid_columns == 0:
                grid_columns = j
            elif grid_columns != len(matrix[i]):
                raise ValueError("Table has wrong structure of row %s." % i)
            cells.append(row_data)
        #
        self._table = cells
        return len(cells), grid_columns

    def output(self):
        specs = []
        for row in self._table:
            row_config = [cell.to_dict() for cell in row]
            specs.append(row_config)
        return specs

    def cell_size(self, cell):
        i, j = self.coord(cell.grid)
        h = sum(self.grid_hs[i:i+cell.rows])
        w = sum(self.grid_ws[j:j+cell.cols])
        return w, h

    def grid_cols(self):
        return len(self.grid_ws)

    def grid_rows(self):
        return len(self.grid_hs)

    def coord(self, grid_id):
        return divmod(grid_id, self.grid_cols())

    @staticmethod
    def set_spec_text(specs, content):
        for row in specs:
            for cell in row:
                from_ = cell['from']
                to_ = cell['to']
                cell['text'] = '\n'.join(content[from_:to_])
        return specs

    def on_scroll_(self, evt):
        self.master.event_generate('<MouseWheel>', delta=evt.delta, state=evt.state)

    def edit_(self, evt):
        cell = self.select_cell(evt.x, evt.y)
        if cell is None:
            return
        x1, y1, x2, y2 = self.bbox(cell.rid)
        self._edited.insert('1.0', cell.text)
        self._edited.place({'x': x1, 'y': y1, 'width': x2-x1, 'height': y2-y1})
        self._edited.focus_set()
        self._edited.tag_add(tk.SEL, '1.0', tk.END)

    def finish_edit_(self, evt):
        # avoid conflict between Ctrl-Enter and <Leave> event
        if not self._edited.winfo_ismapped():
            return
        content = self._edited.get('1.0', tk.END)
        content = content.strip(' \n')
        self._selected.text = content
        self.hide_input_()
        self.draw_table(self.grid_rows(), self.grid_cols())
        self.on_modified_()

    def edit_select_all_(self, evt):
        if not self._edited.winfo_ismapped():
            return
        self._edited.tag_add(tk.SEL, '1.0', tk.END)

    def reset_cowh_(self, rows, cols):
        """
        cowh: Configuration Of Width / Height (of grids).
        adjust configurations of width / height.
        """
        self.grid_hs = [0 for _ in range(rows)]
        self.grid_ws = [0 for _ in range(cols)]
        for row in self._table:
            for cell in row:
                lines = cell.text.split('\n')
                width = max([self._font.measure(k) for k in lines]) / cell.cols + TextTableBox.PADDING*2
                height = TextTableBox.HEIGHT * len(lines) / cell.rows + TextTableBox.PADDING*2
                i, j = divmod(cell.grid, cols)
                for m in range(i, i+cell.rows):
                    for n in range(j, j+cell.cols):
                        if width > self.grid_ws[n]:
                            self.grid_ws[n] = width
                        if height > self.grid_hs[m]:
                            self.grid_hs[m] = height

    def hide_input_(self, evt=None):
        self._edited.delete('1.0', tk.END)
        self._edited.place_forget()

    def find_cell(self, x, y):
        for row in self._table:
            for cell in row:
                x1, y1, x2, y2 = self.bbox(cell.rid)
                if x1 < x < x2 and y1 < y < y2:
                    return cell
        return None

    def on_popup_menu_(self, evt):
        if self.select_cell(evt.x, evt.y):
            self._menu.post(*self.winfo_pointerxy())

    def select_cell(self, x, y):
        cell = self.find_cell(x, y)
        if cell is None:
            return None
        if not self._selected is None:
            self.itemconfig(self._selected.rid, fill='')
        self.itemconfig(cell.rid, fill='green')
        self._selected = cell
        return cell

    def grid_to_cell(self, grid_id):
        for row in self._table:
            for cell in row:
                r, c = self.coord(cell.grid)
                cell_grids = (i*self.grid_cols()+j for i in range(r, r+cell.rows) for j in range(c, c+cell.cols))
                if grid_id in cell_grids:
                    return cell
        return None

    def add_row_up(self):
        row = self.nth_row(self._selected.grid)
        first_cell = self._table[row][0]
        cells = []
        reached = False
        for row in self._table:
            for cell in row:
                if reached:
                    cells.append(cell)
                elif cell == first_cell:
                    cells.extend([TextTableBox.Cell(0, 'new') for _ in range(self.grid_cols())])
                    cells.append(cell)
                    reached = True
                else:
                    cells.append(cell)
        self.draw_cell_array_(cells, self.grid_rows()+1, self.grid_cols())

    def add_row_down(self):
        row = self.nth_row(self._selected.grid)
        last_cell = self._table[row][-1]
        cells = []
        reached = False
        for row in self._table:
            for cell in row:
                if reached:
                    cells.append(cell)
                elif cell == last_cell:
                    cells.append(cell)
                    cells.extend([TextTableBox.Cell(0, 'new') for _ in range(self.grid_cols())])
                    reached = True
                else:
                    cells.append(cell)
        self.draw_cell_array_(cells, self.grid_rows()+1, self.grid_cols())

    def add_col_left(self):
        col = self._selected.grid % self.grid_cols()
        affected = []
        for i, row in enumerate(self._table):
            for j, cell in enumerate(row):
                left = cell.grid % self.grid_cols()
                if left <= col < left + cell.cols:
                    affected.append((i, j, cell))
        for i, j, c in affected:
            self._table[i].insert(j, TextTableBox.Cell(0, 'new', c.rows))
        cells = []
        for row in self._table:
            cells.extend(row)
        self.draw_cell_array_(cells, self.grid_rows(), self.grid_cols()+1)

    def add_col_right(self):
        col = self._selected.grid % self.grid_cols()
        affected = []
        for i, row in enumerate(self._table):
            for j, cell in enumerate(row):
                left = cell.grid % self.grid_cols()
                if left <= col < left + cell.cols:
                    affected.append((i, j, cell))
        for i, j, c in affected:
            self._table[i].insert(j+1, TextTableBox.Cell(0, 'new', c.rows))
        cells = []
        for row in self._table:
            cells.extend(row)
        self.draw_cell_array_(cells, self.grid_rows(), self.grid_cols()+1)

    def del_row(self):
        row = self.nth_row(self._selected.grid)
        affected = []
        start = row * self.grid_cols()
        for i in range(start, start + self.grid_cols()):
            cell = self.grid_to_cell(i)
            if cell not in affected:
                affected.append(cell)
        cells = []
        for row in self._table:
            for cell in row:
                if cell not in affected:
                    cells.append(cell)
                elif cell.rows > 1:
                    cell.rows -= 1
                    cells.append(cell)
        self.draw_cell_array_(cells, self.grid_rows()-1, self.grid_cols())

    def del_col(self):
        col = self._selected.grid % self.grid_cols()
        affected = []
        for i in [i*self.grid_cols()+col for i in range(self.grid_rows())]:
            cell = self.grid_to_cell(i)
            if cell not in affected:
                affected.append(cell)
        cells = []
        for row in self._table:
            for cell in row:
                if cell not in affected:
                    cells.append(cell)
                elif cell.cols > 1:
                    cell.cols -= 1
                    cells.append(cell)
        self.draw_cell_array_(cells, self.grid_rows(), self.grid_cols()-1)

    def merge_up(self):
        r1, c1 = self.coord(self._selected.grid)
        above = self.grid_to_cell(self.grid_cols()*(r1-1) + c1)
        if above is None:
            return
        r2, c2 = self.coord(above.grid)
        if c1 != c2:
            return
        if self._selected.cols != above.cols:
            return
        above.rows += self._selected.rows
        above.text = '%s\n%s' % (above.text, self._selected.text)
        # check redundant rows
        row_start = self.nth_row(above.grid)
        row_end = row_start + above.rows
        for i in range(row_start, row_end):
            row_cells = set([above])
            for j in range(0, self.grid_cols()):
                cell = self.grid_to_cell(i * self.grid_cols() + j)
                if cell in row_cells:
                    continue
                bottom_bound = self.nth_row(cell.grid) + cell.rows
                if bottom_bound == i+1:
                    row_cells.clear()
                    break
                row_cells.add(cell)
            if len(row_cells) > 0:
                break
        for c in row_cells:
            c.rows -= 1
        #
        cells = []
        for row in self._table:
            for cell in row:
                if cell != self._selected:
                    cells.append(cell)
        grid_rows = self.grid_rows()
        if len(row_cells) > 0:
            grid_rows -= 1
        self.draw_cell_array_(cells, grid_rows, self.grid_cols())

    def merge_down(self):
        r1, c1 = self.coord(self._selected.grid)
        below = self.grid_to_cell(self.grid_cols()*(r1+self._selected.rows) + c1)
        if below is None:
            return
        r2, c2 = self.coord(below.grid)
        if c1 != c2:
            return
        if self._selected.cols != below.cols:
            return
        self._selected.rows += below.rows
        self._selected.text = '%s\n%s' % (self._selected.text, below.text)
        # check redundant rows
        row_start = self.nth_row(self._selected.grid)
        row_end = row_start + self._selected.rows
        for i in range(row_start, row_end):
            row_cells = set([self._selected])
            for j in range(0, self.grid_cols()):
                cell = self.grid_to_cell(i * self.grid_cols() + j)
                if cell in row_cells:
                    continue
                bottom_bound = self.nth_row(cell.grid) + cell.rows
                if bottom_bound == i+1:
                    row_cells.clear()
                    break
                row_cells.add(cell)
            if len(row_cells) > 0:
                break
        for c in row_cells:
            c.rows -= 1
        #
        cells = []
        for row in self._table:
            for cell in row:
                if cell != below:
                    cells.append(cell)
        grid_rows = self.grid_rows()
        if len(row_cells) > 0:
            grid_rows -= 1
        self.draw_cell_array_(cells, grid_rows, self.grid_cols())

    def merge_left(self):
        r1, c1 = self.coord(self._selected.grid)
        if c1 == 0:
            return
        left = self.grid_to_cell(self._selected.grid-1)
        r2, c2 = self.coord(left.grid)
        if r1 != r2:
            return
        if self._selected.rows != left.rows:
            return
        left.cols += self._selected.cols
        left.text = '%s\n%s' % (left.text, self._selected.text)
        # check redundant column
        col_start = left.grid % self.grid_cols()
        col_end = col_start + left.cols
        for i in range(col_start, col_end):
            row_cells = set([left])
            for j in range(0, self.grid_rows()):
                cell = self.grid_to_cell(j * self.grid_cols() + i)
                if cell in row_cells:
                    continue
                right_bound = cell.grid % self.grid_cols() + cell.cols
                if right_bound == i+1:
                    row_cells.clear()
                    break
                row_cells.add(cell)
            if len(row_cells) > 0:
                break
        for c in row_cells:
            c.cols -= 1
        #
        cells = []
        for row in self._table:
            for cell in row:
                if cell != self._selected:
                    cells.append(cell)
        grid_cols = self.grid_cols()
        if len(row_cells) > 0:
            grid_cols -= 1
        self.draw_cell_array_(cells, self.grid_rows(), grid_cols)

    def merge_right(self):
        r1, c1 = self.coord(self._selected.grid)
        if c1 + self._selected.cols == self.grid_cols():
            return
        right = self.grid_to_cell(self._selected.grid+self._selected.cols)
        r2, c2 = self.coord(right.grid)
        if r1 != r2:
            return
        if self._selected.rows != right.rows:
            return
        self._selected.cols += right.cols
        self._selected.text = '%s\n%s' % (self._selected.text, right.text)
        # check redundant column
        col_start = self._selected.grid % self.grid_cols()
        col_end = col_start + self._selected.cols
        for i in range(col_start, col_end):
            row_cells = set([self._selected])
            for j in range(0, self.grid_rows()):
                cell = self.grid_to_cell(j * self.grid_cols() + i)
                if cell in row_cells:
                    continue
                right_bound = cell.grid % self.grid_cols() + cell.cols
                if right_bound == i+1:
                    row_cells.clear()
                    break
                row_cells.add(cell)
            if len(row_cells) > 0:
                break
        for c in row_cells:
            c.cols -= 1
        #
        cells = []
        for row in self._table:
            for cell in row:
                if cell != right:
                    cells.append(cell)
        grid_cols = self.grid_cols()
        if len(row_cells) > 0:
            grid_cols -= 1
        self.draw_cell_array_(cells, self.grid_rows(), grid_cols)

    def split_horizontal(self):
        if self._selected.cols == 1:
            return
        cells = []
        for row in self._table:
            for cell in row:
                if cell != self._selected:
                    cells.append(cell)
                else:
                    for i in range(0, cell.cols):
                        cells.append(TextTableBox.Cell(0, cell.text, cell.rows))
        self.draw_cell_array_(cells, self.grid_rows(), self.grid_cols())

    def split_vertical(self):
        if self._selected.rows == 1:
            return
        cells = []
        for row in self._table:
            for cell in row:
                if cell == self._selected:
                    r, c = self.coord(cell.grid)
                    for i in range(r+1, r+cell.rows):
                        grid_idx = i * self.grid_cols() + c
                        cells.append(TextTableBox.Cell(grid_idx, cell.text, 1, cell.cols))
                    cell.rows = 1
                cells.append(cell)
        cells.sort(key=lambda i: i.grid)
        self.draw_cell_array_(cells, self.grid_rows(), self.grid_cols())

    def on_modified_(self):
        w = self.master.master
        if isinstance(w, TextEditor):
            w.on_modified()

    def draw_cell_array_(self, cells, row_num, col_num):
        """
        @param cells: array of table cells. One dimension.
        @param row_num and col_num: the number of rows and cols of new table.
        """
        new_table = []
        matrix = [0] * row_num * col_num
        i, j = 0, 0  # i is iterator to the cells; j is iterator to table grids
        new_row = []
        while i < len(cells):
            cells[i].grid = j
            new_row.append(cells[i])
            #
            r, c = divmod(j, col_num)
            for m in range(r, r+cells[i].rows):
                for n in range(c, c+cells[i].cols):
                    matrix[m * col_num + n] = 1
            #
            i += 1
            if i == len(cells):
                new_table.append(new_row)
                break
            while matrix[j] == 1:
                j += 1
                if j % col_num == 0:
                    new_table.append(new_row)
                    new_row = []
        #
        self._table[:] = new_table
        self._selected = None
        self.draw_table(row_num, col_num)
        self.on_modified_()

    def nth_row(self, cell_idx):
        return int(cell_idx / self.grid_cols())


def unit_test_calendar():
    root = tk.Tk()
    tk.Label(root, text='the date you selected:').pack(side=tk.TOP, fill=tk.X, expand=tk.YES)
    selection = tk.StringVar()
    tk.Entry(root, textvariable=selection).pack(side=tk.TOP, fill=tk.X, expand=tk.YES)
    def choose_date():
        dlg = CalendarDlg(root)
        dlg.show()
        if dlg.date is not None:
            selection.set(str(dlg.date))
    tk.Button(root, text='select', command=choose_date).pack(side=tk.TOP)
    root.mainloop()

if __name__ == "__main__":
    unit_test_calendar()