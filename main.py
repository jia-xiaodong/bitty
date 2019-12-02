#!/usr/bin/python
# -*- coding: utf-8 -*-

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
        self._tree.bind('<2>', self.on_popup_menu_)
        self._tree.bind('<Double-1>', self.select_tag_)
        map(lambda i: self.draw_tags_('', i), self._tags)
        self._moved_node = None  # tag can be moved to another tag as its child
        self._been_shown = False # show this menu item only once
        #
        # user can select tag from tag-tree and put their text to below list-box.
        tk.Label(master, text='Selected:').pack(side=tk.TOP, anchor=tk.W)
        self._list = tk.Listbox(master, selectmode=tk.SINGLE, height=5)
        self._list.pack(fill=tk.BOTH, expand=tk.YES)
        self._list.bind('<BackSpace>', self.deselect_tag_)
        self._list.bind('<Double-1>', self.deselect_tag_)
        map(lambda i: self._list.insert(tk.END, i.name), self._selected)
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
            self._tree.selection_add(clicked)     # selection != focus
            self._tree.focus(clicked)             # selection is visual; focus is logical.
        TagPicker.Popup(self, clicked).post(*self.winfo_pointerxy())

    def on_query_(self, evt):
        # 1. restore
        map(lambda i: self._tree.move(i.iid, i.parent, i.index), self._filtered)
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
        children = self._tree.get_children(iid)
        for i in children:
            if self.filter_node_(i, keyword):
                item = TagPicker.HiddenNode(iid, i, self._tree.index(i))
                self._filtered.append(item)
                hidden.append(i)
        if len(hidden) < len(children):
            return False
        name = self._tree.item(iid, 'text')
        if name.find(keyword) >= 0:
            return False
        # if parent is removed, the children would vanish too.
        if len(hidden) == len(children) > 0:
            for i in children:
                for j in self._filtered[:]:
                    if j.iid == i:
                        self._filtered.remove(j)
                        break
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
        map(lambda i: self._list.insert(tk.END, i.name), self._selected)

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
        self.show_rename_entry_(iid)

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
        self.show_rename_entry_(child)

    def show_rename_entry_(self, iid):
        self._tree.see(iid)
        self._tree.focus(iid)
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
            return True   # node can be moved to root
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
        self._date = tk.StringVar(value=str(self._record.date))
        #
        kw['title'] = 'Document Property'
        jtk.ModalDialog.__init__(self, master, *a, **kw)

    def body(self, master):
        frm = tk.Frame(master)
        frm.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        tk.Label(frm, text='Title:').pack(side=tk.LEFT)
        self._e = tk.Entry(frm, textvariable=self._title)
        self._e.pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        frm = tk.Frame(master)
        frm.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        tk.Label(frm, text='Edited:').pack(side=tk.LEFT)
        e = tk.Entry(frm, textvariable=self._date)
        e.pack(side=tk.LEFT)
        self._indicator = tk.Label(frm, text='V', fg='dark green')
        self._indicator.pack(side=tk.LEFT)
        b = tk.Button(frm, text='...', command=self.change_date)
        b.pack(side=tk.LEFT)
        self._date.trace('w', self.date_changed_)
        #
        self._tag_picker = TagPicker(master, database=self._store, owned=self._record.tags[:])
        self._tag_picker.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        return self._e  # make it getting input focus

    def apply(self):
        self._record.title = self._title.get().strip(' \n')
        self._record.tags = self._tag_picker.get_selection()
        self.result = True

    def validate(self):
        title = self._title.get().strip(' \n')
        if title == '':
            jtk.MessageBubble(self._e, 'Title cannot be empty!')
            return False
        return True

    def change_date(self):
        dlg = jtk.CalendarDlg(self, date=self._record.date)
        dlg.show()
        if dlg.date != self._record.date:
            self._record.date = dlg.date
            self._date.set(str(dlg.date))
        self.set_indicator_(True)

    def date_changed_(self, name, index, mode):
        try:
            dt = self._date.get()
            dt = datetime.datetime.strptime(dt, DATE_FORMAT)
            dt = datetime.date(year=dt.year, month=dt.month, day=dt.day)
            if dt != self._record.date:
                self._record.date = dt
            self.set_indicator_(True)
        except ValueError:
            self.set_indicator_(False)

    def set_indicator_(self, passed):
        if passed:
            self._indicator['fg'] = 'dark green'
            self._indicator['text'] = 'V'
        else:
            self._indicator['fg'] = 'red'
            self._indicator['text'] = 'X'


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
        e = tk.Entry(self, textvariable=self._result)
        e.pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        jtk.MakePlaceHolder(e, ByTitle.PLACE_HOLDER)

    def get_result(self):
        keywords = self._result.get().strip(' \n')
        if keywords == ByTitle.PLACE_HOLDER:
            return ''
        return keywords.split(' ')


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
        dlg.show()
        if dlg.result is None:
            return
        self._result[:] = dlg.result
        self._tags_string.set(','.join(i.name for i in self._result))
        if not self._switch.get():
            self._switch.set(1)


