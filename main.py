#!/usr/bin/python
# -*- coding: utf-8 -*-
import base64
import sys
import jex
import math

if jex.isPython3():
    import tkinter as tk
    from tkinter import ttk
    import tkinter.messagebox as tkMessageBox
    import tkinter.filedialog as tkFileDialog
    import tkinter.font as tkFont
    from enum import Enum, IntEnum

else:
    import Tkinter as tk
    import ttk
    import tkMessageBox
    import tkFileDialog
    import tkFont

import jdb, jtk, jex
import os
import datetime
from PIL import Image, ImageTk
from sys import platform
import json
import io

DATE_FORMAT = '%Y-%m-%d'  # e.g., 2019-03-18


class TagPicker(tk.Frame):
    UNNAMED = '<Node>'
    QUERY_TIP = '<Here is the keyword for query>'

    class Popup(tk.Menu):
        def __init__(self, master, selection):
            tk.Menu.__init__(self, master, tearoff=0)
            self.add_command(label="Add Root Node", command=master.add_root_)
            has_move = (not master._moved_node is None and not master._been_shown)
            if master._been_shown:
                master._moved_node = None
                master._been_shown = False
            if len(selection) > 0:
                label = master._tree.item(selection, 'text')
                self.add_command(label="Delete '%s'" % label, command=master.del_node_)
                self.add_command(label="Add Child", command=master.add_child_)
                self.add_command(label="Rename...", command=lambda: master.show_rename_entry_(selection))
                self.add_command(label="Select '%s'" % label, command=master.select_tag_)
                #
                # either [1/2] or [2/2]. only display one of these 2 menu items.
                if master._moved_node is None:
                    self.add_command(label="[1/2] Move '%s'?" % label,
                                     command=lambda: master.move_item_start_(selection))
            #
            if has_move and master.move_ok_(selection):
                label = master._tree.item(master._moved_node, 'text')
                self.add_command(label="[2/2] Place '%s' here?" % label,
                                 command=lambda: master.move_item_end_(selection))
                master._been_shown = True

    class HiddenNode:
        def __init__(self, parent, iid, index):
            self.parent = parent
            self.iid = iid
            self.index = index

    def __init__(self, master, *a, **kw):
        """
        @param kw: supports
            1. database: DocBase object
            2. owned: array of DBRecordTag objects (optional)
        @return .get_selection(): array of DBRecordTag objects
        """
        self._store = kw.pop('database')
        self._tags = self._store.get_all_tags()
        self._selected = kw.pop('owned', [])
        #
        tk.Frame.__init__(self, master, *a, **kw)
        #
        # user can provide keyword to filter tag-tree, only leaving matched ones.
        self._filtered = []  # the hidden tree-nodes (filtered out)
        self._query = tk.StringVar()
        e = tk.Entry(master, textvariable=self._query)
        jtk.MakePlaceHolder(e, TagPicker.QUERY_TIP)
        e.pack(side=tk.TOP, fill=tk.X, expand=tk.YES)
        e.bind('<Return>', self.on_query_)
        #
        # display all tags in a tree
        self._tree = ttk.Treeview(master, columns='sn', displaycolumns=[],
                                  show='tree',  # three options: '<Empty>', 'headings', 'tree'
                                  selectmode='browse')
        self._tree.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        self._tree.bind(jex.mouse_right_button(), self.on_popup_menu_)
        self._tree.bind('<Double-1>', self.select_tag_)
        # map(lambda i: self.draw_tags_('', i), self._tags)
        for i in self._tags:
            self.draw_tags_('', i)
        self._moved_node = None  # tag can be moved to another tag as its child
        self._been_shown = False  # show this menu item only once
        #
        # user can select tag from tag-tree and put their text to below list-box.
        tk.Label(master, text='Selected:').pack(side=tk.TOP, anchor=tk.W)
        self._list = tk.Listbox(master, selectmode=tk.SINGLE, height=5)
        self._list.pack(fill=tk.BOTH, expand=tk.YES)
        self._list.bind('<BackSpace>', self.deselect_tag_)
        self._list.bind('<Double-1>', self.deselect_tag_)
        # map(lambda i: self._list.insert(tk.END, i.name), self._selected)
        for i in self._selected:
            self._list.insert(tk.END, i.name)
        #
        # "self._name" seems to be reserved in somewhere.
        # If used, ridiculous exception would be raised (unhashable object) when destroyed
        self._naming = tk.StringVar()
        #
        # used to rename a tree node, show off when necessary
        self._entry = tk.Entry(self._tree, textvariable=self._naming)
        self._entry.bind('<Return>', self.rename_)

    def on_popup_menu_(self, evt):
        focused = self._tree.focus()
        clicked = self._tree.identify_row(evt.y)
        if focused != clicked:
            self._tree.selection_remove(focused)  # -- NOTE --
            self._tree.selection_add(clicked)  # selection != focus
            self._tree.focus(clicked)  # selection is visual; focus is logical.
        TagPicker.Popup(self, clicked).post(*self.winfo_pointerxy())

    def on_query_(self, evt):
        # 1. restore
        # map(lambda i: self._tree.move(i.iid, i.parent, i.index), self._filtered)
        for i in self._filtered:
            self._tree.move(i.iid, i.parent, i.index)
        del self._filtered[:]
        # 2.
        keyword = self._query.get().strip(' \n')
        if keyword == '':
            return 'break'
        # 3. use new keyword to filter
        for i in self._tree.get_children():
            if self.filter_node_(i, keyword):
                item = TagPicker.HiddenNode('', i, self._tree.index(i))
                self._filtered.append(item)
        hidden = [i.iid for i in self._filtered]
        self._tree.detach(*hidden)
        return 'break'

    def filter_node_(self, iid, keyword):
        hidden = []
        # depth-first search in children nodes
        children = self._tree.get_children(iid)
        for i in children:
            if self.filter_node_(i, keyword):
                item = TagPicker.HiddenNode(iid, i, self._tree.index(i))
                self._filtered.append(item)
                hidden.append(i)
        if len(hidden) < len(children):
            return False
        # since not in children, do a case-insensitive comparison with itself.
        name = self._tree.item(iid, 'text')
        if keyword.lower() in name.lower():
            self._tree.see(iid)
            return False
        # Because parent is removed (detached), the children would vanish automatically.
        # So no need to filter them again.
        self._filtered[:] = [i for i in self._filtered if i.iid not in children]
        return True

    def select_tag_(self, evt=None):
        selection = self._tree.focus()
        label = self._tree.item(selection, 'text')
        if label == TagPicker.UNNAMED:
            return
        target = self.tag_from_node_(selection)
        # replace coarse with more specific one
        for i in self._selected[:]:
            if target.find(i.sn) is not None:  # same or i is descendant of target
                return
            if i.find(target.sn) is not None:  # target is better than i
                self._selected.remove(i)
                break
        self._selected.append(target)
        self._list.delete(0, tk.END)
        # map(lambda i: self._list.insert(tk.END, i.name), self._selected)
        for i in self._selected:
            self._list.insert(tk.END, i.name)

    def deselect_tag_(self, evt):
        text = self._list.get(tk.ACTIVE)
        self._list.delete(tk.ACTIVE)
        for i in self._selected[:]:
            if i.name == text:
                self._selected.remove(i)
                return

    def draw_tags_(self, parent, tag):
        iid = self._tree.insert(parent, tk.END, text=tag.name, values=tag.sn, tags='node')
        for i in tag.children:
            self.draw_tags_(iid, i)

    def add_root_(self):
        tag = jdb.DBRecordTag(TagPicker.UNNAMED)
        self._store.insert_tag(tag)
        self._tags.append(tag)
        iid = self._tree.insert('', tk.END, text=TagPicker.UNNAMED, values=tag.sn, tags='node', open=True)
        self.schedule_show_rename_entry(iid)

    def del_node_(self):
        iid = self._tree.focus()
        tag = self.tag_from_node_(iid)
        if self._store.check_use(tag) > 0:
            tkMessageBox.showerror(MainApp.TITLE, '%s\nis in use\nand cannot be removed.' % tag.name)
            return
        jdb.DBRecordTag.forest_delete(self._tags, tag)
        self._store.delete_tag(tag)
        self._tree.delete(iid)

    def add_child_(self):
        iid = self._tree.focus()
        selected_tag = self.tag_from_node_(iid)
        tag = jdb.DBRecordTag(TagPicker.UNNAMED, selected_tag.sn)
        jdb.DBRecordTag.forest_add(self._tags, tag)
        self._store.insert_tag(tag)
        selected_tag.add_child(tag)
        child = self._tree.insert(iid, tk.END, text=TagPicker.UNNAMED, values=tag.sn, tags='node', open=True)
        self.schedule_show_rename_entry(child)

    def schedule_show_rename_entry(self, iid):
        self._tree.see(iid)
        self._tree.focus(iid)
        # wait a period of time for node to be visible (see).
        self.after(50, lambda: self.show_rename_entry_(iid))

    def show_rename_entry_(self, iid):
        x, y, w, h = self._tree.bbox(iid)
        self._naming.set(self._tree.item(iid, 'text'))
        self._entry.place(x=x, y=y, width=w, height=h)
        self._entry.select_range(0, tk.END)
        self._entry.focus_set()

    def rename_(self, evt):
        name = self._naming.get().strip(' \n')
        if name == '':
            return 'break'
        iid = self._tree.focus()
        old = self._tree.item(iid, 'text')
        if name == old:
            return 'break'
        self._tree.item(iid, text=name)
        self._entry.place_forget()
        tag = self.tag_from_node_(iid)
        tag.name = name
        self._store.update_tag(tag)
        return 'break'

    def tag_from_node_(self, iid):
        """
        @return DBRecordTag object
        """
        sn = self._tree.item(iid, 'values')
        sn = int(sn[0])
        return jdb.DBRecordTag.forest_find(self._tags, sn)

    def get_selection(self):
        return self._selected

    def move_item_start_(self, target):
        self._moved_node = target
        self._been_shown = False

    def move_item_end_(self, parent):
        # 1. visual effect
        self._tree.move(self._moved_node, parent, len(self._tree.get_children(parent)))
        # 2. data structure
        moved = self.tag_from_node_(self._moved_node)
        jdb.DBRecordTag.forest_delete(self._tags, moved)
        if parent == '':
            moved.parent = 0
        else:
            parent = self._tree.item(parent, 'values')
            moved.parent = int(parent[0])
        jdb.DBRecordTag.forest_add(self._tags, moved)
        # 3. database
        self._store.update_tag(moved)
        # 4. misc
        self._moved_node = None

    def move_ok_(self, parent):
        if self._tree.parent(self._moved_node) == parent:
            return False  # not necessary to move, already been here.
        if parent == '':
            return True  # node can be moved to root
        moved = self.tag_from_node_(self._moved_node)
        static = self._tree.item(parent, 'values')
        static = int(static[0])
        if moved.find(static):
            return False  # node can't be moved to its descendant.
        return True


