#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Database related functions are organized here.
"""

import sqlite3
import datetime
import jex
import zlib
import hashlib


DocCols = jex.enum2('id', 'title', 'text', 'bulk', 'tags', 'date', 'COUNT')
TagCols = jex.enum2('id', 'name', 'base', 'COUNT')


class DBRecordTag(object):
    """
    @note: represents a database record in table "tags". For the table's columns, refer
           to the definition of enum "TagCols".
    """
    def __init__(self, name, base=0, sn=0):
        self._name = name    # tag name
        self._parent = base  # tags can be further divided into more detailed category,
        self._children = []  # e.g., creatures can be animals, birds, fishes, bacteria.
        self._sn = sn        # serial number

    @property
    def sn(self):
        return self._sn

    @sn.setter
    def sn(self, value):
        self._sn = value

    @property
    def children(self):
        return self._children

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, value):
        self._parent = value

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    def add_child(self, tag):
        if tag not in self._children:
            self._children.append(tag)

    def add_descendant(self, tag):
        if tag.parent == self.sn:
            self.add_child(tag)
            return True
        for i in self._children:
            if i.add_descendant(tag):
                return True
        return False

    def remove_descendant(self, tag):
        if tag in self._children:
            self._children.remove(tag)
            return True
        for i in self._children:
            if i.remove_descendant(tag):
                return True
        return False

    def find(self, sn):
        if self._sn == sn:
            return self
        for i in self._children:
            tag = i.find(sn)
            if tag is not None:
                return tag
        return None

    def all_family(self):
        family = [self._sn]
        for i in self._children:
            another = i.all_family()
            family.extend(another)
        return family

    @staticmethod
    def forest_organize(tags, tag):
        for i in tags:
            if i.sn == tag.parent:
                i.add_child(tag)
                return True
            if DBRecordTag.forest_organize(i.children, tag):
                return True
        return False

    @staticmethod
    def forest_find(tags, sn):
        for i in tags:
            t = i.find(sn)
            if t is not None:
                return t
        return None

    @staticmethod
    def forest_delete(tags, tag):
        for i in tags[:]:
            if i == tag:
                tags.remove(tag)
                return True
            if i.remove_descendant(tag):
                return True
        return False

    @staticmethod
    def forest_add(tags, tag):
        if tag.parent == 0:
            tags.append(tag)
            return True
        for i in tags:
            if i.add_descendant(tag):
                return True
        return False


class DBRecordDoc(object):
    """
    @note: represents a database record in table "docs". For the table's columns, refer
           to the definition of enum "DocCols".
    """
    def __init__(self, title, text=None, bulk=None, tags=[], date=None, sn=0):
        self._sn = sn
        self._title = title
        self._text = text  # json-format string
        self._bulk = bulk  # possible values: None, bytes 
        self._tags = tags
        self._date = datetime.date.today() if date is None else date
        self._dirty_flags = set()
        #
        # textual content and images are large data. In order to save memory space,
        # use digests to judge if they're changed.
        self._digests = {}

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        if self._title != value:
            self._title = value
            self.mark_dirty_(DocCols.title)

    @property
    def script(self):
        return self._text

    @script.setter
    def script(self, value):
        byte_array = value.encode(encoding='utf-8')  # md5 can't process unicode directly
        digest = hashlib.md5(byte_array).digest()
        if self._digests.get('text', '') == digest:
            return
        self._text = value
        self._digests.update(text=digest)
        self.mark_dirty_(DocCols.text)

    @property
    def bulk(self):
        return self._bulk

    @bulk.setter
    def bulk(self, value):
        digest = hashlib.md5(value).digest()
        if self._digests.get('bulk', '') == digest:
            return
        self._bulk = value
        self._digests.update(bulk=digest)
        self.mark_dirty_(DocCols.bulk)

    @property
    def date(self):
        return self._date

    @date.setter
    def date(self, value):
        self._date = value
        self.mark_dirty_(DocCols.date)

    @property
    def tags(self):
        return self._tags

    @tags.setter
    def tags(self, value):
        new = set([i.sn for i in value])
        old = set([i.sn for i in self._tags])
        if new == old:
            return
        self._tags[:] = value
        self.mark_dirty_(DocCols.tags)

    @staticmethod
    def tags_str(tags):
        return ','.join(['%d' % i.sn for i in tags])

    @property
    def sn(self):
        return self._sn

    @sn.setter
    def sn(self, value):
        self._sn = value

    @property
    def fragile(self):
        """
        sn = 0: it's newly created and has not been saved in database.
        """
        return self._sn == 0

    def mark_dirty_(self, col):
        self._dirty_flags.add(col)

    def after_saving(self):
        self._dirty_flags.clear()
        # release their memory, and only keep their digests
        self._text = None
        self._bulk = None

    @property
    def unsaved_fields(self):
        return self._dirty_flags

    def init_digest(self, **kw):
        for k, v in kw.items():
            if k == 'text':
                v = v.encode(encoding='utf-8')
            self._digests.update({k: hashlib.md5(v).digest()})


class DocBase(object):
    """
    @note Database class, which is storing all documents.
    """
    date_support = {'detect_types': sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES}
    find_words = None

    def __init__(self, filename):
        self._filename = filename
        self._con = sqlite3.connect(filename, **DocBase.date_support)
        self._tags = self.load_all_tags()

    def read_doc(self, sn):
        """
        @return: tuple(str, bytes)
        """
        try:
            cur = self._con.cursor()
            cur.execute('SELECT text, bulk FROM docs WHERE id=?', (sn,))
            t, b = cur.fetchone()
            return DocBase.unzip_(t), b
        except Exception as e:
            print('Error on select: %s' % e)

    def copy_docs(self, sn_set, database):
        """
        Copy a few records to another database.
        @param sn_set: a set of record IDs.
        @param database: filename of destination database.
        """
        try:
            con = sqlite3.connect(database)
            # check if sn is continuous
            up, down = max(sn_set), min(sn_set)
            if up - down + 1 == len(sn_set):
                condition = 'id <= %d AND id >= %d' % (up, down)
            else:
                condition = 'id in (%s)' % ','.join(str(i) for i in sn_set)
            # filter records
            sql_select = 'SELECT title, text, bulk, date FROM docs WHERE %s' % condition
            cur = self._con.cursor()
            cur.execute(sql_select)
            # write to new database
            sql_insert = 'INSERT INTO docs (title, text, bulk, tags, date) VALUES(?,?,?,?,?)'
            docs = [(ttl, txt, blk, '', dat) for ttl, txt, blk, dat in cur.fetchall()]
            con.executemany(sql_insert, docs)
            con.commit()
            return len(docs)
        except Exception as e:
            print(e)

    def select_doc(self, **conditions):
        try:
            clauses = []
            condition = conditions.pop('title', None)
            if not condition is None:
                clauses.append(condition)
            condition = conditions.pop('from', None)
            if not condition is None:
                clauses.append('date >= "%s"' % condition)  # date must be quoted using marks
            condition = conditions.pop('to', None)
            if not condition is None:
                clauses.append('date <= "%s"' % condition)
            tags = conditions.pop('tags', None)
            #
            # judge if sn fits in between UPPER and LOWER boundary.
            # NOTE: the sn in database may not be continuous.
            upper = conditions.pop('upper', None)
            lower = conditions.pop('lower', None)
            def in_range(sn):
                if upper and sn > upper:
                    return False
                if lower and sn < lower:
                    return False
                return True
            if any([upper, lower]):
                self._con.create_function('InRange', 1, in_range)
                clauses.append('InRange(id)')
            #
            # full-text search
            words = conditions.pop('content', None)
            def contain_words(text):
                content = DocBase.unzip_(text)
                return DocBase.find_words(content, words)
            if not words is None:
                self._con.create_function('Contain', 1, contain_words)
                clauses.append('Contain(text)')
            # construct final SQL statement
            sql = 'SELECT id,title,tags,date FROM docs'
            if len(clauses) > 0:
                sql = '%s WHERE %s' % (sql, ' AND '.join(clauses))
            cur = self._con.cursor()
            cur.execute(sql)
            docs = []
            for sn, tt, tg, dt in cur.fetchall():
                tg = [] if tg == '' else [int(i) for i in tg.split(',')]
                tg = [DBRecordTag.forest_find(self._tags, i) for i in tg]
                if not tags is None:
                    if not any(DBRecordTag.forest_find(tags, i.sn) for i in tg):
                        continue
                docs.append(DBRecordDoc(tt, None, None, tg, dt, sn))
            return docs
        except Exception as e:
            print('Error on select: %s' % e)

    def update_doc(self, record):
        args = {}
        cols = []
        for i in record.unsaved_fields:
            if i == DocCols.title:
                args['ttl'] = record.title
                cols.append('title=:ttl')
            elif i == DocCols.text:
                args['txt'] = DocBase.zip_(record.script)
                cols.append('text=:txt')
            elif i == DocCols.bulk:
                args['blk'] = sqlite3.Binary(record.bulk)
                cols.append('bulk=:blk')
            elif i == DocCols.tags:
                args['tgs'] = DBRecordDoc.tags_str(record.tags)
                cols.append('tags=:tgs')
            elif i == DocCols.date:
                args['dat'] = record.date
                cols.append('date=:dat')
        try:
            if len(cols) > 0:
                sql = 'UPDATE docs SET %s WHERE id=%d' % (', '.join(cols), record.sn)
                self._con.execute(sql, args)
                self._con.commit()
        except Exception as e:
            print('Error on update: %s' % e)
        finally:
            record.after_saving()

    def insert_doc(self, record):
        try:
            sql = 'INSERT INTO docs (title, text, bulk, tags, date) VALUES(?,?,?,?,?)'
            args = (record.title,                 # title
                    DocBase.zip_(record.script),  # main text
                    sqlite3.Binary(record.bulk),  # images
                    DBRecordDoc.tags_str(record.tags),
                    record.date)
            cur = self._con.cursor()
            cur.execute(sql, args)
            self._con.commit()
            record.sn = cur.lastrowid
            record.after_saving()
        except Exception as e:
            print('Error on insertion: %s' % e)

    def delete_doc(self, sn):
        try:
            self._con.execute('DELETE FROM docs WHERE id=?', (sn,))
            self._con.commit()
            return True
        except Exception as e:
            print('Error on deletion: %s' % e)
            return False

    def close(self):
        self._con.close()
        self._filename = None

    def load_all_tags(self):
        try:
            cur = self._con.cursor()
            cur.execute('SELECT * FROM tags')
            tags = [DBRecordTag(n, b, s) for s, n, b in cur.fetchall()]
            root = 0
            for tag in tags[:]:
                if tag.parent == 0:
                    root += 1
                elif DBRecordTag.forest_organize(tags, tag):
                    tags.remove(tag)
            if root != len(tags):
                raise Exception('Error: dangling node: %s found. Program has bugs!' % (len(tags)-root))
            return tags
        except Exception as e:
            print('Error on loading tags: %s' % e)

    def insert_tag(self, tag):
        try:
            cur = self._con.cursor()
            cur.execute('INSERT INTO tags (%s, %s) VALUES(?,?)' %
                        (TagCols.name[1], TagCols.name[2]),
                        (tag.name, tag.parent))
            tag.sn = cur.lastrowid
            self._con.commit()
        except Exception as e:
            print('Error on insertion: %s' % e)

    def delete_tag(self, tag):
        try:
            family = tag.all_family()
            family.reverse()
            family = [(i,) for i in family]  # turn to SQLite format
            cur = self._con.cursor()
            cur.executemany('DELETE FROM tags WHERE id=?', family)
            self._con.commit()
        except Exception as e:
            print('Error on deletion: %s' % e)

    def update_tag(self, tag):
        try:
            cur = self._con.cursor()
            cur.execute('UPDATE tags SET name=?, base=? WHERE id=?', (tag.name, tag.parent, tag.sn))
            self._con.commit()
        except Exception as e:
            print('Error on update: %s' % e)

    def get_all_tags(self):
        return self._tags

    def check_use(self, tag):
        def in_use(owned):
            if owned == '':
                return False
            owned = [int(i) for i in owned.split(',')]
            return any(tag.find(i) for i in owned)
        try:
            self._con.create_function('InUse', 1, in_use)
            cur = self._con.cursor()
            cur.execute('SELECT COUNT(id) from docs WHERE InUse(tags)')
            num, = cur.fetchone()
            return num
        except Exception as e:
            print('Error on checking: %s' % e)

    @property
    def source(self):
        return self._filename

    @staticmethod
    def validate(filename):
        def is_column_identical(cursor, table_name, table_columns):
            cursor.execute('PRAGMA table_info (%s)' % table_name)
            structs = cursor.fetchall()
            result = (structs[i][1] == table_columns[i] for i in range(len(table_columns)))
            return all(result)
        try:
            with sqlite3.connect(filename) as con:
                cur = con.cursor()
                tables = {'docs': [DocCols.name[i] for i in range(DocCols.COUNT)],
                          'tags': [TagCols.name[i] for i in range(TagCols.COUNT)]}
                return all(is_column_identical(cur, i, j) for i, j in tables.items())
        except:
            return False

    @staticmethod
    def create_db(filename):
        try:
            sql = '''CREATE TABLE docs (
                id    INTEGER PRIMARY KEY UNIQUE NOT NULL,
                title TEXT NOT NULL,
                text  BLOB,
                bulk  BLOB,
                tags  TEXT,
                date  DATE);
                CREATE TABLE tags (
                id    INTEGER PRIMARY KEY UNIQUE NOT NULL,
                name  TEXT,
                base  INTEGER DEFAULT (0));'''
            con = sqlite3.connect(filename, **DocBase.date_support)
            con.executescript(sql)
            con.commit()
            #
            return DocBase(filename)
        except Exception as e:
            print('Error on creation of DB: %s' % e)
            return None

    @staticmethod
    def zip_(s):
        if len(s) == 0:
            return sqlite3.Binary('')
        s = s.encode(encoding='utf-8')  # zlib accepts only str, not unicode str.
        return sqlite3.Binary(zlib.compress(s, 6))

    @staticmethod
    def unzip_(s):
        if len(s) == 0:
            return ''
        s = zlib.decompress(s)
        return s.decode(encoding='utf-8')

    @staticmethod
    def assign_finder(function):
        DocBase.find_words = function
