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
            1. database: NoteStore object
            2. owned: array of RecordTag objects (optional)
        @return .get_selection(): array of RecordTag objects
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
        tag = jdb.RecordTag(TagPicker.UNNAMED)
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
        jdb.RecordTag.forest_delete(self._tags, tag)
        self._store.delete_tag(tag)
        self._tree.delete(iid)

    def add_child_(self):
        iid = self._tree.focus()
        selected_tag = self.tag_from_node_(iid)
        tag = jdb.RecordTag(TagPicker.UNNAMED, selected_tag.sn)
        jdb.RecordTag.forest_add(self._tags, tag)
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
        @return RecordTag object
        """
        sn = self._tree.item(iid, 'values')
        sn = int(sn[0])
        return jdb.RecordTag.forest_find(self._tags, sn)

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
        jdb.RecordTag.forest_delete(self._tags, moved)
        if parent == '':
            moved.parent = 0
        else:
            parent = self._tree.item(parent, 'values')
            moved.parent = int(parent[0])
        jdb.RecordTag.forest_add(self._tags, moved)
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
          1. database: NoteStore object. Required.
          2. record: RecordNote object. Required
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
        lbl = tk.Label(frm, textvariable=self._date)
        lbl.pack(side=tk.LEFT)
        lbl.bind('<1>', self.change_date)
        #
        self._tag_picker = TagPicker(master, database=self._store, owned=self._record.tags[:])
        self._tag_picker.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)

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

    def change_date(self, evt):
        dlg = jtk.CalendarDlg(self, date=self._record.date)
        dlg.show()
        if dlg.date != self._record.date:
            self._record.date = dlg.date
            self._date.set(str(dlg.date))


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
    @return an array of RecordTag objects.
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
    DATE_FORMAT = '%Y-%m-%d'  # 2019-03-18

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
            tm = datetime.datetime.strptime(tm, ByDate.DATE_FORMAT)
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
            tm = datetime.datetime.strptime(tm, ByDate.DATE_FORMAT)
            self._from = datetime.date(year=tm.year, month=tm.month, day=tm.day)
            if not self._switch.get():
                self._switch.set(1)
        except ValueError:
            self._from = None

    def to_changed_(self, name, index, mode):
        try:
            tm = self._date_to.get()
            tm = datetime.datetime.strptime(tm, ByDate.DATE_FORMAT)
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
        w, h = self._top.winfo_width(), self._top.winfo_height()
        in_zone = all([0 < evt.x < w, 0 < evt.y < h])
        # only if the mouse enters once then leaves, the preview closes.
        if not self._been_entered:
            if in_zone:
                self._been_entered = True
        elif not in_zone:  # enter and leave
            self._top.destroy()


class OpenDocDlg(jtk.ModalDialog):
    PAGE_NUM = 8
    """
    @return an array when dialog's closed.
    """

    def __init__(self, master, *a, **kw):
        self._store = kw.pop('database')
        self._notes = []
        self._curr = 0
        kw['title'] = 'Select Document to Open'
        jtk.ModalDialog.__init__(self, master, *a, **kw)
        self._sort_reverse = [False, False]
        self._preview = 0

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
        self._note_list.bind('<Enter>', self.preview_schedule_)
        self._note_list.bind('<Leave>', self.preview_unschedule_)
        self._note_list.bind('<Motion>', self.preview_schedule_)
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
            selected = [int(i) + self._curr * OpenDocDlg.PAGE_NUM for i in selected]
            self.result = [self._notes[i] for i in selected]
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
        for i, j in enumerate(self._notes[start:stop]):
            self._note_list.insert('', tk.END, iid=str(i), values=[j.sn, j.title, j.date])
        if len(self._notes) > 0:
            self._note_list.selection_set('0')
        #
        self._progress.set('%d / %d' % (n+1, self.pages_()))
        self._curr = n

    def jump_next_(self):
        if self._curr+1 < self.pages_():
            self.jump_page_(self._curr+1)

    def jump_prev_(self):
        if self._curr > 0:
            self.jump_page_(self._curr-1)

    def pages_(self):
        total = max(len(self._notes), 1)
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
            del self._notes[:]
        else:
            self._notes[:] = self._store.filter_notes(**conditions)
        jtk.MessageBubble(self._btn_search, '%d found' % len(self._notes))
        self.jump_page_(0)

    def preview_open_(self, index):
        index += self._curr * OpenDocDlg.PAGE_NUM
        NotePreview(self, database=self._store, note=self._notes[index])

    def preview_schedule_(self, evt):
        index = self._note_list.identify_row(evt.y)
        if index == '':
            return
        self.preview_unschedule_()
        index = int(index)
        self._preview = self.after(1000, lambda: self.preview_open_(index))

    def preview_unschedule_(self, evt=None):
        self.after_cancel(self._preview)

    def sort_by_id_(self):
        self._sort_reverse[0] = not self._sort_reverse[0]
        self._notes.sort(key=lambda i: i.sn, reverse=self._sort_reverse[0])
        self.jump_page_(0)

    def sort_by_date_(self):
        self._sort_reverse[1] = not self._sort_reverse[1]
        self._notes.sort(key=lambda i: i.date, reverse=self._sort_reverse[1])
        self.jump_page_(0)

    def ok(self, event=None):
        self.preview_unschedule_()
        jtk.ModalDialog.ok(self)


class RelyItem:
    def __init__(self, w, evt, caveat=-1):
        """
        @param w is Tkinter widget, could be menu or button
        """
        self._w = w
        self._c = caveat

    def set_state(self, state):
        if self._c > -1:  # menu item
            self._w.entryconfig(self._c, state=state)
        else:             # button
            self._w.config(state=state)


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
        self.add_listener(menu, MainApp.EVENT_DB_EXIST, 2)  # 2 is menu index
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
        menu.add_command(label='Insert Image', command=self.edit_insert_image_)
        self.add_listener(menu, MainApp.EVENT_DOC_EXIST, 0)
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
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.menu_edit_cut_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Cut <Command-X>')
        self.add_listener(btn, MainApp.EVENT_DOC_EXIST)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32*n, 31, 32*(n+1)-1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.menu_edit_copy_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Copy <Command-C>')
        self.add_listener(btn, MainApp.EVENT_DOC_EXIST)
        #
        n += 1
        ico = ImageTk.PhotoImage(im.crop((0, 32*n, 31, 32*(n+1)-1)))
        btn = tk.Button(toolbar, image=ico, relief=tk.FLAT, command=self.menu_edit_paste_)
        btn.image = ico
        btn.pack(side=tk.LEFT)
        jtk.CreateToolTip(btn, 'Paste <Command-V>')
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
        self._store = jdb.NoteStore.create_db(filename)
        self.event_generate(MainApp.EVENT_DB_EXIST, state=1)

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
        if not jdb.NoteStore.validate(filename):
            tkMessageBox.showerror(MainApp.TITLE, 'Wrong database format')
            return
        if not self.menu_database_close_():
            return
        self._store = jdb.NoteStore(filename)
        self.event_generate(MainApp.EVENT_DB_EXIST, state=1)

    def menu_database_close_(self):
        if self._store is None:
            return True
        for e in self._editor.iter_tabs():
            if e.modified():
                result = self.save_(e)
                # if content exists, reject to continue until a title is given.
                if result == MainApp.SAVE.FailTitle:
                    return False
        self._editor.close_all()
        self._notes.clear()
        self._store.close()
        self._store = None
        self.event_generate(MainApp.EVENT_DB_EXIST, state=0)
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
        self.config_core(editor.core())
        editor.monitor_change()
        self._editor.switch_tab(editor)
        if self._editor.count() == 1:
            self.event_generate(MainApp.EVENT_DOC_EXIST, state=1)

    def menu_doc_open_(self, evt=None):
        dlg = OpenDocDlg(self, database=self._store)
        dlg.show()
        if dlg.result is None:
            return
        for note in dlg.result:
            #
            # if it's already opened
            for e, n in self._notes.iteritems():
                if n.sn == note.sn:
                    self._editor.switch_tab(e)
                    continue
            # if not open, open it
            editor = self._editor.new_editor(note.title)
            self.config_core(editor.core())
            #
            t, s, b = self._store.read_rich(note.sn)
            self.load_content_(editor, t, s, b)
            self._editor.switch_tab(editor)
            #
            note.init_digest(text=t, spec=s, bulk=b)
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
        """
        @return saving result (enum)
        """
        content = editor.content()
        # Saving Requirements No.1: non-empty content
        if content == '':
            return MainApp.SAVE.FailContent
        #
        try:
            record = self._notes[editor]
        except KeyError:
            title = self._editor.get_caption(editor)
            record = jdb.RecordNote(title)
        #
        # specify tags / title / date
        if MainApp.unnamed(record.title) or len(record.tags) == 0:
            dlg = DocPropertyDlg(self, database=self._store, record=record)
            dlg.show()
            if dlg.result is None:
                return MainApp.SAVE.FailTitle
            # Saving Requirements No.2: a proper title
            if MainApp.unnamed(record.title):
                return MainApp.SAVE.FailTitle
            self._editor.set_caption(editor, record.title)
        #
        # format-related misc
        record.format, record.bulk = self.collect_misc_(editor.core())
        #
        # save to database
        record.script = content
        if record.fragile:
            self._store.insert_note(record)
            self._notes[editor] = record
        else:
            self._store.update_note(record)
        editor.on_saved()
        return MainApp.SAVE.Finish

    def menu_doc_close_(self):
        result = MainApp.SAVE.Finish
        editor = self._editor.active()
        if editor.modified():
            result = self.save_(editor)
            # refuse to close if it has content but no title
            if result == MainApp.SAVE.FailTitle:
                return result
        self._editor.remove(editor)
        self._notes.pop(editor, None)
        if self._editor.active() is None:
            self.event_generate(MainApp.EVENT_DOC_EXIST, state=0)
        return result

    def menu_doc_delete_(self):
        editor = self._editor.active()
        try:
            if not tkMessageBox.askokcancel(MainApp.TITLE, 'Do you really want to delete it?'):
                return
            self._store.delete_note(self._notes[editor].sn)
            self._notes.pop(editor)
        finally:
            self._editor.remove(editor)
            if self._editor.active() is None:
                self.event_generate(MainApp.EVENT_DOC_EXIST, state=0)

    def menu_help_about_(self):
        msg = '''
It's an Electrical Diary app.
You can record everything in life at will.

Chinese saying: rotten pencil surpasses smart head. It's more and more obvious when you get aged.

Finished by "Jia xiao dong" on Apr 21, 2019,
At the age of 40.
'''
        tkMessageBox.showinfo(MainApp.TITLE, msg)

    def misc_(self):
        self.title(MainApp.TITLE)
        self.protocol('WM_DELETE_WINDOW', self.quit_)
        self._store = None
        self._notes = {}  # each editor-tab corresponds to a note object
        # lock several widgets until you open a database.
        self.event_generate(MainApp.EVENT_DB_EXIST, state=0)
        self.event_generate(MainApp.EVENT_DOC_EXIST, state=0)

    def menu_doc_attr_(self):
        editor = self._editor.active()
        try:
            record = self._notes[editor]
        except KeyError:
            title = self._editor.get_caption(editor)
            record = jdb.RecordNote(title)
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

    def menu_edit_cut_(self):
        editor = self._editor.active()
        editor.operations()["Cut"]()

    def menu_edit_copy_(self):
        editor = self._editor.active()
        editor.operations()["Copy"]()

    def menu_edit_paste_(self):
        editor = self._editor.active()
        editor.operations()["Paste"]()

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
            editor = self._editor.active()
            if editor is None:
                return
            self._search.attach(editor.core())

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
            self.bind('<Command-s>', self.menu_doc_save_)
            self.bind('<Command-f>', self.menu_edit_find_)
            self.bind('<Command-F>', self.menu_edit_find_)
        else:
            self.unbind('<Command-s>')
            self.unbind('<Command-f>')
            self.unbind('<Command-F>')

    def edit_underline_(self):
        try:
            editor = self._editor.active()
            core = editor.core()
            full_included = False
            it = iter(core.tag_ranges('underline'))
            for start in it:
                end = it.next()
                if core.compare(start, '<=', tk.SEL_FIRST) and core.compare(end, '>=', tk.SEL_LAST):
                    full_included = True
                    break
            if full_included:
                core.tag_remove('underline', tk.SEL_FIRST, tk.SEL_LAST)
            else:
                core.tag_add('underline', tk.SEL_FIRST, tk.SEL_LAST)
            editor.on_modified()
        except:
            pass

    def edit_insert_image_(self):
        extensions = tuple(Image.registered_extensions().keys())
        filename = tkFileDialog.askopenfilename(filetypes=[('Image File', extensions)])
        if filename is '':
            return
        editor = self._editor.active()
        image = jtk.ImageBox(editor, image=open(filename), ext=os.path.splitext(filename)[1])
        editor.core().window_create(tk.INSERT, window=image)
        editor.on_modified()

    def doc_export_html_(self):
        pass

    def collect_misc_(self, text):
        """
        @return tuple(json, bytes). Either could be '' (empty str).
        """
        windows = text.window_names()
        try:
            windows = map(text.nametowidget, windows)
        except tk.TclError:
            pass
        finally:
            # 1. sum up all images
            buf = io.BytesIO()
            jfp = jex.FilePile(buf, 'w')
            windows.sort(cmp=lambda i, j: -1 if text.compare(i, '<', j) else 1)
            images = []
            for i, w in enumerate(windows):
                pos = text.index(w)
                data, scale, ext = w.get_data()
                image_name = '%s%s' % (i, ext)
                jfp.append(image_name, data)
                images.append(dict(name=image_name, pos=pos, scale=scale))
            jfp.close()
            root = {}
            if len(images) > 0:
                root["image"] = images
                bulk = buf.getvalue()
            else:
                bulk = ''
            # 2. sum up all underlines
            it = iter(text.tag_ranges('underline'))
            underlines = ['%s %s' % (str(s), str(next(it))) for s in it]
            if len(underlines) > 0:
                root["underline"] = underlines
            idx = '' if len(root) == 0 else json.dumps(root)
            return idx, bulk

    def config_core(self, text):
        text.tag_config('underline', underline=1)

    def load_content_(self, editor, text, spec, bulk):
        core = editor.core()
        # 1. plain text
        core.insert(tk.END, text)
        try:
            idx = json.loads(spec)
            jfp = jex.FilePile(io.BytesIO(bulk))
            # 2. images
            for i in idx.pop('image', []):
                try:
                    fd = jfp.open(i['name'])
                    ext = os.path.splitext(i['name'])[1]
                    image = jtk.ImageBox(core, image=io.BytesIO(fd.read()), scale=i['scale'], ext=ext)
                    core.window_create(i['pos'], window=image)
                    fd.close()
                except Exception as e:
                    core.insert(i['pos'], '?')
            # 3. underline
            for pos in idx.pop('underline', []):
                pos = pos.split(' ')
                core.tag_add('underline', *pos)
            jfp.close()
        except RuntimeError:
            print('bulk data cannot be extracted.')
        except Exception as e:
            pass  #print('Error: %s' % e)
        editor.monitor_change()


def main():
    MainApp().mainloop()


def make_toolbar_gray():
    im = Image.open('toolbar.jpg').convert('L')
    im.save('toolbar.jpg', 'JPEG', bits=8)


if __name__ == "__main__":
    main()