class DocPropertyDlg(jtk.ModalDialog):
    def __init__(self, master, *a, **kw):
        """
        keyword parameters:
          1. database: DocBase object. Required.
          2. record: DBRecordDoc object. Required
        @return True if something is changed.
        """
        self._store = kw.pop('database')
        self._record = kw.pop('record')
        self._title = tk.StringVar(value=self._record.title)
        self._date_created = tk.StringVar(value=str(self._record.date_created))
        self._date_modified = tk.StringVar(value=str(self._record.date_modified))
        #
        kw['title'] = 'Document Property'
        jtk.ModalDialog.__init__(self, master, *a, **kw)

    def body(self, master):
        frm = tk.Frame(master)
        frm.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        tk.Label(frm, text='Title:').pack(side=tk.LEFT)
        self._e = tk.Entry(frm, textvariable=self._title)
        self._e.pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        #
        frm = tk.Frame(master)
        frm.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        tk.Label(frm, text='Created:').pack(side=tk.LEFT)
        e = tk.Entry(frm, textvariable=self._date_created)
        e.pack(side=tk.LEFT)
        self._indicator = tk.Label(frm, text='V', fg='dark green')
        self._indicator.pack(side=tk.LEFT)
        b = tk.Button(frm, text='...', command=self.change_date)
        b.pack(side=tk.LEFT)
        self._date_created.trace('w', self.date_changed_)
        #
        frm = tk.Frame(master)
        frm.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        tk.Label(frm, text='Modified:').pack(side=tk.LEFT)
        e = tk.Entry(frm, textvariable=self._date_modified)
        e.pack(side=tk.LEFT)
        self._indicator2 = tk.Label(frm, text='V', fg='dark green')
        self._indicator2.pack(side=tk.LEFT)
        b = tk.Button(frm, text='...', command=self.change_date2)
        b.pack(side=tk.LEFT)
        self._date_modified.trace('w', self.date2_changed_)
        #
        self._tag_picker = TagPicker(master, database=self._store, owned=self._record.tags[:])
        self._tag_picker.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        return self._e  # make it getting input focus

    def apply(self):
        self._record.title = self._title.get().strip(' \n')
        self._record.tags = self._tag_picker.get_selection()
        date = self.get_date(self._date_created)
        if date is not None and date != self._record.date_created:
            self._record.date_created = date
        date = self.get_date(self._date_modified)
        if date is not None and date != self._record.date_modified:
            self._record.date_modified = date
        self.result = True

    def validate(self):
        title = self._title.get().strip(' \n')
        if title == '':
            jtk.MessageBubble(self._e, 'Title cannot be empty!')
            return False
        date1 = self.get_date(self._date_created)
        date2 = self.get_date(self._date_modified)
        if date1 is None or date2 is None:
            jtk.MessageBubble(self._e, 'Time format is wrong!')
            return False
        return True

    def change_date(self):
        current_date = self.get_date(self._date_created)
        dlg = jtk.CalendarDlg(self, date=self._record.date_created if current_date is None else current_date)
        dlg.show()
        if dlg.date != current_date:
            self._date_created.set(str(dlg.date))
        self.set_indicator_(self._indicator, True)

    def date_changed_(self, name, index, mode):
        dt = self.get_date(self._date_created)
        self.set_indicator_(self._indicator, dt is not None)

    def change_date2(self):
        current_date = self.get_date(self._date_modified)
        dlg = jtk.CalendarDlg(self, date=self._record.date_modified if current_date is None else current_date)
        dlg.show()
        if dlg.date != current_date:
            self._date_modified.set(str(dlg.date))
        self.set_indicator_(self._indicator2, True)

    def date2_changed_(self, name, index, mode):
        dt = self.get_date(self._date_modified)
        self.set_indicator_(self._indicator2, dt is not None)

    @staticmethod
    def set_indicator_(label, passed):
        if passed:
            label['fg'] = 'dark green'
            label['text'] = 'V'
        else:
            label['fg'] = 'red'
            label['text'] = 'X'

    @staticmethod
    def get_date(date_str_var: tk.StringVar):
        try:
            dt = date_str_var.get()
            dt = datetime.datetime.strptime(dt, DATE_FORMAT)
            return datetime.date(year=dt.year, month=dt.month, day=dt.day)
        except ValueError:
            return None


class TagPickDlg(jtk.ModalDialog):
    def __init__(self, master, *a, **kw):
        self._store = kw.pop('database')
        self._tags = kw.pop('tags', None)
        self._owned = kw.pop('owned', [])
        jtk.ModalDialog.__init__(self, master, *a, **kw)

    def body(self, master):
        tp = TagPicker(master, database=self._store, owned=self._owned)
        tp.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        self._tag_picker = tp

    def apply(self):
        self.result = self._tag_picker.get_selection()


class SearchCondition(tk.Frame):
    def __init__(self, master, *a, **kw):
        tk.Frame.__init__(self, master, *a, **kw)
        self._switch = tk.IntVar(value=0)

    def enabled(self):
        return True if self._switch.get() else False


class ByTitle(SearchCondition):
    PLACE_HOLDER = '<Space Separated Keywords (AND)>'
    """
    @return an array of keywords.
    """

    def __init__(self, master, *a, **kw):
        SearchCondition.__init__(self, master, *a, **kw)
        #
        self._result = tk.StringVar()
        tk.Checkbutton(self, variable=self._switch).pack(side=tk.LEFT)
        cb = self.register(self.auto_toggle)
        e = tk.Entry(self, textvariable=self._result, validate='key', validatecommand=(cb, '%P'))
        e.pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        jtk.MakePlaceHolder(e, ByTitle.PLACE_HOLDER)

    def get_result(self):
        keywords = self._result.get().strip(' \n')
        if keywords == ByTitle.PLACE_HOLDER:
            return ''
        return keywords.lower().split(' ')

    def auto_toggle(self, text):
        """
        If user input something, tick Checkbutton on automatically.
        """
        text = text.strip()
        if len(text) == 0 or text == ByTitle.PLACE_HOLDER:
            self._switch.set(0)
        else:
            self._switch.set(1)
        return True


class ByTags(SearchCondition):
    """
    @return an array of DBRecordTag objects.
        If nothing selected, return [] (aka. empty array)
    """

    def __init__(self, master, *a, **kw):
        self._store = kw.pop('database')
        SearchCondition.__init__(self, master, *a, **kw)
        #
        tk.Checkbutton(self, variable=self._switch).pack(side=tk.LEFT)
        self._tags_string = tk.StringVar()
        self._result = []
        e = tk.Entry(self, textvariable=self._tags_string, state=tk.DISABLED)
        e.pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        jtk.CreateToolTip(e, 'Hierarchically Organized Tags (OR)')
        tk.Button(self, text='...', command=self.open_tag_picker_).pack(side=tk.LEFT)

    def get_result(self):
        return self._result

    def open_tag_picker_(self):
        dlg = TagPickDlg(self, database=self._store, owned=self._result)
        if dlg.show() is False:
            return
        self._result[:] = dlg.result
        self._tags_string.set(','.join(i.name for i in self._result))
        self._switch.set(len(self._result) > 0)


class ByDate(SearchCondition):
    """
    @return tuple(from, to), both 'from' and 'to' are date objects (or None, if not selected).
    """

    TIME_TYPE_CREATE = 0
    TIME_TYPE_MODIFY = 1

    def __init__(self, master, *a, **kw):
        SearchCondition.__init__(self, master, *a, **kw)
        #
        tk.Checkbutton(self, variable=self._switch).pack(side=tk.LEFT)
        #
        frm = tk.LabelFrame(self, text='Type')
        frm.pack(side=tk.LEFT, fill=tk.BOTH, expand=tk.NO, padx=5, pady=5)
        self._time_type = tk.IntVar(value=ByDate.TIME_TYPE_CREATE)
        tk.Radiobutton(frm, text='Create', value=ByDate.TIME_TYPE_CREATE, variable=self._time_type).pack(side=tk.TOP, fill=tk.Y)
        tk.Radiobutton(frm, text='Modify', value=ByDate.TIME_TYPE_MODIFY, variable=self._time_type).pack(side=tk.TOP, fill=tk.Y)
        #
        frm = tk.LabelFrame(self, text='Time')
        frm.pack(side=tk.LEFT, fill=tk.BOTH, expand=tk.YES, padx=5, pady=5)
        # row 1
        row1 = tk.Frame(frm)
        row1.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        self._from, self._to = None, None
        self._date_from = tk.StringVar()
        self._date_from.trace('w', self.from_changed_)
        e = tk.Entry(row1, textvariable=self._date_from)
        e.pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        jtk.MakePlaceHolder(e, "<from what day it was edited?>")
        btn = tk.Button(row1, text='...')
        btn['command'] = lambda: self.open_date_picker_(self._date_from)
        btn.pack(side=tk.LEFT, padx=5)
        # row 2
        row2 = tk.Frame(frm)
        row2.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        self._date_to = tk.StringVar()
        self._date_to.trace('w', self.to_changed_)
        e = tk.Entry(row2, textvariable=self._date_to)
        e.pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        jtk.MakePlaceHolder(e, "<to what day it was edited?>")
        btn = tk.Button(row2, text='...')
        btn['command'] = lambda: self.open_date_picker_(self._date_to)
        btn.pack(side=tk.LEFT, padx=5)

    def open_date_picker_(self, var):
        option = {}
        try:
            tm = var.get()
            tm = datetime.datetime.strptime(tm, DATE_FORMAT)
            if jtk.CalendarDlg.YEAR_FROM <= tm.year <= jtk.CalendarDlg.YEAR_TO:
                option['date'] = datetime.date(year=tm.year, month=tm.month, day=tm.day)
        except ValueError:
            pass
        finally:
            dlg = jtk.CalendarDlg(self, **option)
            dlg.show()
            var.set(str(dlg.date))

    def get_result(self):
        return self._time_type.get(), self._from, self._to

    def from_changed_(self, name, index, mode):
        try:
            tm = self._date_from.get()
            tm = datetime.datetime.strptime(tm, DATE_FORMAT)
            self._from = datetime.date(year=tm.year, month=tm.month, day=tm.day)
            if not self._switch.get():
                self._switch.set(1)
        except ValueError:
            self._from = None
            if self._to is None:
                self._switch.set(0)

    def to_changed_(self, name, index, mode):
        try:
            tm = self._date_to.get()
            tm = datetime.datetime.strptime(tm, DATE_FORMAT)
            self._to = datetime.date(year=tm.year, month=tm.month, day=tm.day)
            if not self._switch.get():
                self._switch.set(1)
        except ValueError:
            self._to = None
            if self._from is None:
                self._switch.set(0)


class ByOrder(SearchCondition):
    def __init__(self, master, *a, **kw):
        SearchCondition.__init__(self, master, *a, **kw)
        tk.Checkbutton(self, variable=self._switch).pack(side=tk.LEFT)
        cb = self.register(self.auto_toggle)
        self._from = tk.StringVar()
        self._to = tk.StringVar()
        e = tk.Entry(self, textvariable=self._from, width=16, validate='key', validatecommand=cb)
        e.pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        jtk.MakePlaceHolder(e, '<Record ID from ?>')
        e = tk.Entry(self, textvariable=self._to, width=16, validate='key', validatecommand=cb)
        e.pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        jtk.MakePlaceHolder(e, '<Record ID to ?>')

    def get_result(self):
        # from
        f = None
        try:
            f = int(self._from.get())
        except ValueError:
            pass
        # to
        t = None
        try:
            t = int(self._to.get())
        except ValueError:
            pass
        return f, t

    def auto_toggle(self):
        results = self.get_result()
        ticked = self._switch.get()
        if not ticked and any(i is not None for i in results):
            self._switch.set(1)
        if ticked and all(i is None for i in results):
            self._switch.set(0)
        return True


