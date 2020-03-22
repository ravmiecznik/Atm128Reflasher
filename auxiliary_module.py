"""
author: Rafal Miecznik
contact: ravmiecznk@gmail.com

Some useful tools...
"""

import struct

class WindowGeometry(object):
    def __init__(self, QtGuiobject):
        self.pos_x = QtGuiobject.x()
        self.pos_y = QtGuiobject.y()
        self.height = QtGuiobject.height()
        self.width = QtGuiobject.width()

    def get_position_to_the_right(self):
        pos_x = self.width + self.pos_x
        return pos_x

    def __call__(self):
        return self.pos_x, self.pos_y, self.width, self.height


def null_function(*args, **kwargs):
    print("args: {}, kwargs: {}".format(args, kwargs))


class Uint16(int):
    def __init__(self, value, **kwargs):
        int.__init__(self, value % 0xffff, **kwargs)

    def __new__(self, value, **kwargs):
        obj = int.__new__(self, value % 0xffff, **kwargs)
        return obj

    def __add__(self, other):
        return Uint16(int.__add__(self, other))

    def __sub__(self, other):
        return Uint16(int.__sub__(self, other))

    def __mul__(self, other):
        return Uint16(int.__mul__(self, other))

    def __div__(self, other):
        return Uint16(int.__div__(self, other))


class MeanCalculator():
    def __init__(self):
        self.__val = float(0)
        self.__cnt = 0

    def count(self, val):
        self.__val += val
        self.__cnt += 1

    def calc(self):
        try:
            return self.__val/self.__cnt
        except ZeroDivisionError:
            return 0

    def __add__(self, other):
        self.count(other)
        return self

    def __repr__(self):
        return "Mean {}".format(self.calc())


#format raw string to hex values
raw_str_to_hex = lambda raw: (len(raw) * "{:02X} ").format(*[ord(i) for i in raw])


"""
https://docs.python.org/3/library/struct.html

FORMAT      C Type          Python Type         Standard Size
-------------------------------------------------------------
h           short           integer             2
H           unsigned short  integer             2
b           signed char     integer             1
B           unsigned char   integer             1
...and more
"""

raw_to_uint16 = lambda raw: struct.unpack('H', raw)[0]
raw_to_uint8 = lambda raw: struct.unpack('B', raw)[0]
raw_to_uint = lambda raw: raw_to_uint16(raw) if len(raw) == 2 else raw_to_uint8(raw)

uint16_to_raw = lambda  u8: struct.pack('H', u8)
uint8_to_raw = lambda  u8: struct.pack('B', u8)
uint_to_raw = lambda u: uint16_to_raw(u) if u > 0xff else uint8_to_raw(u)



if __name__ == "__main__":
    print raw_to_uint('\xff\x01')