class ByDate(SearchCondition):
    """
    @return tuple(from, to), both 'from' and 'to' are date objects (or None, if not selected).
    """
    def __init__(self, master, *a, **kw):
        SearchCondition.__init__(self, master, *a, **kw)
        #
        tk.Checkbutton(self, variable=self._switch).pack(side=tk.LEFT)
        # row 1
        row1 = tk.Frame(self)
        row1.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        self._date_from = tk.StringVar()
        self._date_from.trace('w', self.from_changed_)
        self._from = None
        e = tk.Entry(row1, textvariable=self._date_from)
        e.pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        jtk.MakePlaceHolder(e, "<from what day it was edited?>")
        btn = tk.Button(row1, text='...')
        btn['command'] = lambda: self.open_date_picker_(self._date_from)
        btn.pack(side=tk.LEFT)
        # row 2
        row2 = tk.Frame(self)
        row2.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        self._date_to = tk.StringVar()
        self._date_to.trace('w', self.to_changed_)
        self._to = None
        e = tk.Entry(row2, textvariable=self._date_to)
        e.pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        jtk.MakePlaceHolder(e, "<to what day it was edited?>")
        btn = tk.Button(row2, text='...')
        btn['command'] = lambda: self.open_date_picker_(self._date_to)
        btn.pack(side=tk.LEFT)

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
        return self._from, self._to

    def from_changed_(self, name, index, mode):
        try:
            tm = self._date_from.get()
            tm = datetime.datetime.strptime(tm, DATE_FORMAT)
            self._from = datetime.date(year=tm.year, month=tm.month, day=tm.day)
            if not self._switch.get():
                self._switch.set(1)
        except ValueError:
            self._from = None

    def to_changed_(self, name, index, mode):
        try:
            tm = self._date_to.get()
            tm = datetime.datetime.strptime(tm, DATE_FORMAT)
            self._to = datetime.date(year=tm.year, month=tm.month, day=tm.day)
            if not self._switch.get():
                self._switch.set(1)
        except ValueError:
            self._to = None


class ByOrder(SearchCondition):
    def __init__(self, master, *a, **kw):
        SearchCondition.__init__(self, master, *a, **kw)
        tk.Checkbutton(self, variable=self._switch).pack(side=tk.LEFT)
        self._from = tk.StringVar()
        e = tk.Entry(self, textvariable=self._from, width=16)
        e.pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        jtk.MakePlaceHolder(e, '<Record ID from ?>')
        self._to = tk.StringVar()
        e = tk.Entry(self, textvariable=self._to, width=16)
        e.pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        jtk.MakePlaceHolder(e, '<Record ID to ?>')

    def get_result(self):
        try:
            f = int(self._from.get())
        except ValueError:
            f = None
        try:
            t = int(self._to.get())
        except ValueError:
            t = None
        finally:
            return f, t


