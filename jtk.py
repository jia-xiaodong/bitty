#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
An enhancement to Tkinter.
"""

import Tkinter as tk
import ttk
import calendar
import datetime
import tkFont
import math
import tkFileDialog
from PIL import Image, ImageSequence, ImageTk
from sys import platform
import jex


PLATFORM = jex.enum1(Darwin=0, Win=1)
curr_os = PLATFORM.Darwin if platform.startswith('darwin') else PLATFORM.Win


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

      2. Then override the beenModified() method to implement the behavior
      that you want to happen when the Text is modified.
    """

    def __init__(self):
        self.clear_modified_flag_()
        self.bind('<<Modified>>', self.event_fired_)  # built-in virtual event

    def been_modified(self, event=None):
        """
        Override this method in your own class
        """
        pass

    def event_fired_(self, event=None):
        if self.clearing_:
            return
        self.been_modified(event)
        #
        # if no manual resetting, <<Modified>> event won't fire again
        self.clear_modified_flag_()

    def clear_modified_flag_(self):
        self.clearing_ = True
        try:
            # Set 'modified' to 0.  This will also trigger the <<Modified>> virtual event
            # So we need set above sentinel.
            self.tk.call(self._w, 'edit', 'modified', 0)
        finally:
            self.clearing_ = False


class NotifiedText(tk.Text, ModifiedMixin):
    EVENT_MODIFIED = '<<Changed>>'
    EVENT_VIEW_CHG = '<<ViewChanged>>'

    def __init__(self, *a, **b):
        tk.Text.__init__(self, *a, **b)
        ModifiedMixin.__init__(self)
        self._event_listeners = {}
        #self._event_count = {}  # debug

    def add_listeners(self, event, listener):
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
    _text_font = None
    _digit_width = 0

    def __init__(self, master, text, **kwargs):
        """
        Display line number and bookmarks.
        @param text: is instance of NotifiedText
        """
        tk.Canvas.__init__(self, master, **kwargs)
        self._text = text
        self._range = (-1, -1)
        self.binding_keys_()

        # text should notify canvas when event is fired
        self._text.add_listeners(NotifiedText.EVENT_MODIFIED, self)
        self._text.add_listeners(NotifiedText.EVENT_VIEW_CHG, self)

        # use a font to measure the width of canvas required to hold digits
        if self._text_font is None:
            dummy = self.create_text(0, 0, text='0')
            self._text_font = tkFont.nametofont(self.itemcget(dummy, 'font'))
            self.delete(dummy)
            self._digit_width = max(self._text_font.measure(str(i)) for i in range(10))

    def redraw_(self):
        positions = []
        idx = self._text.index("@0,0")  # coordinates --> 'line.char'
        start = int(idx.split(".")[0])
        while True:
            info = self._text.dlineinfo(idx)
            if info is None:
                break
            positions.append(info[1])
            idx = self._text.index("%s+1line" % idx)
        end = int(idx.split(".")[0]) - 1
        # if no change, don't redraw
        if self._range == (start, end):
            return
        self._range = (start, end)
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
        required = self._digit_width * (int(math.log10(line_num))+1)
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
                  'PasteSelection', # ButtonRelease-2 (mouse right button)
                  'Undo',           # Mod1-z, Ctrl-Lock-Z
                  'Redo',           # Mod1-y, Ctrl-Lock-Y
                  'Clear']:         # @TODO: <Key-Clear>
            self._ops[i] = lambda: self._txt.event_generate('<<%s>>' % i)

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
        bindings = ['<Mod1-a>', '<Control-a>']
        self._ops['SelectAll'] = self.select_all
        self._txt.bind(bindings[curr_os], self.select_all)
        #
        bindings = ['<Mod1-Up>', '<Control-Up>']
        self._ops['Top'] = self.jump_top
        self._txt.bind(bindings[curr_os], self.jump_top)
        #
        bindings = ['<Mod1-Down>', '<Control-Down>']
        self._ops['Bottom'] = self.jump_bottom
        self._txt.bind(bindings[curr_os], self.jump_bottom)
        #
        if curr_os == PLATFORM.Darwin:
            self._txt.bind('<Mod1-Left>', self._ops['LineStart'])
            self._txt.bind('<Mod1-Right>', self._ops['LineEnd'])
        elif curr_os == PLATFORM.Win:
            # TODO:
            pass

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

    def next_line(self):
        self._txt.mark_set(tk.INSERT, tk.INSERT + ' +1line')

    def prev_line(self):
        self._txt.mark_set(tk.INSERT, tk.INSERT + ' -1line')

    def next_char(self):
        self._txt.mark_set(tk.INSERT, tk.INSERT + ' +1c')

    def prev_char(self):
        self._txt.mark_set(tk.INSERT, tk.INSERT + ' -1c')

    def flip_adj_chars(self):
        pass

    def open_new_line(self):
        pass

    def del_to_line_end(self):
        pass

    def del_next_char(self):
        pass

    def del_prev_char(self):
        pass

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
        self._txt.add_listeners(NotifiedText.EVENT_MODIFIED, self)
        self.bind(NotifiedText.EVENT_MODIFIED, self.on_modified, True)

    def content(self):
        content = self._txt.get('1.0', tk.END+'-1c').split('\n')
        # delete redundant space (line-end)
        content = [i.rstrip(' ') for i in content]
        return '\n'.join(content)

    def operations(self):
        return self._ops


