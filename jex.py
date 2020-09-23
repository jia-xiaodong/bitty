#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Auxiliary functions that make programming more natural
are all placed here.
"""

import functools
import struct
import io, sys

def isPython3():
    if sys.version > '3':
        return True
    return False


def is_str(s):
    if isPython3():
        return isinstance(s, str)
    else:
        return isinstance(s, basestring)


if not isPython3():
    def enum1(*sequential, **named):
        """
        @param sequential:
        @param named:
        @return: a dynamically created enum.

        Because in Python prior to 3.4, there's no built-in enum definition. So we have to
        make it ourselves.
        use case:
          Numbers = enum1('ZERO', 'ONE', 'TWO')        --> Numbers.ZERO (aka. 0), Numbers.ONE (aka. 1)
          Numbers = enum1(ONE=1, TWO=2, THREE='three') --> Numbers.THREE (aka. 'three')
          getattr(Numbers, 'TWO') --> Numbers.TWO      --> 2
        """
        enums = dict(zip(sequential, range(len(sequential))), **named)
        return type('Enum', (), enums)  # builtin function: type(new_cls_name, bases, attrs)


    def enum2(*sequential, **named):
        """
        A more powerful enum creation than above
        @param sequential:
        @param named:
        @return: a dynamically created enum.
        this enum has not only above functions, but also a reverse indexing, such as:
        Numbers.name[1]        --> 'ONE'
        Numbers.name['three']  --> 'THREE'
        """
        enums = dict(zip(sequential, range(len(sequential))), **named)
        reverse = dict((value, key) for key, value in enums.iteritems())
        enums['name'] = reverse
        return type('Enum', (), enums)


class InvalidArgumentTypeError(ValueError):
    """
    Raised when the type of an argument to a function is not what it should be.
    """
    def __init__(self, arg_num, func_name, accepted_arg_type):
        self.error = 'The {0} argument of {1}() is not a {2}'\
            .format(arg_num, func_name, accepted_arg_type)

    def __str__(self):
        return self.error


class InvalidArgumentNumberError(ValueError):
    """
    Raised when the number of arguments supplied to a function is incorrect.
    Note that this check is only performed from the number of arguments
    specified in the validate_accept() decorator. If the validate_accept()
    call is incorrect, it is possible to have a valid function where this
    will report a false validation.
    """
    def __init__(self, func_name):
        self.error = 'Invalid number of arguments for {0}()'.format(func_name)

    def __str__(self):
        return self.error


class InvalidReturnType(ValueError):
    """
    As the name implies, the return value is the wrong type.
    """
    def __init__(self, return_type, func_name):
        self.error = 'Invalid return type {0} for {1}()'.format(return_type, func_name)

    def __str__(self):
        return self.error


def ordinal(num):
    """
    Returns the ordinal number of a given integer, as a string.
    eg. 1 -> 1st, 2 -> 2nd, 3 -> 3rd, etc.
    """
    if 10 <= num % 100 < 20:
        return '{0}th'.format(num)
    else:
        ord = {1: 'st', 2: 'nd', 3: 'rd'}.get(num % 10, 'th')
        return '{0}{1}'.format(num, ord)


def accepts(*valid_types):
    """
    A decorator to validate the parameter types of a given function.
    It is passed a tuple of types. eg. (<type 'tuple'>, <type 'int'>)

    Note: It doesn't do a deep check, for example checking through a
          tuple of types. The argument passed must only be types.
    """
    def decorator(f):
        @functools.wraps(f)
        def decorator_wrapper(*args, **kwargs):
            if len(valid_types) is not len(args):
                raise InvalidArgumentNumberError(f.__name__)
            for sn, (actual, valid) in enumerate(zip(args, valid_types)):
                if type(actual) is not valid:
                    order = ordinal(sn+1)
                    raise InvalidArgumentTypeError(order, f.__name__, valid)
            return f(args, kwargs)
        return decorator_wrapper
    return decorator


def returns(valid_type):
    """
    A decorator to validate the return type.
    """
    def decorator(f):
        @functools.wraps(f)
        def decorator_wrapper(*args, **kwargs):
            returned = f(args, kwargs)
            if type(returned) is not valid_type:
                raise InvalidReturnType(valid_type, f.__name__)
            return returned
        return decorator_wrapper
    return decorator


class FilePile:
    """
    Purpose:
      I had planned to bunch a few images into a zip file for storage.
      But I finds out that even for the same file, zip will compress to different bytes.
      It leads to many useless / redundant database writing commit.
      So I have to make one by myself.
      This class only put a few files together into one big file.
    """
    MAGIC_HEAD = b'jxd'
    #
    TYPE_FILENAME = 0
    TYPE_CONTENT = 1

    class FilePiece:
        """
        A FilePiece represents an independent file embedded in FilePile.
        """
        def __init__(self, name, offset, size):
            self.filename = name
            self.offset = offset
            self.size = size

    def __init__(self, fo, mode='r'):
        if mode not in ('r', 'w'):
            raise RuntimeError('Only "w" or "r" supported.')
        #
        if mode == 'r':
            head = fo.read(3)
            if head != FilePile.MAGIC_HEAD:
                raise ValueError('Wrong file format')
        #
        self._mode = mode
        self._fo = fo
        #
        if mode == 'r':
            self._file_list = self.build_file_list_()
        else:
            self._fo.write(FilePile.MAGIC_HEAD)

    def open(self, filename):
        """
        @return io.BytesIO object
        """
        if self._mode != 'r':
            raise RuntimeError('Only "r" mode supports open.')
        for i in self._file_list:
            if i.filename == filename:
                self._fo.seek(i.offset)
                content = self._fo.read(i.size)
                return io.BytesIO(content)
        raise RuntimeError('File %s not found' % filename)

    def append(self, filename, content):
        if self._mode != 'w':
            raise RuntimeError('Only "w" mode supports append.')
        filename = filename.encode(encoding='utf-8')
        length = len(filename)
        tlv = struct.pack('>BI%ds' % length, FilePile.TYPE_FILENAME, length, filename)
        self._fo.write(tlv)
        length = len(content)
        tlv = struct.pack('>BI%ds' % length, FilePile.TYPE_CONTENT, length, content)
        self._fo.write(tlv)

    def close(self):
        if self._mode == 'w':
            self._fo.flush()
        self._fo = None

    def build_file_list_(self):
        """
        For 'read' purpose, scan whole FilePile to build a list beforehand as index.
        """
        try:
            file_list = []
            error = RuntimeError('Wrong file format')
            tl = self._fo.read(5)  # tag (one byte) + length (4 bytes)
            while tl != '':
                tag, length = struct.unpack('>BI', tl)
                if tag != FilePile.TYPE_FILENAME:
                    raise error
                filename = self._fo.read(length)
                filename = filename.decode(encoding='utf-8')
                tl = self._fo.read(5)
                tag, length = struct.unpack('>BI', tl)
                if tag != FilePile.TYPE_CONTENT:
                    raise error
                if length == 0:
                    raise error
                file_list.append(FilePile.FilePiece(filename, self._fo.tell(), length))
                self._fo.seek(length, 1)
                tl = self._fo.read(5)
        finally:
            return file_list


def unit_test1():
    @accepts(int, int)
    @returns(str)
    def add_nums(i1, i2):
        #return i1 + i2     # correct
        return 'xxx'        # Invalid return value
    #print(add_nums(1, 'b'))# Invalid parameter type
    print(add_nums(1, 2))


def unit_test_write():
    """
    @note: The generated file has an extra char '\x0a' in the file end (on Mac).
    I think it's possibly the EOF mark. Because it doesn't exist when debugging
    the 'reading' process. So it can be ignored, I think.
    """
    with open('a.bin', 'wb') as fo:
        fp = FilePile(fo, 'w')
        fp.append('01.jpg', '0123456789abcdef')
        fp.append('02.jpg', 'fedcba9876543210')
        fp.close()


def unit_test_read():
    fp = FilePile(open('a.bin'))
    f = fp.open('01.jpg')
    s = f.read()
    print(s)
    f = fp.open('02.jpg')
    s = f.read()
    print(s)

if __name__ == '__main__':
    unit_test_read()