class NotePreview:
    LINES_MAX = 15
    LINE_WIDTH = 40

    def __init__(self, master, database, note):
        self._top = top = tk.Toplevel(master, bd=1)
        top.transient(master)          # floating above master always
        top.wm_overrideredirect(True)  # remove window title bar
        #
        tk.Label(top, text='Title: %s' % note.title).pack(side=tk.TOP, anchor=tk.W)
        #
        tags = ','.join(i.name for i in note.tags)
        tk.Label(top, text='Tags: %s' % tags).pack(side=tk.TOP, anchor=tk.W)
        #
        tk.Label(top, text='Edited: %s' % note.date).pack(side=tk.TOP, anchor=tk.W)
        #
        option = {'width': NotePreview.LINE_WIDTH, 'height': NotePreview.LINES_MAX}
        editor = jtk.TextEditor(top, core=option)
        content = database.read_plain(note.sn)
        limit = NotePreview.LINE_WIDTH * NotePreview.LINES_MAX
        lines = content[:limit].split('\n')[:NotePreview.LINES_MAX]
        editor.core().insert(tk.END, '\n'.join(lines))
        editor.core().config(state=tk.DISABLED)  # disable editing after loading
        editor.pack(side=tk.TOP, pady=5)
        #
        # Strange function. It will affect <Motion> event behavior.
        # Here it grabs the mouse <motion> event without user's explicit click on window.
        # Of course, I mean it on Mac platform for now. TODO: what about windows?
        top.grab_set()
        top.bind('<Motion>', self.close_)
        #
        top.geometry("+%d+%d" % (master.winfo_rootx()+100, master.winfo_rooty()))
        # detect user 'enter-zone' behavior
        self._been_entered = False

    def close_(self, evt):
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


class OpenDocDlg(jtk.ModalDialog):
    # 8 items per page
    PAGE_NUM = 8
    # 2 sorting methods
    SORT_BY_ID = 0
    SORT_BY_DATE = 1
    """
    @return a tuple(array of serial number, array of DBRecordDoc, current page)
    """

    class QueryConfig(object):
        def __init__(self):
            self._hits = []
            self._curr_page = 0
            self._sort_states = [False, False]

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
            self._sort_states = [False, False]

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

    def body(self, master):
        frm = tk.LabelFrame(master, text='Search by:')
        frm.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES, ipadx=5, ipady=5)
        # search conditions
        box = jtk.TabBox(frm)
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
        # --- results ---
        frm = tk.LabelFrame(master, text='Result:')
        frm.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        #
        self._note_list = ttk.Treeview(frm, columns=['ID', 'Title', 'Date'],
                                       show='headings',         # hide first icon column
                                       height=OpenDocDlg.PAGE_NUM,
                                       selectmode=tk.EXTENDED)  # multiple rows can be selected
        self._note_list.pack(fill=tk.BOTH, expand=tk.YES, padx=5, pady=5)
        self._note_list.bind('<Double-1>', self.ok)
        self._note_list.bind('<space>', self.open_preview_)
        self._note_list.bind('<2>', self.open_preview_)
        # <Up> and <Down> is the default key bindings for Treeview
        self._note_list.bind('<Left>', self.jump_prev_)
        self._note_list.bind('<Right>', self.jump_next_)
        #
        self._note_list.column('ID', width=20, minwidth=20)
        self._note_list.heading('ID', text='ID', command=self.sort_by_id_)
        self._note_list.heading('Title', text='Title')
        width = tkFont.Font().measure('1999-99-99')
        self._note_list.column('Date', width=width, minwidth=width)
        self._note_list.heading('Date', text='Date', command=self.sort_by_date_)

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
        tk.Button(box, text='>>|', command=lambda: self.jump_page_(self.pages_()-1)).pack(side=tk.LEFT)
        #
        self._progress = tk.StringVar(value='page number')
        tk.Label(box, textvariable=self._progress).pack(side=tk.LEFT)
        #
        self._btn_search = btn = tk.Button(box, text="Search", command=self.search_)
        btn.pack(side=tk.LEFT)
        tk.Button(box, text="OK", command=self.ok).pack(side=tk.LEFT)
        #
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
            self._note_list.insert('', tk.END, iid=str(i), values=[j.sn, j.title, j.date])
        if len(self._state.hits) > 0:
            self._note_list.selection_set('0')  # automatically select the 1st one
            self._note_list.focus('0')          # give the 1st one focus (visually)
            self._note_list.focus_set()         # widget get focus to accept '<space>', '<Up>', '<Down>'
        #
        self._progress.set('%d / %d' % (n+1, self.pages_()))
        self._state.page = n

    def jump_next_(self, evt=None):
        if self._state.page+1 < self.pages_():
            self.jump_page_(self._state.page+1)

    def jump_prev_(self, evt=None):
        if self._state.page > 0:
            self.jump_page_(self._state.page-1)

    def pages_(self):
        total = max(len(self._state.hits), 1)
        return (total - 1) / OpenDocDlg.PAGE_NUM + 1

    def search_(self):
        conditions = {}
        if self._sb_tit.enabled():
            keywords = self._sb_tit.get_result()
            if len(keywords) > 0:
                keywords[:] = ['"%%%s%%"' % i for i in keywords]
                latter = ' AND desc LIKE '.join(keywords)
                conditions['title'] = 'desc LIKE %s' % latter
        if self._sb_tag.enabled():
            tags = self._sb_tag.get_result()
            if len(tags) > 0:
                conditions['tags'] = tags
        if self._sb_dat.enabled():
            from_, to_ = self._sb_dat.get_result()
            if not from_ is None:
                conditions['from'] = from_
            if not to_ is None:
                conditions['to'] = to_
        if self._sb_ord.enabled():
            lower, upper = self._sb_ord.get_result()
            if not upper is None:
                conditions['upper'] = upper
            if not lower is None:
                conditions['lower'] = lower
        if self._sb_txt.enabled():
            keywords = self._sb_txt.get_result()
            if len(keywords) > 0:
                conditions['content'] = keywords
        if len(conditions) == 0:
            self._state.clear()
        else:
            self._state.hits = self._store.select_doc(**conditions)
        jtk.MessageBubble(self._btn_search, '%d found' % len(self._state.hits))
        self.jump_page_(0)

    def open_preview_(self, evt=None):
        if evt.type == '2':  # TODO: 2 for key?
            active = self._note_list.focus()
        else:                # TODO: 4 for mouse?
            active = self._note_list.identify_row(evt.y)
        if active == '':
            return
        index = self._note_list.index(active)
        index += self._state.page * OpenDocDlg.PAGE_NUM
        NotePreview(self, database=self._store, note=self._state.hits[index])

    def sort_by_id_(self):
        self._state.sort_switch(OpenDocDlg.SORT_BY_ID)
        self._state.hits.sort(key=lambda i: i.sn, reverse=self._state.sort_state(OpenDocDlg.SORT_BY_ID))
        self.jump_page_(0)

    def sort_by_date_(self):
        self._state.sort_switch(OpenDocDlg.SORT_BY_DATE)
        self._state.hits.sort(key=lambda i: i.date, reverse=self._state.sort_state(OpenDocDlg.SORT_BY_DATE))
        self.jump_page_(0)


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