class NotePreview:
    LINES_MAX = 15
    LINE_WIDTH = 40

    def __init__(self, master, database, note: jdb.DBRecordDoc):
        self._top = top = tk.Toplevel(master, bd=1, relief=tk.RIDGE)
        top.transient(master)  # floating above master always
        #
        top.update_idletasks()      # according to doc, idle tasks must be done before below function call
        top.overrideredirect(True)  # remove window title bar
        #
        tk.Label(top, text='Title: %s' % note.title).pack(side=tk.TOP, anchor=tk.W)
        #
        tags = ','.join(i.name for i in note.tags)
        tk.Label(top, text='Tags: %s' % tags).pack(side=tk.TOP, anchor=tk.W)
        #
        tk.Label(top, text='Created: %s' % note.date_created).pack(side=tk.TOP, anchor=tk.W)
        #
        tk.Label(top, text='Modified: %s' % note.date_modified).pack(side=tk.TOP, anchor=tk.W)
        #
        tk.Label(top, text='Size: %d B' % note.size).pack(side=tk.TOP, anchor=tk.W)
        #
        content, _ = database.read_doc(note.sn)
        content = json.loads(content).pop("text", '')
        limit = NotePreview.LINE_WIDTH * NotePreview.LINES_MAX
        lines = content[:limit].split('\n')[:NotePreview.LINES_MAX]
        option = {'width': NotePreview.LINE_WIDTH, 'height': NotePreview.LINES_MAX}
        editor = tk.Text(top, **option)
        editor.insert(tk.END, '\n'.join(lines))
        editor.config(state=tk.DISABLED)  # disable editing after loading
        editor.pack(side=tk.TOP, pady=5)
        # we need mouse events, of which <motion> is our interest
        # but we need keyboard focus to be on the Main Dialog
        top.grab_set()
        top.bind('<Motion>', self.check_close_)
        #top.focus_set()
        #
        top.geometry("+%d+%d" % (master.winfo_rootx() + 100, master.winfo_rooty()))
        # detect user 'enter-zone' behavior
        self._been_entered = False

    def check_close_(self, evt):
        x, y = self._top.winfo_rootx(), self._top.winfo_rooty()
        position = (evt.x_root - x, evt.y_root - y)  # in top-level coordinate space
        w, h = self._top.winfo_width(), self._top.winfo_height()
        in_zone = all([0 < position[0] < w, 0 < position[1] < h])
        # only if the mouse enters once then leaves, the preview closes.
        if not self._been_entered:
            if in_zone:
                self._been_entered = True
        elif not in_zone:  # enter and leave
            self._top.destroy()

    def close(self):
        self._top.destroy()


class StatedDoc(jdb.DBRecordDoc):
    """
    除了数据表的记录的原始数据，还保存了附加状态
    """
    def __init__(self, title, text=None, bulk=None, tags=[], date=None, date2=None, sn=0, size=0):
        jdb.DBRecordDoc.__init__(self, title, text, bulk, tags, date, date2, sn, size)
        self._readonly = False

    @property
    def readonly(self):
        return self._readonly

    @readonly.setter
    def readonly(self, value):
        self._readonly = value

    @staticmethod
    def from_db(raw: jdb.DBRecordDoc):
        result = StatedDoc(None)
        result._sn = raw.sn
        result._title = raw.title
        result._text = raw.script
        result._bulk = raw.bulk
        result._tags = raw.tags
        result._date = raw.date_created
        result._date2 = raw.date_modified
        result._size = raw.size
        return result


class OpenDocDlg(jtk.ModalDialog):
    # 8 items per page
    PAGE_NUM = 8
    # 2 sorting methods
    SORT_BY_ID = 0
    SORT_BY_DATE_CREATE = 1
    SORT_BY_DATE_MODIFY = 2
    SORT_BY_SIZE = 3
    SORT_COUNT = 4
    """
    @return a tuple(array of serial number, array of DBRecordDoc, current page)
    """

    class QueryConfig(object):
        def __init__(self):
            self._hits = []
            self._curr_page = 0
            self._sort_states = [False] * OpenDocDlg.SORT_COUNT

        @property
        def hits(self):
            return self._hits

        @hits.setter
        def hits(self, value):
            self._hits[:] = value

        @property
        def page(self):
            return self._curr_page

        @page.setter
        def page(self, value):
            self._curr_page = value

        def sort_state(self, index):
            return self._sort_states[index]

        def sort_switch(self, index):
            self._sort_states[index] = not self._sort_states[index]

        def clear(self):
            del self._hits[:]
            self._curr_page = 0
            self._sort_states[:] = [False] * OpenDocDlg.SORT_COUNT

    def __init__(self, master, *a, **kw):
        self._store = kw.pop('database')
        self._state = kw.pop('state', None)
        if self._state is None:
            self._state = OpenDocDlg.QueryConfig()
        kw['title'] = 'Select Document to Open'
        jtk.ModalDialog.__init__(self, master, *a, **kw)
        # jump to the page of lastly opened time
        if len(self._state.hits) > 0:
            self.jump_page_(self._state.page)
        self._preview = None

    def body(self, master):
        frm = tk.LabelFrame(master, text='Search by:')
        frm.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES, ipadx=5, ipady=5)
        # search conditions
        box = jtk.TabBarFrame(frm, width=70)
        box.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        # 1. search by title
        self._sb_tit = ByTitle(box)
        box.add(self._sb_tit, 'Title')
        # 2. search by tags
        self._sb_tag = ByTags(box, database=self._store)
        box.add(self._sb_tag, 'Tags')
        # 3. search by date
        self._sb_dat = ByDate(box)
        box.add(self._sb_dat, 'Date')
        # 4. search by order
        self._sb_ord = ByOrder(box)
        box.add(self._sb_ord, 'Order')
        # 5. search by content (Because its UI is same with ByTitle, so use ByTitle directly)
        self._sb_txt = ByTitle(box)
        box.add(self._sb_txt, 'Content')
        self._box = box
        # --- results ---
        frm = tk.LabelFrame(master, text='Result:')
        frm.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        #
        self._note_list = ttk.Treeview(frm, columns=['ID', 'Title', 'Date1', 'Date2', 'Size'],
                                       show='headings',  # hide first icon column
                                       height=OpenDocDlg.PAGE_NUM,
                                       selectmode=tk.EXTENDED)  # multiple rows can be selected
        self._note_list.pack(fill=tk.BOTH, expand=tk.YES, padx=5, pady=5)
        self._note_list.bind('<Double-1>', self.ok)
        self._note_list.bind('<Shift_R>', self.ok)
        self._note_list.bind('<space>', self.open_preview_)
        self._note_list.bind(jex.mouse_right_button(), self.open_preview_)
        # <Up> and <Down> is the default key bindings for Treeview
        self._note_list.bind('<Left>', self.jump_prev_)
        self._note_list.bind('<Right>', self.jump_next_)
        #
        self.bind('<Next>', self.loop_tab_next_)
        self.bind('<Prior>', self.loop_tab_prev_)
        #
        default_font = tkFont.Font()
        width = default_font.measure('999')
        self._note_list.column('ID', width=width, minwidth=min(30, width))
        self._note_list.heading('ID', text='ID', command=self.sort_by_id_)
        self._note_list.heading('Title', text='Title')
        width = default_font.measure('9999-99-99')
        self._note_list.column('Date1', width=width, minwidth=width)
        self._note_list.heading('Date1', text='Date Created', command=self.sort_by_date_)
        self._note_list.column('Date2', width=width, minwidth=width)
        self._note_list.heading('Date2', text='Date Modified', command=self.sort_by_date2_)
        width = default_font.measure('9999.99 MB')
        self._note_list.column('Size', width=width, minwidth=width, anchor=tk.E)
        self._note_list.heading('Size', text='Size', command=self.sort_by_size_)

    def apply(self):
        try:
            selected = self._note_list.selection()
            selected = [int(i) + self._state.page * OpenDocDlg.PAGE_NUM for i in selected]
            self.result = (selected, self._state)
        except:
            self.result = None

    def buttonbox(self):
        box = tk.Frame(self)
        #
        tk.Button(box, text='|<<', command=lambda: self.jump_page_(0)).pack(side=tk.LEFT)
        tk.Button(box, text='<-', command=self.jump_prev_).pack(side=tk.LEFT)
        tk.Button(box, text='->', command=self.jump_next_).pack(side=tk.LEFT)
        tk.Button(box, text='>>|', command=lambda: self.jump_page_(self.pages_() - 1)).pack(side=tk.LEFT)
        #
        self._progress = tk.StringVar(value='page number')
        tk.Label(box, textvariable=self._progress).pack(side=tk.LEFT)
        #
        self._btn_search = btn = tk.Button(box, text="Search", command=self.search_)
        btn.pack(side=tk.LEFT)
        tk.Button(box, text="OK", command=self.ok).pack(side=tk.LEFT)
        #
        self.bind("<Return>", self.search_)
        self.bind("<Escape>", self.cancel)
        #
        box.pack()
        return box

    def jump_page_(self, n):
        # update page progress
        self._note_list.delete(*self._note_list.get_children(''))
        start = n * OpenDocDlg.PAGE_NUM
        stop = start + OpenDocDlg.PAGE_NUM
        for i, j in enumerate(self._state.hits[start:stop]):
            self._note_list.insert('', tk.END, iid=str(i), values=[j.sn, j.title, j.date_created, j.date_modified, self.intuitive_nb_str(j.size)])
        if len(self._state.hits) > 0:
            self._note_list.selection_set('0')  # automatically select the 1st one
            self._note_list.focus('0')  # give the 1st one focus (visually)
            self._note_list.focus_set()  # widget get focus to accept '<space>', '<Up>', '<Down>'
        #
        self._progress.set('%d / %d' % (n + 1, self.pages_()))
        self._state.page = n

    def jump_next_(self, evt=None):
        if self._state.page + 1 < self.pages_():
            self.jump_page_(self._state.page + 1)

    def jump_prev_(self, evt=None):
        if self._state.page > 0:
            self.jump_page_(self._state.page - 1)

    def pages_(self):
        total = max(len(self._state.hits), 1)
        return (total - 1) // OpenDocDlg.PAGE_NUM + 1  # [Python 3x] floored divide: "//"

    def search_(self, evt=None):
        conditions = {}
        if self._sb_tit.enabled():
            keywords = self._sb_tit.get_result()
            if len(keywords) > 0:
                keywords[:] = ['"%%%s%%"' % i for i in keywords]
                latter = ' AND title LIKE '.join(keywords)
                conditions['title'] = 'title LIKE %s' % latter
        if self._sb_tag.enabled():
            tags = self._sb_tag.get_result()
            if len(tags) > 0:
                conditions['tags'] = tags
        if self._sb_dat.enabled():
            type_, from_, to_ = self._sb_dat.get_result()
            if from_ is not None:
                conditions['from' if type_ == ByDate.TIME_TYPE_CREATE else 'from2'] = from_
            if to_ is not None:
                conditions['to' if type_ == ByDate.TIME_TYPE_CREATE else 'to2'] = to_
        if self._sb_ord.enabled():
            lower, upper = self._sb_ord.get_result()
            if upper is not None:
                conditions['upper'] = upper
            if lower is not None:
                conditions['lower'] = lower
        if self._sb_txt.enabled():
            keywords = self._sb_txt.get_result()
            if len(keywords) > 0:
                conditions['content'] = keywords
        if len(conditions) == 0:
            self._state.clear()
        else:
            docs = self._store.select_doc(**conditions)
            self._state.hits[:] = [StatedDoc.from_db(i) for i in docs]
        jtk.MessageBubble(self._btn_search, '%d found' % len(self._state.hits))
        self.jump_page_(0)

    def open_preview_(self, evt=None):
        if evt.type == tk.EventType.KeyPress:
            active = self._note_list.focus()
        else:  # tk.EventType.ButtonPress:
            active = self._note_list.identify_row(evt.y)
        if active == '':
            return
        index = self._note_list.index(active)
        index += self._state.page * OpenDocDlg.PAGE_NUM
        if self._preview is not None:
            self._preview.close()
        self._preview = NotePreview(self, database=self._store, note=self._state.hits[index])

    def sort_by_id_(self):
        self._state.sort_switch(OpenDocDlg.SORT_BY_ID)
        self._state.hits.sort(key=lambda i: i.sn, reverse=self._state.sort_state(OpenDocDlg.SORT_BY_ID))
        self.jump_page_(0)

    def sort_by_date_(self):
        self._state.sort_switch(OpenDocDlg.SORT_BY_DATE_CREATE)
        self._state.hits.sort(key=lambda i: i.date_created, reverse=self._state.sort_state(OpenDocDlg.SORT_BY_DATE_CREATE))
        self.jump_page_(0)

    def sort_by_date2_(self):
        self._state.sort_switch(OpenDocDlg.SORT_BY_DATE_MODIFY)
        self._state.hits.sort(key=lambda i: i.date_modified, reverse=self._state.sort_state(OpenDocDlg.SORT_BY_DATE_MODIFY))
        self.jump_page_(0)

    def sort_by_size_(self):
        self._state.sort_switch(OpenDocDlg.SORT_BY_SIZE)
        self._state.hits.sort(key=lambda i: i.size, reverse=self._state.sort_state(OpenDocDlg.SORT_BY_SIZE))
        self.jump_page_(0)

    def loop_tab_next_(self, evt=None):
        tabs = [self._sb_tit, self._sb_tag, self._sb_dat, self._sb_ord, self._sb_txt]
        for i, tab in enumerate(tabs):
            if self._box.active == tab:
                next_tab = (i+1) % len(tabs)
                self._box.switch_tab(tabs[next_tab])
                break

    def loop_tab_prev_(self, evt=None):
        tabs = [self._sb_txt, self._sb_ord, self._sb_dat, self._sb_tag, self._sb_tit]
        for i, tab in enumerate(tabs):
            if self._box.active == tab:
                next_tab = (i+1) % len(tabs)
                self._box.switch_tab(tabs[next_tab])
                break

    def cancel(self, event=None):
        if self._preview is not None:
            self._preview.close()
            self._preview = None
            return
        super().cancel(event)

    @staticmethod
    def intuitive_nb_str(n: int):
        if n < 1024:
            return '{} B'.format(n)
        elif n < 1024 * 1024:
            return '{:.2f} KB'.format(n / 1024)
        else:
            return '{:.2f} MB'.format(n / (1024 * 1024))


