# -*- coding: utf-8 -*-
"""
author: Rafal Miecznik
contact: ravmiecznk@gmail.com
"""

#import pytest
#import pytest_mccabe
from io import BytesIO
#from call_tracker import method_call_track

#@shallow_track_class_calls
class CircIoBuffer(BytesIO):
    def __init__(self, initial_buffer=bytearray(), size=1024):
        initial_buffer = initial_buffer[-size:]
        bytes_len = len(initial_buffer)
        BytesIO.__init__(self, initial_buffer)
        self._available = bytes_len
        self._limit = size
        self._head = 0
        self._tail = self._available % self._limit
        self._set_head(bytes_len)
        self.__write_locked = False

    def lock_write(self):
        self.__write_locked = True

    def unlock_write(self):
        self.__write_locked = False

    def available(self):
        return self._available

    def _write(self, bytes):
        bytes_len = len(bytes)
        self._available = self._available + bytes_len
        if self._available > self._limit:
            self._available = self._limit
        self.seek(self._tail)
        BytesIO.write(self, bytes)
        self._set_head(bytes_len)
        self._set_tail(bytes_len)

    def write(self, bytes):
        """
        bytes_1 and bytes_2: this split avoids scenario when head reaches the tail
        :param bytes:
        :return:
        """
        if not self.__write_locked:
            bytes = bytes[-self._limit:]
            bytes_1 = bytes[0: self._limit - self._tail]
            bytes_2 = bytes[self._limit - self._tail:]
            self._write(bytes_1)
            self._write(bytes_2)
            return True
        else:
            return False

    def _set_head(self, bytes_amount, read_flag=False):
        if self._available >= self._limit or read_flag:
            self._head = (self._head + bytes_amount) % self._limit

    def _set_tail(self, bytes_amount):
        self._tail = (self._tail + bytes_amount) % self._limit
        self.seek(self._tail)
        if self._available == self._limit:
             self._head = self._tail

    def _set_available(self, bytes_amount):
        self._available = self._available + bytes_amount
        ### tests shows that below section may be an overhead ###
        # if self._available < 0:
        #     self._available = 0
        # elif self._available > self._limit:
        #     self._available = self._limit

    def writelines(self, sequence_of_strings=''):
        raise NotImplementedError

    def read(self, amount=None):
        amount = amount if amount != None else self._available
        result = self.peek(amount)
        if result:
            self._set_head(amount, read_flag=True)
            self._set_available(-amount)
        return result

    def __len__(self):
        return self._available

    def peek(self, amount=None):
        """
        Check current content of buffer
        :param amount:
        :return:
        """
        result = ''
        if self._available:
            amount = amount if amount != None else self._available
            self.seek(self._head)
            result = BytesIO.read(self, amount)
            if self.tell() == self._limit:
               self.seek(0)
               result += BytesIO.read(self, amount - len(result))
        return result

    def flush(self):
        self.__init__(initial_buffer='', size=self._limit)

    def flush_until(self, sequence=''):
        cb = CircIoBuffer(size=len(sequence))
        while sequence not in cb:
            char = self.read(1)
            if char == '':
                break
            cb.write(char)

    def show(self):
        content = self.peek()
        content += ' '*(self._limit - len(content))
        main = '|{}|'.format('|'.join(list(content)))
        top = ' '*(len(main))
        bottom = top
        top = insert_str(top, 'H', self._head)
        bottom = insert_str(bottom, 'T', self._tail)
        output = '{} <-{}\n'.format(top, self._head)
        output += '{}  {}\n'.format(main, self._available)
        output += '{} <-{}'.format(bottom, self._tail)
        return output

    def __str__(self):
        tell = self.tell()
        self.seek(0)
        res = self.read()
        self.seek(tell)
        return res

    def __contains__(self, item):
        return item in self.peek()

def insert_str(string, substring, pos):
    pos = pos*2 + 1
    string = string[0:pos] + substring + string[pos + len(substring):]
    return string

if __name__ == "__main__":
    cb = CircIoBuffer(size=10)
    cb.write('rafal')
    cb.write('rafal')
    for i in '123456':
        cb.write(i)
        print(cb.peek())