class TabBox(tk.Frame):
    WIDTH_ACTIVE = 20
    WIDTH_HIDDEN = 10

    def __init__(self, master=None, *a, **kw):
        tk.Frame.__init__(self, master, *a, **kw)
        self._tabs = {}
        self._active = None
        self._top = tk.Frame(self)
        self._top.pack(side=tk.TOP, fill=tk.X, expand=tk.NO, anchor=tk.W)

    def add(self, frame, caption):
        """
        @param frame is an instance of tk.Frame class
        """
        frame.pack_forget()  # hide on init
        btn = tk.Button(self._top, text=caption, relief=tk.SUNKEN,
                        foreground='white', disabledforeground='black', bg='grey',
                        command=lambda: self.switch_tab(frame))
        btn.pack(side=tk.LEFT)
        self._tabs[frame] = btn
        if len(self._tabs) == 1:
            self.switch_tab(frame)

    def remove(self, frame=None, caption=None):
        """
        @param frame is tk.Frame instance
        @param caption is str instance
        """
        if caption is not None:
            for f, b in self._tabs.iteritems():
                if b['text'] == caption:
                    frame = f
                    break  # remove the first-found one even if multiple pages have same caption
        if frame is None:
            return
        if frame not in self._tabs:
            return
        frame.pack_forget()
        self._tabs[frame].pack_forget()
        del self._tabs[frame]
        #
        # pick up another as active frame
        if frame != self._active:
            return
        self._active = None
        if len(self._tabs) > 0:
            self.switch_tab(self._tabs.keys()[-1])

    def switch_tab(self, frame):
        """
        @param frame is tk.Frame instance
        """
        if self._active == frame:
            return
        #
        if self._active:
            self._tabs[self._active].config(relief=tk.SUNKEN, state=tk.NORMAL)
            self._active.pack_forget()
        frame.pack(side=tk.BOTTOM, expand=tk.YES, fill=tk.BOTH)
        self._tabs[frame].config(relief=tk.FLAT, state=tk.DISABLED)
        self._active = frame

    def exists(self, caption):
        return any(b['text'] == caption for b in self._tabs.itervalues())

    def iter_tabs(self):
        """
        easier than iterator protocol
        """
        for frame in self._tabs:
            yield frame

    def active(self):
        return self._active

    def count(self):
        return len(self._tabs)


class MultiTabEditor(TabBox):
    WIDTH_ACTIVE = 20
    WIDTH_HIDDEN = 10
    EVENT_SWITCH = '<<SwitchTab>>'

    def __init__(self, master, *a, **kw):
        self._captions = {}
        self._font = kw.pop('font', None)
        TabBox.__init__(self, master, *a, **kw)

    def add(self, editor, caption):
        """
        Do NOT use this method!
        It's used internally through overriding.
        Use below new_editor instead.
        """
        self._captions[editor] = caption
        caption = self.fake_caption_(editor)
        #
        TabBox.add(self, editor, caption)
        # the full tab title
        CreateToolTip(self._tabs[editor], self._captions[editor])
        #
        editor.bind(TextEditor.EVENT_CLEAN, self.event_caption_)
        editor.bind(TextEditor.EVENT_DIRTY, self.event_caption_)

    def remove(self, editor=None, caption=None):
        if caption is not None:
            try:
                editor = [f for (f, c) in self._captions.iteritems() if c == caption][0]
            except IndexError as e:
                return
        TabBox.remove(self, editor)
        #
        if editor in self._captions:
            del self._captions[editor]

    def switch_tab(self, editor):
        if self._active == editor:
            return
        #
        if self._active is not None:
            self._tabs[self._active].config(text=self.fake_caption_(self._active))
        TabBox.switch_tab(self, editor)
        self._tabs[editor].config(text=self.fake_caption_(editor, True))
        self.event_generate(MultiTabEditor.EVENT_SWITCH, when='tail')

    def exists(self, caption):
        return any(c == caption for c in self._captions.itervalues())

    def set_caption(self, editor, caption):
        btn = self._tabs[editor]
        self._captions[editor] = caption
        active = (btn.cget('state') == tk.DISABLED)
        btn.config(text=self.fake_caption_(editor, active))
        CreateToolTip(btn, caption)

    def reset_caption(self, editor):
        if editor not in self._tabs:
            return
        btn = self._tabs[editor]
        active = (btn.cget('state') == tk.DISABLED)
        btn.config(text=self.fake_caption_(editor, active))

    def get_caption(self, editor):
        return self._captions[editor] if editor in self._captions else ''

    def fake_caption_(self, editor, active=False):
        """
        the caption displaying on the tab-bar.
        If it's too long, give it a shorter one.
        """
        limit = MultiTabEditor.WIDTH_ACTIVE if active else MultiTabEditor.WIDTH_HIDDEN
        caption = self._captions[editor]
        if editor.modified():
            caption = '* %s' % caption
        if len(caption) > limit:
            caption = '%s...' % caption[:limit-3]
        return caption

    def event_caption_(self, evt):
        self.reset_caption(evt.widget)

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

    def iter_texts(self):
        for t in self.iter_tabs():
            yield t.core()

    def close_all(self):
        tabs = [i for i in self.iter_tabs()]
        map(lambda t: self.remove(t), tabs)


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