class EntryOps:
    @staticmethod
    def select_all(evt):
        w = evt.widget
        if not isinstance(w, tk.Entry):
            return
        w.select_range(0, tk.END)

    @staticmethod
    def jump_to_start(evt):
        w = evt.widget
        if not isinstance(w, tk.Entry):
            return
        w.icursor(0)

    @staticmethod
    def jump_to_end(evt):
        w = evt.widget
        if not isinstance(w, tk.Entry):
            return
        w.icursor(tk.END)

    @staticmethod
    def copy(evt):
        w = evt.widget
        if not isinstance(w, tk.Entry):
            return
        w.event_generate('<<Copy>>')

    @staticmethod
    def cut(evt):
        w = evt.widget
        if not isinstance(w, tk.Entry):
            return
        w.event_generate('<<Cut>>')

    @staticmethod
    def paste(evt):
        w = evt.widget
        if not isinstance(w, tk.Entry):
            return
        w.event_generate('<<Paste>>')


class TipManager(object):
    prefix = 'tip_'

    def __init__(self):
        self._tips = {}
        self._wnd = None

    def insert(self, text, content, start, end, sn=None):
        """
        @param text: tk.Text control
        @param content: string of text
        @param sn: if is None, assigned as ID automatically
        """
        if text not in self._tips:
            self._tips[text] = {}
        if sn is None:
            sn = self.free_index_(text)
        self._tips[text][sn] = content
        name = '%s%d' % (TipManager.prefix, sn)
        text.tag_add(name, start, end)
        text.tag_config(name, background='gray90')  # the bigger number, the lighter gray color
        text.tag_bind(name, '<Enter>', lambda evt, t=text, s=sn: self.schedule_(t, s))
        text.tag_bind(name, '<Leave>', self.unschedule_)

    def free_index_(self, text):
        """
        @return a free index.
        @note: it clears unused strings of text.
        """
        tip_tags = [i for i in text.tag_names() if i.startswith(TipManager.prefix)]
        keys = [TipManager.sn_from_tag(i) for i in tip_tags]
        # clear unused strings
        unused = [i for i in self._tips[text].keys() if i not in keys]
        for i in unused:
            del self._tips[text][i]
        # find the smallest index free to use
        for i, sn in enumerate(self._tips[text].keys()):
            if i < sn:
                return i
        return len(self._tips[text].keys())

    def includes(self, text, index1, index2):
        tip_tags = [i for i in text.tag_names() if i.startswith(TipManager.prefix)]
        hits = []
        for i in tip_tags:
            ranges = text.tag_ranges(i)
            if len(ranges) < 2:  # it's strange that sometimes ranges is empty!
                continue
            if text.compare(ranges[1], '<=', index1):
                continue
            if text.compare(ranges[0], '>=', index2):
                continue
            hits.append((i, ranges))
        return hits

    def schedule_(self, text, sn):
        self._wnd = tk.Toplevel(text)
        self._wnd.wm_overrideredirect(True)  # remove window title bar
        label = tk.Label(self._wnd, text=self._tips[text][sn], justify=tk.LEFT, bg='yellow')
        label.pack(ipadx=5)
        # calculate coordinates
        rx, ry = text.winfo_rootx(), text.winfo_rooty()
        x, y, _, _ = text.bbox(tk.CURRENT)  # mouse cursor
        w, h = label.winfo_reqwidth(), label.winfo_reqheight()
        padding = 20  # keep a minimal distance from screen border
        ox = max(rx + x - w / 2, padding)
        oy = max(ry + y - h, padding)
        nth_screen = math.ceil((rx + x) / text.winfo_screenwidth())  # multi-screen support
        rightmost = nth_screen * text.winfo_screenwidth()
        ox = min(ox, rightmost - padding - w)
        oy = min(oy, text.winfo_screenheight() - padding - h)
        self._wnd.wm_geometry("+%d+%d" % (ox, oy))

    def unschedule_(self, evt=None):
        if self._wnd is None:
            return
        self._wnd.destroy()
        self._wnd = None

    def remove(self, text, name):
        text.tag_unbind(name, '<Enter>')
        text.tag_unbind(name, '<Leave>')
        text.tag_delete(name)
        sn = TipManager.sn_from_tag(name)
        del self._tips[text][sn]

    def get_content(self, text, name):
        sn = TipManager.sn_from_tag(name)
        return self._tips[text][sn]

    def update(self, text, name, content):
        sn = TipManager.sn_from_tag(name)
        self._tips[text][sn] = content

    def export_format(self, text):
        formats = []
        tip_tags = []
        for i in text.tag_names():
            if i.startswith(TipManager.prefix):
                ranges = text.tag_ranges(i)
                if len(ranges) < 2:  # it's strange that sometimes ranges is empty!
                    continue
                tip_tags.append((i, text.index(ranges[0]), text.index(ranges[1])))
        # the purpose of sort is only one: digest comparison
        jex.sort_by_cmp(tip_tags, lambda i, j: -1 if text.compare(i[1], '<', j[1]) else 1)
        for t, s, e in tip_tags:
            txt = self.get_content(text, t)
            formats.append(dict(start=s, end=e, text=txt))
        return formats

    @staticmethod
    def sn_from_tag(name):
        return int(name[len(TipManager.prefix):])


class TipEditDlg(jtk.ModalDialog):
    _placeholder = '<Place something helpful here>'

    def __init__(self, master, *a, **kw):
        """
        keyword parameters:
          sel: the selected characters.
          tip(optional): old tip owned previously.
        @return None: if user clicks "Cancel" button.
                ''(empty str) if user wants to delete this tip.
                other str: it will be your new tip.
        """
        self._sel = kw.pop('sel')
        self._tip = kw.pop('tip', TipEditDlg._placeholder)
        #
        kw['title'] = 'Edit a Tip'
        jtk.ModalDialog.__init__(self, master, *a, **kw)

    def body(self, master):
        tk.Label(master, text=self._sel).pack(side=tk.TOP, fill=tk.X, expand=tk.YES)
        self._text = tk.Text(master, width=80, height=4)
        self._text.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        self._text.insert('1.0', self._tip)
        # make a selection beforehand. So user can easily replace/delete them all
        self._text.tag_add(tk.SEL, '1.0', tk.END)
        return self._text

    def apply(self):
        content = self._text.get('1.0', tk.END)
        content = content.strip()
        if len(content) == 0 or content == TipEditDlg._placeholder:
            self.result = ''  # if user doesn't want any tip, leave it empty
        else:
            self.result = content

    def buttonbox(self):
        box = tk.Frame(self)
        w = tk.Button(box, text="OK", width=10, command=self.ok)
        w.pack(side=tk.LEFT, padx=5, pady=5)
        w = tk.Button(box, text="Cancel", width=10, command=self.cancel)
        w.pack(side=tk.LEFT, padx=5, pady=5)

        self.bind("<Escape>", self.cancel)

        box.pack()
        return box


class DocCopyDlg(jtk.ModalDialog):
    def __init__(self, master, *a, **kw):
        self._storePath = tk.StringVar()
        self._recordIDs = tk.StringVar()
        jtk.ModalDialog.__init__(self, master, *a, **kw)

    def body(self, master):
        frame = tk.Frame(master)
        frame.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        tk.Label(frame, text='Destination:').pack(side=tk.LEFT)
        e1 = tk.Entry(frame, textvariable=self._storePath)
        e1.pack(side=tk.LEFT, expand=tk.YES, fill=tk.X)
        tk.Button(frame, text='Browse', command=self.onclick_browse).pack(side=tk.LEFT)
        frame = tk.Frame(master)
        frame.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        tk.Label(frame, text='Record IDs:').pack(side=tk.LEFT)
        placeholder = '<Separated by comma; Ranged by hyphen>'
        e2 = tk.Entry(frame, textvariable=self._recordIDs, width=len(placeholder))
        e2.pack(side=tk.LEFT, expand=tk.YES, fill=tk.X)
        jtk.MakePlaceHolder(e2, placeholder)
        return e1

    def validate(self):
        database = self._storePath.get()
        records = self.get_record_id()
        return len(database) > 0 and len(records) > 0

    def apply(self):
        database = self._storePath.get()
        records = self.get_record_id()
        self.result = (database, records)

    def onclick_browse(self):
        filename = tkFileDialog.askopenfilename()
        if filename == '':
            return
        self._storePath.set(filename)

    def get_record_id(self):
        records = self._recordIDs.get()
        records = records.split(',')
        record_id = set()
        for i in records:
            try:
                i = i.strip()
                if i.find('-') > 0:
                    pos = i.find('-')
                    start = int(i[:pos])
                    stop = int(i[pos + 1:])
                    # add new range: [start, stop]
                    # +1 to include "stop"
                    record_id = record_id.union(set(range(start, stop + 1)))
                else:
                    record_id.add(int(i))
            except Exception as e:
                print(e)
        return record_id