class RelyItem:
    def __init__(self, w, evt, caveat=-1):
        """
        @param w is Tkinter widget, could be menu or button
        @note: if w is a menu, then caveat is the index of its sub-menu item.
        """
        self._w = w
        self._c = caveat

    def set_state(self, state):
        if self._c > -1:  # menu item
            self._w.entryconfig(self._c, state=state)
        else:             # button
            self._w.config(state=state)


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
        text.tag_config(name, background='gray92')  # the bigger number, the lighter gray color
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
        unused = [i for i in self._tips[text].iterkeys() if i not in keys]
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
            range = text.tag_ranges(i)
            if text.compare(range[1], '<', index1):
                continue
            if text.compare(range[0], '>', index2):
                continue
            hits.append((i, range[0], range[1]))
        return hits

    def schedule_(self, text, sn):
        self._wnd = tk.Toplevel(text)
        self._wnd.wm_overrideredirect(True)  # remove window title bar
        label = tk.Label(self._wnd, text=self._tips[text][sn], justify=tk.LEFT, bg='yellow')
        label.pack(ipadx=5)
        rx, ry = text.winfo_rootx(), text.winfo_rooty()
        x, y, _, _ = text.bbox(tk.CURRENT)
        w, h = label.winfo_reqwidth(), label.winfo_reqheight()
        self._wnd.wm_geometry("+%d+%d" % (rx+x-w/2, ry+y-h))

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
                tip_tags.append((i, text.index(ranges[0]), text.index(ranges[1])))
        # the purpose of sort is only one: digest comparison
        tip_tags.sort(cmp=lambda i, j: -1 if text.compare(i[1], '<', j[1]) else 1)
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
        @return True if something is changed.
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
        self._text.tag_add(tk.SEL, '1.0', tk.END)
        return self._text

    def apply(self):
        content = self._text.get('1.0', tk.END)
        self.result = content.strip()

    def validate(self):
        content = self._text.get('1.0', tk.END)
        return content.strip() != TipEditDlg._placeholder