class ImageBox(tk.Canvas):
    def __init__(self, master, *a, **kw):
        """
        keyword arguments:
          image: file object. Required.
          ext: str, filename extension. Required.
          scale: integer, 0~100. Optional. 100 is default value.
        @note: keep file object alive while ImageBox alive except you don't use 'dump' method
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
        self.bind('<Map>', self.display_)
        self.bind('<Enter>', self.hud_on_)
        self.bind('<Leave>', self.hud_off_)
        # For GIF
        self._gif_task = 0
        self._gif_buff = None
        self._gif_curr = -1
        self._gif_dura = 0
        if self._src.format == 'GIF':
            self._gif_curr = 0
            self._gif_buff = ImageSequence.Iterator(self._src)
            self._gif_dura = min(self._src.info['duration'], 200)
            self.bind('<1>', self.toggle_)
        #
        hud = tk.Frame(self)
        hud.pack()
        tk.Label(hud, textvariable=self._info).pack(side=tk.TOP)
        frm = tk.Frame(hud)
        frm.pack(side=tk.TOP)
        tk.Scale(frm, orient=tk.HORIZONTAL, variable=self._scale, from_=1).pack(side=tk.LEFT)
        tk.Button(frm, text='Export', command=self.dump).pack(side=tk.LEFT)
        self._hud = self.create_window(3, 3, anchor=tk.NW, window=hud, state=tk.HIDDEN)

    def is_gif(self):
        return self._gif_curr > -1

    def resize_(self):
        if self._gif_task > 0:  # GIF is playing
            self.after_cancel(self._gif_task)
            self._gif_task = 0
        self.after(100, self.display_)

    def toggle_(self, evt):
        if not self.is_gif():
            return
        if self._gif_task > 0:
            self.after_cancel(self._gif_task)
            self._gif_task = 0
        else:
            self._gif_task = self.after(self._gif_dura, self.display_)

    def display_(self, evt=None):
        scale = self._scale.get()
        new_w, new_h = self._src.width*scale/100, self._src.height*scale/100
        #
        if self._dst is None or self._dst.width() != new_w:
            self.config(width=new_w, height=new_h)
        #
        if self.is_gif():
            src = self._gif_buff[self._gif_curr]
            if self._gif_task > 0:
                self._gif_curr += 1
                if self._gif_curr < self._src.n_frames:
                    self._gif_task = self.after(self._gif_dura, self.display_)
                else:
                    self._gif_task = 0
                    self._gif_curr = 0
        else:
            src = self._src
        self._dst = ImageTk.PhotoImage(image=src.resize((new_w, new_h)))
        if self._iid == 0:
            # TODO: why start drawing from (3,3)?
            self._iid = self.create_image(3, 3, anchor=tk.NW, image=self._dst)
        else:
            self.itemconfig(self._iid, image=self._dst)
        #
        if self.is_gif():
            self._info.set('GIF, %s, %s/%s' % (self._src.size, self._gif_curr+1, self._src.n_frames))
        else:
            self._info.set('%s, %s' % (self._src.format, self._src.size))

    def hud_on_(self, evt):
        self.itemconfig(self._hud, state=tk.NORMAL)
        self._scb = self._scale.trace('w', lambda n, i, m: self.resize_())

    def hud_off_(self, evt):
        self.itemconfig(self._hud, state=tk.HIDDEN)
        self._scale.trace_vdelete('w', self._scb)
        self._scb = None

    def dump(self):
        filename = tkFileDialog.asksaveasfilename(defaultextension=self._ext)
        if filename == '':
            return
        with open(filename, 'wb') as fo:
            self._bak.seek(0)
            fo.write(self._bak.read())

    def get_data(self):
        self._bak.seek(0)
        return self._bak.read(), self._scale.get(), self._ext


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