class DocCompareDlg(jtk.ModalDialog):
    def __init__(self, master, *a, **kw):
        self._storePath = tk.StringVar()
        self._this_database = kw.pop('me')
        jtk.ModalDialog.__init__(self, master, *a, **kw)

    def body(self, master):
        frame = tk.Frame(master)
        frame.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        tk.Label(frame, text='Another:').pack(side=tk.LEFT)
        e1 = tk.Entry(frame, textvariable=self._storePath)
        e1.pack(side=tk.LEFT, expand=tk.YES, fill=tk.X)
        tk.Button(frame, text='Browse', command=self.onclick_browse).pack(side=tk.LEFT)
        tk.Button(frame, text='Compare', command=self.onclick_compare).pack(side=tk.LEFT)
        #
        tk.Label(master, text='Result:').pack(side=tk.TOP, anchor=tk.W)
        frame = tk.Frame(master)
        frame.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        tk.Label(frame, text='this').pack(side=tk.LEFT, anchor=tk.CENTER, fill=tk.BOTH, expand=tk.YES)
        tk.Label(frame, text='that').pack(side=tk.LEFT, anchor=tk.CENTER, fill=tk.BOTH, expand=tk.YES)
        frame = tk.Frame(master)
        frame.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        columns = ['id', 'title']
        font = tkFont.Font()
        dw = max(font.measure(d) for d in '0123456789')
        tv1 = ttk.Treeview(frame, show='headings', height=5, columns=columns, selectmode=tk.BROWSE)
        tv1.pack(side=tk.LEFT, fill=tk.BOTH, expand=tk.YES)
        tv1.column('#1', width=dw*3, anchor=tk.W)
        tv1.heading('#1', text=columns[0])
        tv1.column('#2', width=dw*40, anchor=tk.W)
        tv1.heading('#2', text=columns[1])
        self._tv1 = tv1
        tv2 = ttk.Treeview(frame, show='headings', height=5, columns=columns, selectmode=tk.BROWSE)
        tv2.pack(side=tk.LEFT, fill=tk.BOTH, expand=tk.YES)
        tv2.column('#1', width=dw*3, anchor=tk.W)
        tv2.heading('#1', text=columns[0])
        tv2.column('#2', width=dw*40, anchor=tk.W)
        tv2.heading('#2', text=columns[1])
        self._tv2 = tv2

    def onclick_browse(self):
        filename = tkFileDialog.askopenfilename()
        if filename == '':
            return
        if self._this_database.source == filename:
            tkMessageBox.showerror(MainApp.TITLE, 'Same file!')
            return
        self._storePath.set(filename)

    def onclick_compare(self):
        database = self._storePath.get()
        if not os.path.exists(database):
            return
        if not jdb.DocBase.validate(database):
            tkMessageBox.showerror(MainApp.TITLE, 'Database format is different!')
            return
        this_hashes = self._this_database.get_hashes()
        that_hashes = jdb.DocBase(database).get_hashes()
        h1 = set([d for s, t, d in this_hashes])
        h2 = set([d for s, t, d in that_hashes])
        common = h1.intersection(h2)
        this_docs = [(sn, title) for sn, title, digest in this_hashes if digest not in common]
        that_docs = [(sn, title) for sn, title, digest in that_hashes if digest not in common]
        self._tv1.delete(*self._tv1.get_children())
        for doc in this_docs:
            self._tv1.insert('', tk.END, values=(doc[0], doc[1]))
        self._tv2.delete(*self._tv2.get_children())
        for doc in that_docs:
            self._tv2.insert('', tk.END, values=(doc[0], doc[1]))


class MenuId(IntEnum):
    INVALID = -1

    ROOT_DB = 1
    ROOT_DOC = 2
    ROOT_EDIT = 3

    DATABASE_CLOSE = 2

    DOC_NEW = 0
    DOC_OPEN = 1
    DOC_SAVE = 2
    DOC_CLOSE = 3
    DOC_DELETE = 4
    DOC_EXPORT_HTML = 5
    DOC_COPY_DB = 6
    DOC_COMPARE_DB = 7

    # 数字不连续是因为分隔符的存在
    EDIT_IMAGE = 0
    EDIT_TABLE = 1
    EDIT_UNDERLINE = 3
    EDIT_LIST = 4
    EDIT_SUP = 5
    EDIT_SUB = 6
    EDIT_TIP = 7
    EDIT_CLIPBOARD = 9
    EDIT_READONLY = 10


class RelyItem:
    def __init__(self, w, evt, sid: MenuId = MenuId.INVALID):
        """
        @param w is Tkinter widget, could be menu or button
        @note: if w is a menu, then sid is the index of its sub-menu item.
        """
        self._w = w
        self._c = sid

    def set_state(self, state):
        if self._c > MenuId.INVALID:  # menu item
            self._w.entryconfig(int(self._c), state=state)
        else:  # button
            self._w.config(state=state)