class MainApp(tk.Tk):
    TITLE = 'bitty'
    UNNAMED = 'untitled'
    #
    SAVE = jex.enum1(Finish=0, FailContent=1, FailTitle=2)
    # All text editors are using same font
    DEFAULT_FONT = 'Helvetica' if platform == 'darwin' else 'Courier'
    DEFAULT_SIZE = 18
    #
    RELY = jex.enum1(DB=0, DOC=1)
    EVENT_DB_EXIST = '<<DBExist>>'    # sent when database is opened / closed.
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
        self.add_listener(menu, MainApp.EVENT_DB_EXIST, 2)  # 2 is the index of menu 'Close'
        menu.add_separator()
        menu.add_command(label='Quit', command=self.quit_)
        menu_bar.add_cascade(label='Database', menu=menu)
        # doc
        menu = tk.Menu(menu_bar, tearoff=0)
        menu.add_command(label='New', command=self.menu_doc_new_)
        self.add_listener(menu, MainApp.EVENT_DB_EXIST, 0)
        menu.add_command(label='Open', command=self.menu_doc_open_)
        self.add_listener(menu, MainApp.EVENT_DB_EXIST, 1)
        menu.add_command(label='Save', command=self.menu_doc_save_)
        self.add_listener(menu, MainApp.EVENT_DOC_EXIST, 2)
        menu.add_command(label='Close', command=self.menu_doc_close_)
        self.add_listener(menu, MainApp.EVENT_DOC_EXIST, 3)
        menu.add_command(label='Delete', command=self.menu_doc_delete_)
        self.add_listener(menu, MainApp.EVENT_DOC_EXIST, 4)
        menu.add_command(label='Export to HTML', command=self.doc_export_html_)
        self.add_listener(menu, MainApp.EVENT_DOC_EXIST, 5)
        menu_bar.add_cascade(label='Document', menu=menu)
        self.add_listener(menu_bar, MainApp.EVENT_DB_EXIST, 1)
        # edit
        menu = tk.Menu(menu_bar, tearoff=0)
        menu.add_command(label='Insert Image File', command=self.edit_insert_image_)
        self.add_listener(menu, MainApp.EVENT_DOC_EXIST, 0)
        menu.add_command(label='Insert Text Table', command=self.edit_insert_table_)
        self.add_listener(menu, MainApp.EVENT_DOC_EXIST, 1)
        menu.add_command(label='Copy from Clipboard', command=self.copy_from_clipboard_)
        self.add_listener(menu, MainApp.EVENT_DOC_EXIST, 2)
        menu.add_command(label='Attach a Tip', command=self.edit_a_tip_)
        self.add_listener(menu, MainApp.EVENT_DOC_EXIST, 3)
        menu_bar.add_cascade(label='Edit', menu=menu)
        self.add_listener(menu_bar, MainApp.EVENT_DB_EXIST, 2)
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
        ico = ImageTk.PhotoImage(im.crop((0, 32*n, 31, 32*(n+1)-1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.menu_doc_new_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Create a New Document')
        self.add_listener(btn, MainApp.EVENT_DB_EXIST)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32*n, 31, 32*(n+1)-1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.menu_doc_open_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Open a Document')
        self.add_listener(btn, MainApp.EVENT_DB_EXIST)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32*n, 31, 32*(n+1)-1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.menu_doc_save_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Save Current Document')
        self.add_listener(btn, MainApp.EVENT_DOC_EXIST)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32*n, 31, 32*(n+1)-1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.menu_doc_close_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Close Current Document')
        self.add_listener(btn, MainApp.EVENT_DOC_EXIST)
        #
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32*n, 31, 32*(n+1)-1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.edit_insert_image_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Insert Image File')
        self.add_listener(btn, MainApp.EVENT_DOC_EXIST)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32*n, 31, 32*(n+1)-1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.edit_insert_table_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Insert Text Table')
        self.add_listener(btn, MainApp.EVENT_DOC_EXIST)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32*n, 31, 32*(n+1)-1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.edit_underline_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Format: Underline')
        self.add_listener(btn, MainApp.EVENT_DOC_EXIST)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32*n, 31, 32*(n+1)-1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.edit_mark_list_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Format: List')
        self.add_listener(btn, MainApp.EVENT_DOC_EXIST)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32*n, 31, 32*(n+1)-1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.edit_make_superscript_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Format: Superscript')
        self.add_listener(btn, MainApp.EVENT_DOC_EXIST)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32*n, 31, 32*(n+1)-1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.edit_make_subscript_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Format: Subscript')
        self.add_listener(btn, MainApp.EVENT_DOC_EXIST)
        #
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32*n, 31, 32*(n+1)-1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.menu_edit_find_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Find and Replace')
        self.add_listener(btn, MainApp.EVENT_DOC_EXIST)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32*n, 31, 32*(n+1)-1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.menu_doc_attr_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Document Title and Tags')
        self.add_listener(btn, MainApp.EVENT_DOC_EXIST)
        #
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32*n, 31, 32*(n+1)-1)))
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
        editor = jtk.MultiTabEditor(self, font=self._font)
        editor.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        editor.bind(jtk.MultiTabEditor.EVENT_SWITCH, self.on_tab_switched_)
        self._editor = editor

    def init_status_bar_(self):
        pass

    def menu_database_new_(self):
        filename = tkFileDialog.asksaveasfilename(defaultextension='.sqlite3')
        if filename is '':
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
        if filename is '':
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
        if self._editor.active() and\
           not tkMessageBox.askokcancel(MainApp.TITLE, 'Are you sure to QUIT?'):
            return
        if not self.menu_database_close_():
            return
        self.destroy()

    def menu_doc_new_(self, evt=None):
        editor = self._editor.new_editor(MainApp.UNNAMED)
        self.config_core(editor)
        editor.monitor_change()
        self._editor.switch_tab(editor)
        if self._editor.count() == 1:
            self.event_generate(MainApp.EVENT_DOC_EXIST, state=1)

    def menu_doc_open_(self, evt=None):
        dlg = OpenDocDlg(self, database=self._store, state=self._last_search)
        dlg.show()
        if dlg.result is None:
            return
        indices, self._last_search = dlg.result
        opened = {n:e for e, n in self._notes.iteritems()}
        for note in [self._last_search.hits[i] for i in indices]:
            # if it's already opened
            if note in opened:
                self._editor.switch_tab(opened[note])
                continue
            # if not opened yet
            editor = self._editor.new_editor(note.title)
            self.config_core(editor)
            self._editor.switch_tab(editor)
            self.load_content_(editor, note)
            editor.monitor_change()
            self._notes[editor] = note
            #
            if self._editor.count() == 1:
                self.event_generate(MainApp.EVENT_DOC_EXIST, state=1)

    def menu_doc_save_(self, evt=None):
        editor = self._editor.active()
        if not editor.modified():
            return
        self.save_(editor)

    def save_(self, editor):
        errors = set()
        try:
            record = self._notes[editor]
        except KeyError:
            title = self._editor.get_caption(editor)
            record = jdb.DBRecordDoc(title)
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

    def menu_doc_close_(self):
        editor = self._editor.active()
        if editor.modified():
            choice = tkMessageBox.askyesnocancel(MainApp.TITLE, 'Wanna SAVE changes before closing doc?')
            if choice is None:  # cancel
                return
            if choice is True:
                self.save_(editor)
        self._editor.remove(editor)
        self._notes.pop(editor, None)
        if self._editor.active() is None:
            self.event_generate(MainApp.EVENT_DOC_EXIST, state=0)
            self._search.pack_forget()

    def menu_doc_delete_(self):
        editor = self._editor.active()
        if not tkMessageBox.askokcancel(MainApp.TITLE, 'Do you really want to delete it?'):
            return
        if editor in self._notes:
            note = self._notes.pop(editor)
            if self._store.delete_doc(note.sn) and note in self._last_search.hits:
                self._last_search.hits.remove(note)
        self._editor.remove(editor)
        if self._editor.active() is None:
            self.event_generate(MainApp.EVENT_DOC_EXIST, state=0)

    def menu_help_about_(self):
        msg = '''
It's an Electrical Diary app.
You can record everything in life at will.

Chinese saying: rotten pencil surpasses smart head.
It's more and more obvious when I get aged.

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
        self.bind_class('Entry', '<Mod1-a>', EntryOps.select_all)
        self.bind_class('Entry', '<Mod1-A>', EntryOps.select_all)
        self.bind_class('Entry', '<Mod1-Left>', EntryOps.jump_to_start)
        self.bind_class('Entry', '<Mod1-Right>', EntryOps.jump_to_end)
        self.bind_class('Entry', '<Mod1-C>', EntryOps.copy)
        self.bind_class('Entry', '<Mod1-X>', EntryOps.cut)
        self.bind_class('Entry', '<Mod1-V>', EntryOps.paste)
        #
        jdb.DocBase.assign_finder(self.find_words)

    def menu_doc_attr_(self):
        editor = self._editor.active()
        try:
            record = self._notes[editor]
        except KeyError:
            title = self._editor.get_caption(editor)
            record = jdb.DBRecordDoc(title)
        #
        dlg = DocPropertyDlg(self, database=self._store, record=record)
        dlg.show()
        if dlg.result is None:
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
            if len(parts) == 1:     # option 1: 'untitled'
                return True
            if parts[2].isdigit():  # option 2: 'untitled-2'
                return True
        return False

    def menu_edit_find_(self, evt=None):
        editor = self._editor.active()
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
            self._search.attach(self._editor.active().core())

    def font_changed_(self):
        family = self._font_family.get()
        size = int(self._font_size.get())
        try:
            if self._font.cget('family') != family:
                self._font.config(family=family)
            if self._font.cget('size') != size:
                self._font.config(size=size)
        except Exception as e:
            pass

    def init_listeners_(self):
        self._relied = {}
        self.bind(MainApp.EVENT_DB_EXIST, self.notify_db_ops_)
        self.bind(MainApp.EVENT_DOC_EXIST, self.notify_doc_ops_)

    def add_listener(self, wgt, evt, caveat=-1):
        item = RelyItem(wgt, evt, caveat)
        if evt in self._relied:
            self._relied[evt].append(item)
        else:
            self._relied[evt] = [item]

    def notify_db_ops_(self, evt):
        state = tk.NORMAL if evt.state else tk.DISABLED
        map(lambda w: w.set_state(state), self._relied[MainApp.EVENT_DB_EXIST])
        #
        if evt.state:
            self.bind('<Command-n>', self.menu_doc_new_)
            self.bind('<Command-o>', self.menu_doc_open_)
        else:
            self.unbind('<Command-n>')
            self.unbind('<Command-o>')

    def notify_doc_ops_(self, evt):
        state = tk.NORMAL if evt.state else tk.DISABLED
        map(lambda w: w.set_state(state), self._relied[MainApp.EVENT_DOC_EXIST])
        #
        if evt.state:
            self.bind('<Mod1-s>', self.menu_doc_save_)
            self.bind('<Mod1-S>', self.menu_doc_save_)
            self.bind('<Mod1-f>', self.menu_edit_find_)
            self.bind('<Mod1-F>', self.menu_edit_find_)
        else:
            self.unbind('<Mod1-s>')
            self.unbind('<Mod1-S>')
            self.unbind('<Mod1-f>')
            self.unbind('<Mod1-F>')

    def edit_underline_(self):
        self.toggle_format_('underline')

    def edit_mark_list_(self):
        TAG = 'list'
        try:
            editor = self._editor.active()
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

    def edit_make_superscript_(self):
        self.toggle_format_('sup', 'sub')

    def edit_make_subscript_(self):
        self.toggle_format_('sub', 'sup')

    def toggle_format_(self, tag, conflict=None):
        try:
            editor = self._editor.active()
            core = editor.core()
            # 1. check
            sel_range = core.tag_ranges(tk.SEL)
            if len(sel_range) == 0:
                sel_range = (core.index(tk.INSERT), core.index('%s+1c' % tk.INSERT))
            it = iter(core.tag_ranges(tag))
            fully_included = False
            for s in it:
                e = it.next()
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
        extensions = tuple(Image.registered_extensions().keys())
        images = tkFileDialog.askopenfilename(filetypes=[('Image File', extensions)], multiple=True)
        if len(images) == 0:
            return
        editor = self._editor.active()
        core = editor.core()
        if len(images) == 1:
            image = jtk.ImageBox(core, image=open(images[0]), ext=os.path.splitext(images[0])[1])
            core.window_create(tk.INSERT, window=image)
        else:
            for i, each in enumerate(images):
                core.insert(tk.INSERT, '\n%d\n' % (i+1))
                image = jtk.ImageBox(core, image=open(each), ext=os.path.splitext(each)[1])
                core.window_create(tk.INSERT, window=image)
        editor.on_modified()

    def edit_insert_table_(self):
        try:
            ts = self.clipboard_get()
            table = json.loads(ts)
        except ValueError:
            table = [[{'text': 'single-click'}, {'text': 'to select'}, {'text': 'table cell'}],
                     [{'text': 'double-click'}, {'text': 'to edit'}, {'text': 'text'}],
                     [{'text': 'control-enter'}, {'text': 'to finish'}, {'text': 'input'}]]
        finally:
            editor = self._editor.active()
            w = jtk.TextTableBox(editor.core(), table=table, font=self._font)
            editor.core().window_create(tk.INSERT, window=w)
            editor.on_modified()

    def doc_export_html_(self):
        # TODO: export one doc to HTML
        pass

    def config_core(self, editor):
        text = editor.core()
        text.tag_config('underline', underline=1)
        text.tag_config('list', lmargin1=12, lmargin2=12)  # 12 pixels, for list
        #
        height = self._font.metrics("linespace")
        text.tag_config('sup', offset=height/3)
        text.tag_config('sub', offset=-height/3)

    def copy_from_clipboard_(self):
        editor = self._editor.active()
        content = editor.clipboard_get()
        content = '\n'.join(content.splitlines())
        editor.core().insert(tk.INSERT, content)
        editor.core().see(tk.INSERT)

    def edit_a_tip_(self):
        # TODO: make operations more natural.
        try:
            editor = self._editor.active()
            core = editor.core()
            # 1. check selection
            sel_range = core.tag_ranges(tk.SEL)
            if len(sel_range) == 0:
                tkMessageBox.showerror(MainApp.TITLE, 'Select a part of text before adding a tip.')
                return
            # 2.
            tips = self._tip_mgr.includes(core, *sel_range)
            if len(tips) == 0:
                text = core.get(*sel_range)
                dlg = TipEditDlg(self, sel=text)
                dlg.show()
                if dlg.result is None:
                    return
                self._tip_mgr.insert(core, dlg.result, tk.SEL_FIRST, tk.SEL_LAST)
            elif len(tips) > 1:
                tkMessageBox.showerror(MainApp.TITLE, 'You cannot select more than 1 tip.')
                return
            elif tips[0][1] == sel_range[0] and tips[0][2] == sel_range[1]:
                choice = tkMessageBox.askyesnocancel(MainApp.TITLE, 'Really want to delete tip?')
                if choice is True:
                    self._tip_mgr.remove(core, tips[0][0])
            else:
                text = core.get(*sel_range)
                content = self._tip_mgr.get_content(core, tips[0][0])
                dlg = TipEditDlg(self, sel=text, tip=content)
                dlg.show()
                if dlg.result is not None:
                    self._tip_mgr.update(core, tips[0][0], dlg.result)
                pass # edit old tip
            # 3. need saving
            editor.on_modified()
        except Exception as e:
            print('Error: %s' % e)

    def collect_content_(self, text):
        """
        @param text: tk.Text widget.
        @return tuple(textual_data, binary_data)
        """
        content = text.get('1.0', tk.END).splitlines()
        #
        textual = {}
        #
        windows = text.window_names()
        if len(windows) > 0 and isinstance(windows[0], basestring):
            windows = map(text.nametowidget, windows)  # name is converted to widget object
        #
        # Use "?" as placeholder which will be replaced by genuine widget when loading from
        # database in future. With the help of a placeholder, it's easy to insert window to
        # tk.Text by original position.
        windows = [w for w in windows if isinstance(w, jtk.StorageMixin)]
        windows.sort(cmp=lambda i, j: -1 if text.compare(i, '<', j) else 1)
        for w in windows:
            row, col = text.index(w).split('.')
            row, col = int(row) - 1, int(col)
            content[row] = '%s?%s' % (content[row][:col], content[row][col:])
        # 1. text
        content = [i.rstrip() for i in content]  # delete redundant trailing spaces
        textual["text"] = '\n'.join(content)
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
            binary = ''
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
        # 8. tips
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
            textual, binary = self._store.read_rich(doc.sn)
            textual = json.loads(textual)
            text = textual.pop("text", '')
            # 1. text
            core.insert('1.0', text)
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
                table = jtk.TextTableBox(core, table=i['specs'], font=self._font)
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
            # 8. tips
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
        return all(text.find(i) > -1 for i in words)


if __name__ == "__main__":
    MainApp().mainloop()