class MainApp(tk.Tk):
    TITLE = 'bitty'
    UNNAMED = 'untitled'
    #
    if jex.isPython3():
        class SAVE(Enum):
            Finish = 0
            FailContent = 1
            FailTitle = 2
    else:
        SAVE = jex.enum1(Finish=0, FailContent=1, FailTitle=2)

    # All text editors are using same font
    DEFAULT_FONT = 'Helvetica' if platform == 'darwin' else '宋体'
    DEFAULT_SIZE = 18
    #
    if jex.isPython3():
        class RELY(Enum):
            DB = 0
            DOC = 1
    else:
        RELY = jex.enum1(DB=0, DOC=1)

    EVENT_DB_EXIST = '<<DBExist>>'  # sent when database is opened / closed.
    EVENT_DOC_EXIST = '<<DocExist>>'  # sent when first document opened / last document closed.

    def __init__(self, *a, **kw):
        tk.Tk.__init__(self, *a, **kw)
        self.init_listeners_()
        self.init_menu_()
        self.init_editor_()
        self.init_status_bar_()
        self.misc_()

    def init_menu_(self):
        menu_bar = tk.Menu(self)
        # database
        menu = tk.Menu(menu_bar, tearoff=0)
        menu.add_command(label='New', command=self.menu_database_new_)
        menu.add_command(label='Open', command=self.menu_database_open_)
        menu.add_command(label='Close', command=self.menu_database_close_)
        self.add_listener(menu, MainApp.EVENT_DB_EXIST, MenuId.DATABASE_CLOSE)
        menu.add_separator()
        menu.add_command(label='Quit', command=self.quit_)
        menu_bar.add_cascade(label='Database', menu=menu)
        # doc
        menu = tk.Menu(menu_bar, tearoff=0)
        menu.add_command(label='New', command=self.menu_doc_new_)
        self.add_listener(menu, MainApp.EVENT_DB_EXIST, MenuId.DOC_NEW)
        menu.add_command(label='Open', command=self.menu_doc_open_)
        self.add_listener(menu, MainApp.EVENT_DB_EXIST, MenuId.DOC_OPEN)
        menu.add_command(label='Save', command=self.menu_doc_save_)
        self.add_listener(menu, MainApp.EVENT_DOC_EXIST, MenuId.DOC_SAVE)
        menu.add_command(label='Close', command=self.menu_doc_close_)
        self.add_listener(menu, MainApp.EVENT_DOC_EXIST, MenuId.DOC_CLOSE)
        menu.add_command(label='Delete', command=self.menu_doc_delete_)
        self.add_listener(menu, MainApp.EVENT_DOC_EXIST, MenuId.DOC_DELETE)
        menu.add_command(label='Export to HTML', command=self.doc_export_html_)
        self.add_listener(menu, MainApp.EVENT_DOC_EXIST, MenuId.DOC_EXPORT_HTML)
        menu.add_command(label='Copy to Other DB', command=self.doc_copy_elsewhere_)
        self.add_listener(menu, MainApp.EVENT_DB_EXIST, MenuId.DOC_COPY_DB)
        menu.add_command(label='Compare to Other DB', command=self.doc_compare)
        self.add_listener(menu, MainApp.EVENT_DB_EXIST, MenuId.DOC_COMPARE_DB)
        menu_bar.add_cascade(label='Document', menu=menu)
        self.add_listener(menu_bar, MainApp.EVENT_DB_EXIST, MenuId.ROOT_DOC)
        # edit
        menu = tk.Menu(menu_bar, tearoff=0)
        menu.add_command(label='Insert Image File', command=self.edit_insert_image_)
        self.add_listener(menu, MainApp.EVENT_DOC_EXIST, MenuId.EDIT_IMAGE)
        menu.add_command(label='Insert Text Table', command=self.edit_insert_table_)
        self.add_listener(menu, MainApp.EVENT_DOC_EXIST, MenuId.EDIT_TABLE)
        menu.add_separator()  # separator holds one place (index 2) in menu
        menu.add_command(label='Make Underline', command=self.edit_underline_)
        self.add_listener(menu, MainApp.EVENT_DOC_EXIST, MenuId.EDIT_UNDERLINE)
        menu.add_command(label='Make List', command=self.edit_mark_list_)
        self.add_listener(menu, MainApp.EVENT_DOC_EXIST, MenuId.EDIT_LIST)
        menu.add_command(label='Make Superscript', command=self.edit_make_superscript_)
        self.add_listener(menu, MainApp.EVENT_DOC_EXIST, MenuId.EDIT_SUP)
        menu.add_command(label='Make Subscript', command=self.edit_make_subscript_)
        self.add_listener(menu, MainApp.EVENT_DOC_EXIST, MenuId.EDIT_SUB)
        menu.add_command(label='Edit a Tip', command=self.edit_a_tip_)
        self.add_listener(menu, MainApp.EVENT_DOC_EXIST, MenuId.EDIT_TIP)
        menu.add_separator()
        menu.add_command(label='Copy from Clipboard', command=self.copy_from_clipboard_)
        self.add_listener(menu, MainApp.EVENT_DOC_EXIST, MenuId.EDIT_CLIPBOARD)
        self._doc_readonly = tk.BooleanVar(value=0)
        menu.add_checkbutton(label='Readonly', onvalue=1, offvalue=0, variable=self._doc_readonly, command=self.toggle_doc_readonly_)
        self.add_listener(menu, MainApp.EVENT_DOC_EXIST, MenuId.EDIT_READONLY)
        menu_bar.add_cascade(label='Edit', menu=menu)
        self.add_listener(menu_bar, MainApp.EVENT_DB_EXIST, MenuId.ROOT_EDIT)
        # help
        menu = tk.Menu(menu_bar, tearoff=0)
        menu.add_command(label='About', command=self.menu_help_about_)
        menu_bar.add_cascade(label='Help', menu=menu)
        #
        self.config(menu=menu_bar)

    def init_editor_(self):
        toolbar = tk.Frame(self.master, bd=1, relief=tk.RAISED)
        toolbar.pack(side=tk.TOP, anchor=tk.W)
        #
        im = Image.open('toolbar.jpg')
        #
        n = 0
        ico = ImageTk.PhotoImage(im.crop((0, 32 * n, 31, 32 * (n + 1) - 1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.menu_doc_new_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Create a New Document')
        self.add_listener(btn, MainApp.EVENT_DB_EXIST)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32 * n, 31, 32 * (n + 1) - 1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.menu_doc_open_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Open a Document')
        self.add_listener(btn, MainApp.EVENT_DB_EXIST)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32 * n, 31, 32 * (n + 1) - 1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.menu_doc_save_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Save Current Document')
        self.add_listener(btn, MainApp.EVENT_DOC_EXIST)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32 * n, 31, 32 * (n + 1) - 1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.menu_doc_close_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Close Current Document')
        self.add_listener(btn, MainApp.EVENT_DOC_EXIST)
        #
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32 * n, 31, 32 * (n + 1) - 1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.edit_insert_image_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Insert Image File')
        self.add_listener(btn, MainApp.EVENT_DOC_EXIST)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32 * n, 31, 32 * (n + 1) - 1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.edit_insert_table_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Insert Text Table')
        self.add_listener(btn, MainApp.EVENT_DOC_EXIST)
        #
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32 * n, 31, 32 * (n + 1) - 1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.edit_underline_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Format: Underline')
        self.add_listener(btn, MainApp.EVENT_DOC_EXIST)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32 * n, 31, 32 * (n + 1) - 1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.edit_mark_list_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Format: List')
        self.add_listener(btn, MainApp.EVENT_DOC_EXIST)
        self.add_listener(btn, MainApp.EVENT_DOC_EXIST)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32 * n, 31, 32 * (n + 1) - 1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.edit_code_snippet_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Format: Code Snippet')
        self.add_listener(btn, MainApp.EVENT_DOC_EXIST)
        #
        n += 2
        ico = ImageTk.PhotoImage(im.crop((0, 32 * n, 31, 32 * (n + 1) - 1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.edit_a_tip_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Edit a Tip')
        self.add_listener(btn, MainApp.EVENT_DOC_EXIST)
        #
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32 * n, 31, 32 * (n + 1) - 1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.menu_edit_find_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Find and Replace')
        self.add_listener(btn, MainApp.EVENT_DOC_EXIST)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32 * n, 31, 32 * (n + 1) - 1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.menu_doc_attr_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Document Title and Tags')
        self.add_listener(btn, MainApp.EVENT_DOC_EXIST)
        #
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32 * n, 31, 32 * (n + 1) - 1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.menu_doc_delete_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Delete Current Document')
        self.add_listener(btn, MainApp.EVENT_DOC_EXIST)
        #
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        #
        fonts = tkFont.families(self)
        if MainApp.DEFAULT_FONT not in fonts:
            MainApp.DEFAULT_FONT = fonts[0]
        self._font_family = tk.StringVar(value=MainApp.DEFAULT_FONT)
        tk.OptionMenu(toolbar, self._font_family, *fonts).pack(side=tk.LEFT)
        self._font_size = tk.StringVar(value=MainApp.DEFAULT_SIZE)
        box = tk.Spinbox(toolbar, from_=10, to=36, increment=1, textvariable=self._font_size, width=3)
        box.pack(side=tk.LEFT)
        jtk.CreateToolTip(box, 'Change Document Font Size')
        self.add_listener(box, MainApp.EVENT_DOC_EXIST)
        self._font_family.trace('w', lambda name, index, mode: self.font_changed_())
        self._font_size.trace('w', lambda name, index, mode: self.font_changed_())
        #
        self._search = jtk.SearchBar(self)
        #
        im.close()
        self._font = tkFont.Font(family=MainApp.DEFAULT_FONT, size=MainApp.DEFAULT_SIZE)
        editor = jtk.MultiTabEditor(self, font=self._font.copy())
        editor.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        editor.bind(jtk.TabBarFrame.EVENT_TAB_SWITCH, self.on_tab_switched_)
        self._editor = editor

    def init_status_bar_(self):
        sub = tk.Frame(self)
        sub.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=tk.NO)
        w = ttk.Sizegrip(sub)
        w.pack(side=tk.RIGHT, fill=tk.BOTH, expand=tk.NO)

    def menu_database_new_(self):
        filename = tkFileDialog.asksaveasfilename(defaultextension='.sqlite3')
        if filename == '':
            return
        if os.path.exists(filename):
            tkMessageBox.showinfo(MainApp.TITLE, 'Please delete it in File Explorer')
            return
        self._store = jdb.DocBase.create_db(filename)
        self._last_search = None
        self.event_generate(MainApp.EVENT_DB_EXIST, state=1)
        self.title('[%s] %s' % (MainApp.TITLE, os.path.basename(filename)))

    def menu_database_open_(self):
        option = {'filetypes': [('SQLite3 File', ('*.db3', '*.s3db', '*.sqlite3', '*.sl3')),
                                ('All Files', ('*.*',))]}
        filename = tkFileDialog.askopenfilename(**option)
        if filename == '':
            return
        # if same database, ignore
        if self._store is not None and self._store.source == filename:
            return
        # if unknown database, ignore
        if not jdb.DocBase.validate(filename):
            tkMessageBox.showerror(MainApp.TITLE, 'Wrong database format')
            return
        if not self.menu_database_close_():
            return
        self._store = jdb.DocBase(filename)
        self._last_search = None
        self.event_generate(MainApp.EVENT_DB_EXIST, state=1)
        self.title('[%s] %s' % (MainApp.TITLE, os.path.basename(filename)))

    def menu_database_close_(self):
        if self._store is None:
            return True
        if any(e.modified() for e in self._editor.iter_tabs()):
            choice = tkMessageBox.askyesnocancel(MainApp.TITLE, 'Wanna SAVE everything before closing database?')
            if choice is None:  # cancel
                return False
            if choice is True:
                for e in self._editor.iter_tabs():
                    if e.modified():
                        self.save_(e)
        self._editor.close_all()
        self._notes.clear()
        self._store.close()
        self._store = None
        self.event_generate(MainApp.EVENT_DOC_EXIST, state=0)
        self.event_generate(MainApp.EVENT_DB_EXIST, state=0)
        self.title(MainApp.TITLE)
        return True

    def quit_(self):
        if self._editor.active and \
                not tkMessageBox.askokcancel(MainApp.TITLE, 'Are you sure to QUIT?'):
            return
        if not self.menu_database_close_():
            return
        self.destroy()

    def menu_doc_new_(self, evt=None):
        editor = self._editor.new_editor(MainApp.UNNAMED)
        self.config_core(editor)
        self._editor.bind(jtk.TabBarFrame.EVENT_TAB_CLOSED, lambda e: self.on_tab_closed(editor))
        editor.monitor_change()
        self._editor.set_active(editor)
        if self._editor.count() == 1:
            self.event_generate(MainApp.EVENT_DOC_EXIST, state=1)

    def menu_doc_open_(self, evt=None):
        dlg = OpenDocDlg(self, database=self._store, state=self._last_search)
        if dlg.show() is False:
            return
        indices, self._last_search = dlg.result
        opened = {n: e for e, n in self._notes.items()}
        for i in indices:
            note = self._last_search.hits[i]
            # self._last_search.hits may contains the same doc to the ones in self._notes.
            # we replace the new doc with the old one, which has newer digests.
            for old_note in opened:
                if old_note.sn == note.sn and old_note != note:
                    self._last_search.hits[i] = old_note
                    note = old_note
                    break
            # activate the editor opened previously
            if note in opened:
                self._editor.set_active(opened[note])
                continue
            # if not opened yet
            editor = self._editor.new_editor(note.title)
            self.config_core(editor)
            self._editor.bind(jtk.TabBarFrame.EVENT_TAB_CLOSED, lambda e: self.on_tab_closed(editor))
            self._editor.set_active(editor)
            self.load_content_(editor, note)
            editor.monitor_change()
            self._notes[editor] = note
            #
            if self._editor.count() == 1:
                self.event_generate(MainApp.EVENT_DOC_EXIST, state=1)

    def menu_doc_save_(self, evt=None):
        editor = self._editor.active
        if not editor.modified():
            return
        self.save_(editor)

    def save_(self, editor):
        errors = set()
        try:
            record = self._notes[editor]
            record.date_modified = datetime.date.today()
        except KeyError:
            title = self._editor.get_caption(editor)
            record = StatedDoc(title)
        #
        # specify tags / title / date
        if MainApp.unnamed(record.title) or len(record.tags) == 0:
            dlg = DocPropertyDlg(self, database=self._store, record=record)
            dlg.show()
            if MainApp.unnamed(record.title):
                errors.add(MainApp.SAVE.FailTitle)
            if MainApp.SAVE.FailTitle not in errors:
                self._editor.set_caption(editor, record.title)
        #
        textual, binary = self.collect_content_(editor.core())
        if len(textual) == 0:
            errors.add(MainApp.SAVE.FailContent)
        #
        if MainApp.SAVE.FailContent in errors:
            return errors
        #
        # save everything to database
        record.bulk = binary
        record.script = json.dumps(textual)
        if record.fragile:
            self._store.insert_doc(record)
            self._notes[editor] = record
        else:
            self._store.update_doc(record)
        editor.on_saved()
        errors.add(MainApp.SAVE.Finish)
        return errors

    def menu_doc_close_(self, evt=None):
        editor = self._editor.active
        if editor.modified():
            choice = tkMessageBox.askyesnocancel(MainApp.TITLE, 'Wanna SAVE changes before closing doc?')
            if choice is None:  # cancel
                return
            if choice is True:
                self.save_(editor)
        self._editor.remove(editor)
        self._notes.pop(editor, None)
        if self._editor.active is None:
            self.event_generate(MainApp.EVENT_DOC_EXIST, state=0)
            self._search.pack_forget()

    def menu_doc_delete_(self):
        editor = self._editor.active
        caption = self._editor.get_caption(editor)
        if not tkMessageBox.askokcancel(MainApp.TITLE, 'Do you really want to delete\n"%s"?' % caption):
            return
        if editor in self._notes:
            note = self._notes.pop(editor)
            if self._store.delete_doc(note.sn) and note in self._last_search.hits:
                self._last_search.hits.remove(note)
        self._editor.remove(editor)
        if self._editor.active is None:
            self.event_generate(MainApp.EVENT_DOC_EXIST, state=0)

    def menu_help_about_(self):
        msg = '''
It's an Electrical Diary app.
You can write everything here in daily life.

Chinese saying: rotten pencil surpasses smart head.
It's more and more obvious when I get old.

Finished by "Jia xiao dong" on Apr 21, 2019,
At the age of 40.
'''
        tkMessageBox.showinfo(MainApp.TITLE, msg)

    def misc_(self):
        self.title(MainApp.TITLE)
        self.protocol('WM_DELETE_WINDOW', self.quit_)
        self._store = None
        self._notes = {}  # each editor-tab corresponds to a note object
        self._last_search = None
        self._tip_mgr = TipManager()
        # lock several widgets until you open a database.
        self.event_generate(MainApp.EVENT_DB_EXIST, state=0)
        self.event_generate(MainApp.EVENT_DOC_EXIST, state=0)
        #
        # enhance tk.Entry with more hot keys
        self.bind_class('Entry', '<Control-a>', EntryOps.select_all)
        self.bind_class('Entry', '<Control-A>', EntryOps.select_all)
        self.bind_class('Entry', '<Control-Left>', EntryOps.jump_to_start)
        self.bind_class('Entry', '<Control-Right>', EntryOps.jump_to_end)
        self.bind_class('Entry', '<Control-C>', EntryOps.copy)
        self.bind_class('Entry', '<Control-X>', EntryOps.cut)
        self.bind_class('Entry', '<Control-V>', EntryOps.paste)
        #
        jdb.DocBase.assign_finder(self.find_words)

    def menu_doc_attr_(self):
        editor = self._editor.active
        try:
            record = self._notes[editor]
        except KeyError:
            title = self._editor.get_caption(editor)
            record = StatedDoc(title)
        #
        dlg = DocPropertyDlg(self, database=self._store, record=record)
        if dlg.show() is False:
            return
        self._editor.set_caption(editor, record.title)
        editor.on_modified()  # add a flag besides title as an alert
        if not editor in self._notes:
            self._notes[editor] = record

    @staticmethod
    def unnamed(title):
        parts = title.split('_')
        if len(parts) > 2:  # unknown format
            return False
        if parts[0] == MainApp.UNNAMED:
            if len(parts) == 1:  # option 1: 'untitled'
                return True
            if parts[2].isdigit():  # option 2: 'untitled-2'
                return True
        return False

    def menu_edit_find_(self, evt=None):
        editor = self._editor.active
        if self._search.winfo_ismapped():
            self._search.detach()
            self._search.pack_forget()
        else:
            shift_pressed = (evt and (evt.state & 0x0001))
            self._search.attach(editor.core(), shift_pressed)
            self._search.pack(before=self._editor, side=tk.TOP, anchor=tk.W, fill=tk.X)

    def on_tab_switched_(self, evt):
        if self._search.winfo_ismapped():
            self._search.detach()
            self._search.attach(self._editor.active.core())

        # current font settings updated to panel
        if self._editor.active is not None:
            editor = self._editor.active
            core = editor.core()
            font = tkFont.Font(font=core['font'])
            family = self._font_family.get()
            size = int(self._font_size.get())
            if font.cget('family') != family:
                self._font_family.set(font.cget('family'))
            if font.cget('size') != size:
                self._font_size.set(font.cget('size'))
            #
            if editor in self._notes:
                ro = self._notes[editor].readonly
                self._doc_readonly.set(ro)
                core['state'] = tk.DISABLED if ro else tk.NORMAL
            else:
                self._doc_readonly.set(False)  # 未保存的文档永远都可以编辑

    def font_changed_(self):
        family = self._font_family.get()
        size = int(self._font_size.get())
        changed = False
        try:
            editor = self._editor.active
            core = editor.core()
            font = tkFont.Font(font=core['font'])
            if font.cget('family') != family:
                font.config(family=family)
                changed = True
            if font.cget('size') != size:
                font.config(size=size)
                changed = True
            if changed:
                core.config(font=font)
                editor.on_modified()
        except Exception as e:
            pass

    def init_listeners_(self):
        self._relied = {}
        self.bind(MainApp.EVENT_DB_EXIST, self.notify_db_ops_)
        self.bind(MainApp.EVENT_DOC_EXIST, self.notify_doc_ops_)
        #
        if jex.is_macos():
            self.bind('<Command-O>', lambda e: self.menu_database_open_())
        elif jex.is_win():
            self.bind('<Control-O>', lambda e: self.menu_database_open_())

    def add_listener(self, wgt, evt, sid: MenuId = MenuId.INVALID):
        """
        @param wgt: widget.
        @param evt: event.
        @param sid: if wgt is a menu, then sid is the index of its sub-menu item. Otherwise it's meaningless.
        """
        item = RelyItem(wgt, evt, sid)
        if evt in self._relied:
            self._relied[evt].append(item)
        else:
            self._relied[evt] = [item]

    def notify_db_ops_(self, evt):
        state = tk.NORMAL if evt.state else tk.DISABLED
        for w in self._relied[MainApp.EVENT_DB_EXIST]:
            w.set_state(state)
        # map(lambda w: w.set_state(state), self._relied[MainApp.EVENT_DB_EXIST])
        #
        optional = 'Command' if jex.is_macos() else 'Control'
        hotkeys = {'n': self.menu_doc_new_,
                   'o': self.menu_doc_open_,
                   'w': self.menu_doc_close_}
        if evt.state:
            for k, f in hotkeys.items():
                self.bind(f'<{optional}-{k}>', f)
        else:
            for k in hotkeys.keys():
                self.unbind(k)

    def notify_doc_ops_(self, evt):
        state = tk.NORMAL if evt.state else tk.DISABLED
        for w in self._relied[MainApp.EVENT_DOC_EXIST]:
            w.set_state(state)
        # map(lambda w: w.set_state(state), self._relied[MainApp.EVENT_DOC_EXIST])
        #
        if evt.state:
            self.bind('<Control-s>', self.menu_doc_save_)
            self.bind('<Control-S>', self.menu_doc_save_)
            self.bind('<Control-f>', self.menu_edit_find_)
            self.bind('<Control-F>', self.menu_edit_find_)
        else:
            self.unbind('<Control-s>')
            self.unbind('<Control-S>')
            self.unbind('<Control-f>')
            self.unbind('<Control-F>')

    def edit_underline_(self):
        self.toggle_format_('underline')

    def edit_mark_list_(self):
        TAG = 'list'
        try:
            editor = self._editor.active
            core = editor.core()
            # 1. check if current line is list.
            sel_range = core.tag_ranges(tk.SEL)
            if len(sel_range) == 0:
                sel_range = (tk.INSERT, tk.INSERT)
            idx_head1 = core.index('%s linestart' % sel_range[0])
            idx_last1 = core.index('%s lineend+1c' % sel_range[1])  # '+1c' for '\n'
            it = iter(core.tag_ranges(TAG))
            fully_included = False
            for s in it:
                e = it.next()
                idx_head2 = core.index('%s linestart' % s)
                idx_last2 = core.index('%s lineend+1c' % e)
                if core.compare(idx_head2, '<=', idx_head1) and core.compare(idx_last2, '>=', idx_last1):
                    fully_included = True
                    break
            # 2. If so, deactivate it to normal text. If not, make it so.
            if fully_included:
                core.tag_remove(TAG, idx_head1, idx_last1)
            else:
                core.tag_add(TAG, idx_head1, idx_last1)
            # 3. need saving
            editor.on_modified()
        except Exception as e:
            print('Error: %s' % e)

    def edit_code_snippet_(self):
        try:
            editor = self._editor.active
            core = editor.core()
            sel_range = core.tag_ranges(tk.SEL)
            if len(sel_range) == 0:
                return
            # select whole line
            sel_range = (core.index(f'{sel_range[0]} linestart'), core.index(f'{sel_range[1]} +1 lines linestart'))
            if len(core.get(sel_range[1])) == 0:
                core.insert(tk.END, '\n')
            core.tag_remove(tk.SEL, '1.0', tk.END)  # unselect text to avoid accidental deletion
            #
            fully_included = False
            it = iter(core.tag_ranges('code'))
            for s in it:
                e = next(it)
                if core.compare(s, '<=', sel_range[0]) and core.compare(e, '>=', sel_range[1]):
                    fully_included = True
                    break
            #
            if fully_included:
                core.tag_remove('code', *sel_range)
            else:
                core.tag_add('code', *sel_range)
            editor.on_modified()
        except Exception as e:
            print('Error: %s' % e)

    def edit_make_superscript_(self):
        self.toggle_format_('sup', 'sub')

    def edit_make_subscript_(self):
        self.toggle_format_('sub', 'sup')

    def toggle_format_(self, tag, conflict=None):
        try:
            editor = self._editor.active
            core = editor.core()
            # 1. check
            sel_range = core.tag_ranges(tk.SEL)
            if len(sel_range) == 0:
                sel_range = (core.index(tk.INSERT), core.index('%s+1c' % tk.INSERT))
            it = iter(core.tag_ranges(tag))
            fully_included = False
            for s in it:
                e = next(it)
                if core.compare(s, '<=', sel_range[0]) and core.compare(e, '>=', sel_range[1]):
                    fully_included = True
                    break
            # 2. If so, deactivate it to normal text. If not, make it so.
            if fully_included:
                core.tag_remove(tag, *sel_range)
            else:
                if conflict is not None:
                    core.tag_remove(conflict, *sel_range)
                core.tag_add(tag, *sel_range)
            # 3. need saving
            editor.on_modified()
        except Exception as e:
            print('Error: %s' % e)

    def edit_insert_image_(self):
        try:
            s = self.clipboard_get()
            root = json.loads(s)
            bitty_obj = root.pop("jxd_bitty")
            if bitty_obj['format'] != 'image':
                raise
            image_bytes = bitty_obj['data']
            image_bytes = image_bytes.encode('utf8')
            image_bytes = base64.urlsafe_b64decode(image_bytes)
            image_ext = bitty_obj['ext']
            editor = self._editor.active
            core = editor.core()
            image = jtk.ImageBox(core, image=io.BytesIO(image_bytes), ext=image_ext)
            core.window_create(tk.INSERT, window=image)
        except Exception as e:
            extensions = tuple(Image.registered_extensions().keys())
            images = tkFileDialog.askopenfilename(filetypes=[('Image File', extensions)], multiple=True)
            if len(images) == 0:
                return
            editor = self._editor.active
            core = editor.core()
            if len(images) == 1:
                with open(images[0], 'rb') as fi:
                    image = jtk.ImageBox(core, image=io.BytesIO(fi.read()), ext=os.path.splitext(images[0])[1])
                    core.window_create(tk.INSERT, window=image)
            else:
                # a hidden trick: copy start-number from clipboard
                try:
                    start = int(self.clipboard_get())
                except:
                    start = 0
                #
                for i, each in enumerate(images):
                    with open(each, 'rb') as fi:
                        core.insert(tk.INSERT, '\n%d\n' % (i + start + 1))
                        image = jtk.ImageBox(core, image=io.BytesIO(fi.read()), ext=os.path.splitext(each)[1])
                        core.window_create(tk.INSERT, window=image)
        editor.on_modified()

    def edit_insert_table_(self):
        try:
            ts = self.clipboard_get()
            table = json.loads(ts)
        except Exception as e:
            table = [[{"text": "single-click"}, {"text": "to select"}, {"text": "table cell"}],
                     [{"text": "double-click"}, {"text": "to edit"}, {"text": "text"}],
                     [{"text": "control-enter"}, {"text": "to finish"}, {"text": "input"}]]
        finally:
            editor = self._editor.active
            font = tkFont.Font(font=editor.core()['font'])
            w = jtk.TextTableBox(editor.core(), table=table, font=font)
            editor.core().window_create(tk.INSERT, window=w)
            editor.on_modified()

    def doc_export_html_(self):
        # TODO: export one doc to HTML
        pass

    def doc_copy_elsewhere_(self):
        dlg = DocCopyDlg(self)
        if dlg.show() is False:
            return
        database, records = dlg.result
        if not jdb.DocBase.validate(database):
            tkMessageBox.showerror(MainApp.TITLE, 'Database format is different!')
            return
        num = self._store.copy_docs(records, database)
        quiz = 'records are duplicated to'
        tkMessageBox.showinfo(MainApp.TITLE, '%d %s\n%s.' % (num, quiz, os.path.basename(database)))

    def doc_compare(self):
        dlg = DocCompareDlg(self, me=self._store)
        dlg.show()

    def config_core(self, editor):
        text = editor.core()
        font = tkFont.Font(font=text['font'])
        text.tag_config('underline', underline=1)
        text.tag_config('list', lmargin1=12, lmargin2=12)  # 12 pixels, for list
        text.tag_config('code', background='black', foreground='white')
        #
        height = font.metrics("linespace")
        text.tag_config('sup', offset=height / 3)
        text.tag_config('sub', offset=-height / 3)
        #
        font_different = False
        setting_font_family = self._font_family.get()
        setting_font_size = self._font_size.get()
        if font.cget('family') != setting_font_family:
            font.config(family=setting_font_family)
            font_different = True
        if font.cget('size') != setting_font_size:
            font.config(size=setting_font_size)
            font_different = True
        if font_different:
            text.config(font=font)

    def copy_from_clipboard_(self):
        editor = self._editor.active
        content = editor.clipboard_get()
        content = '\n'.join(content.splitlines())
        editor.core().insert(tk.INSERT, content)
        editor.core().see(tk.INSERT)

    def toggle_doc_readonly_(self):
        editor = self._editor.active
        if editor not in self._notes:
            self._doc_readonly.set(False)
            return
        doc = self._notes[editor]
        doc.readonly = not doc.readonly
        # 1. UI: menu checkbox
        self._doc_readonly.set(doc.readonly)
        # 2. UI control: disabled
        editor.core()['state'] = tk.DISABLED if doc.readonly else tk.NORMAL
        # 3. UI control's children
        for table in self.all_custom_windows(editor.core(), jtk.TextTableBox):
            table.readonly = doc.readonly

    def edit_a_tip_(self):
        editor = self._editor.active
        core = editor.core()
        target_tip = None
        sel_range = core.tag_ranges(tk.SEL)
        if len(sel_range) == 0:  # user doesn't select anything, try neighboring old tip
            tags = core.tag_names('%s-1c' % tk.INSERT)  # try left neighbor at first
            tags = [i for i in tags if i.startswith(TipManager.prefix)]
            if len(tags) > 0:
                target_tip = tags[0]
                sel_range = tip_range = core.tag_ranges(target_tip)
            else:
                tags = core.tag_names('%s+1c' % tk.INSERT)  # then try right neighbor
                tags = [i for i in tags if i.startswith(TipManager.prefix)]
                if len(tags) > 0:
                    target_tip = tags[0]
                    sel_range = tip_range = core.tag_ranges(target_tip)
                else:
                    tkMessageBox.showerror(MainApp.TITLE, 'Select a part of text before adding a tip.')
                    return
        if target_tip is None:  # user makes a selection
            tips = self._tip_mgr.includes(core, *sel_range)
            tips_nb = len(tips)
            if tips_nb > 1:
                tkMessageBox.showerror(MainApp.TITLE, 'You cannot select more than 1 tip.')
                return
            if tips_nb == 0:  # new tip
                dlg = TipEditDlg(self, sel=core.get(*sel_range))
                if dlg.show() and len(dlg.result) > 0:
                    self._tip_mgr.insert(core, dlg.result, *sel_range)
                    editor.on_modified()
                return
            target_tip, tip_range = tips[0]
        #
        # edit old tip / delete old tip
        text = core.get(*sel_range)
        content = self._tip_mgr.get_content(core, target_tip)
        dlg = TipEditDlg(self, sel=text, tip=content)
        if dlg.show() is False:  # user cancels
            return
        if len(dlg.result) == 0:  # delete tip
            if not tkMessageBox.askyesno(MainApp.TITLE, 'Are you sure to delete it?'):
                return
            self._tip_mgr.remove(core, target_tip)
            editor.on_modified()
        else:  # update old tip
            tip_different = (dlg.result != content)
            if tip_different:
                self._tip_mgr.update(core, target_tip, dlg.result)
            range_different = any(core.compare(sel_range[i], '!=', tip_range[i]) for i in range(2))
            if range_different:
                core.tag_remove(target_tip, *tip_range)
                core.tag_add(target_tip, *sel_range)
            if any([tip_different, range_different]):
                editor.on_modified()

    def collect_content_(self, text):
        """
        @param text: tk.Text widget.
        @return tuple(textual_data, binary_data)
        """
        content = text.get('1.0', tk.END).splitlines()
        #
        textual = {}
        #
        windows = self.all_custom_windows(text)
        #
        # Use "?" as placeholder which will be replaced by genuine widget when loading from
        # database in future. With the help of a placeholder, it's easy to insert window to
        # tk.Text by original position.
        windows = [w for w in windows if isinstance(w, jtk.StorageMixin)]
        jex.sort_by_cmp(windows, lambda i, j: -1 if text.compare(i, '<', j) else 1)
        for w in windows:
            row, col = text.index(w).split('.')
            row, col = int(row) - 1, int(col)
            content[row] = '%s?%s' % (content[row][:col], content[row][col:])
        # 1. text
        content = [i.rstrip() for i in content]  # delete redundant trailing spaces
        textual["text"] = '\n'.join(content)
        # 2. font
        font = tkFont.Font(font=text['font'])
        font_spec = {'family': font['family'], 'size': font['size']}
        textual['font'] = font_spec
        # 2. images (their binary data is separated to variable 'binary')
        buf = io.BytesIO()
        jfp = jex.FilePile(buf, 'w')
        images = []
        for i, w in enumerate([w for w in windows if isinstance(w, jtk.ImageBox)]):
            pos = text.index(w)
            data, scale, ext = w.output()
            image_name = '%s%s' % (i, ext)
            jfp.append(image_name, data)
            images.append(dict(name=image_name, pos=pos, scale=scale))
        jfp.close()
        if len(images) > 0:
            textual["image"] = images
        binary = buf.getvalue()
        # even if buffer is empty, it still contains magic head bytes
        if len(binary) == len(jex.FilePile.MAGIC_HEAD):
            binary = b''
        # 3. tables
        tables = []
        for w in [w for w in windows if isinstance(w, jtk.TextTableBox)]:
            tables.append(dict(pos=text.index(w), specs=w.output()))
        if len(tables) > 0:
            textual["table"] = tables
        # 4. underlines
        it = iter(text.tag_ranges('underline'))
        underlines = ['%s %s' % (str(s), str(next(it))) for s in it]
        if len(underlines) > 0:
            textual["underline"] = underlines
        # 5. lists
        it = iter(text.tag_ranges('list'))
        lists = ['%s %s' % (str(s), str(next(it))) for s in it]
        if len(lists) > 0:
            textual['list'] = lists
        # 6. superscription
        it = iter(text.tag_ranges('sup'))
        sups = ['%s %s' % (str(s), str(next(it))) for s in it]
        if len(sups) > 0:
            textual['sup'] = sups
        # 7. subscription
        it = iter(text.tag_ranges('sub'))
        subs = ['%s %s' % (str(s), str(next(it))) for s in it]
        if len(subs) > 0:
            textual['sub'] = subs
        # 8. code
        it = iter(text.tag_ranges('code'))
        subs = ['%s %s' % (str(s), str(next(it))) for s in it]
        if len(subs) > 0:
            textual['code'] = subs
        # 9. tips
        tips = self._tip_mgr.export_format(text)
        if len(tips) > 0:
            textual['tip'] = tips
        return textual, binary

    def load_content_(self, editor, doc):
        """
        load one document record from database.
        @param editor: is tk.Text widget
        @param doc: is DBRecordDoc object
        """
        try:
            core = editor.core()
            textual, binary = self._store.read_doc(doc.sn)
            textual = json.loads(textual)
            text = textual.pop("text", '')
            # 1. text
            core.insert('1.0', text)
            # 2. font
            font_spec = textual.pop("font", '')
            font = None
            if len(font_spec) > 0:
                font = tkFont.Font(family=font_spec['family'], size=font_spec['size'])
            if font is None:
                font = self._font.copy()
            core.config(font=font)
            # 2. images
            images = textual.pop('image', [])
            if len(images) > 0:
                jfp = jex.FilePile(io.BytesIO(binary))
                for i in images:
                    fd = jfp.open(i['name'])
                    ext = os.path.splitext(i['name'])[1]
                    image = jtk.ImageBox(core, image=io.BytesIO(fd.read()), scale=i['scale'], ext=ext)
                    core.delete(i['pos'])  # delete placeholder
                    core.window_create(i['pos'], window=image)
                    fd.close()
                jfp.close()
            # 3. tables
            for i in textual.pop('table', []):
                table = jtk.TextTableBox(core, table=i['specs'], font=font)
                core.delete(i['pos'])  # delete placeholder
                core.window_create(i['pos'], window=table)
            # 4. underlines
            for pos in textual.pop('underline', []):
                pos = pos.split(' ')
                core.tag_add('underline', *pos)
            # 5. lists
            for pos in textual.pop('list', []):
                pos = pos.split(' ')
                core.tag_add('list', *pos)
            # 6. superscription
            for pos in textual.pop('sup', []):
                pos = pos.split(' ')
                core.tag_add('sup', *pos)
            # 7. subscription
            for pos in textual.pop('sub', []):
                pos = pos.split(' ')
                core.tag_add('sub', *pos)
            # 8. subscription
            for pos in textual.pop('code', []):
                pos = pos.split(' ')
                core.tag_add('code', *pos)
            # 9. tips
            for i, t in enumerate(textual.pop('tip', [])):
                self._tip_mgr.insert(core, t['text'], t['start'], t['end'], i)
            #
            # data-loading finished, now initialize digests for big data
            doc.init_digest(text=text, bulk=binary)
        except RuntimeError:
            print('bulk data cannot be extracted.')
        except Exception as e:
            print('Error: %s' % e)

    def find_words(self, textual, words):
        root = json.loads(textual)
        text = []
        for t in root.pop('table', []):
            data = t['specs']
            text.extend([cell['text'] for row in data for cell in row])
        for t in root.pop('tip', []):
            text.append(t['text'])
        text = '\n'.join(text)
        if 'text' in root:
            text = '%s\n%s' % (text, root['text'])
        return all(i in text.lower() for i in words)  # case-insensitive compare

    def on_tab_closed(self, editor: jtk.TextEditor):
        windows = self.all_custom_windows(editor.core(), jtk.ImageBox)
        for w in windows:
            w.release_file()

    @staticmethod
    def all_custom_windows(text: tk.Text, cls=None):
        windows = text.window_names()
        if len(windows) > 0 and jex.is_str(windows[0]):
            windows = map(text.nametowidget, windows)  # name is converted to widget object
        if cls is not None:
            windows = [w for w in windows if isinstance(w, cls)]
        return windows


if __name__ == "__main__":
    MainApp().mainloop()
