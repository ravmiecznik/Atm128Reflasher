"""
author: Rafal Miecznik
contact: ravmiecznk@gmail.com
"""

import pytest

from circ_io_buffer import CircIoBuffer

TEST_STRING = 'test string'
TEST_STRING_LEN = len(TEST_STRING)


def test_circbuffer_init():
    """"Check if circ buffer is IOBase instance"""
    from io import IOBase
    cb = CircIoBuffer()
    assert isinstance(cb, IOBase)


def test_circ_buffer_len():
    cb = CircIoBuffer(TEST_STRING)
    assert len(TEST_STRING) == len(cb)


def test_tail_circularity():
    cb = CircIoBuffer(size=5)
    cb.write('12')
    assert cb.tell() == 2
    cb.write('345')
    assert cb.tell() == 0


def test_head_marker():
    cb = CircIoBuffer(size=5)
    assert cb._head == 0
    cb = CircIoBuffer(size=5, initial_buffer='12')
    assert cb._head == 0
    cb = CircIoBuffer(size=5, initial_buffer='12345')
    assert cb._head == 0
    cb.write('12')
    assert cb._head == 2
    cb.write('3450')
    assert cb._head == 1
    cb.write('0000')
    assert cb._head == 0


def test_tail_markger():
    size = 5
    cb = CircIoBuffer(size=size)
    assert cb._tail == 0
    cb = CircIoBuffer(size=size, initial_buffer='12')
    assert cb._tail == 2
    cb = CircIoBuffer(size=size, initial_buffer='12345')
    assert cb._tail == 0
    cb.write('12')
    assert cb._tail == 2
    cb.write('3451')
    assert cb._tail == 1
    assert len(cb) == size
    assert cb._available == size


def test_read():
    cb = CircIoBuffer(initial_buffer=TEST_STRING, size=TEST_STRING_LEN)
    assert len(cb) == TEST_STRING_LEN
    assert cb.read() == TEST_STRING
    assert len(cb) == 0


def test_read_big_buffers():
    test_string = '12345'
    size = len(test_string)
    cb = CircIoBuffer(size=size, initial_buffer=test_string)
    assert len(cb) == len(test_string)
    cb.write('x')
    assert len(cb) == len(test_string)
    assert cb.read(1) == '2'
    assert len(cb) == len(test_string) - 1
    assert cb.read() == '345x'
    assert len(cb) == 0
    assert cb._tail == 1
    assert cb._head == 1
    cb.write('a')
    assert len(cb) == 1
    assert cb._tail == 2
    assert cb._head == 1
    assert cb.read(0) == ''
    assert cb._tail == 2
    assert cb._head == 1
    cb.write('12345')
    assert cb._tail == (2 + size) % size
    assert cb._head == (2 + size) % size
    assert cb.read() == '12345'
    cb.write('abcde67890x')
    assert cb.read() == '7890x'


def test_peek():
    cb = CircIoBuffer(TEST_STRING)
    assert cb.peek() == TEST_STRING
    assert len(cb) == TEST_STRING_LEN
    assert cb.read() == TEST_STRING
    assert len(cb) == 0


def test_flush():
    cb = CircIoBuffer(TEST_STRING, size=123)
    cb.flush()
    assert cb._limit == 123
    assert cb.read() == ''
    cb.write('tmp')
    assert len(cb) == 3
    assert cb.read() == 'tmp'
    cb.write(123*'dd')
    assert len(cb) == 123
    assert cb.read() == 123*'d'


def test_contains():
    cb = CircIoBuffer(TEST_STRING)
    assert 'test' in cb
    cb.read(len('test'))
    assert 'test' not in cb


def test_show():
    cb = CircIoBuffer(TEST_STRING, size=TEST_STRING_LEN)
    print
    expected_result = ' H                      <-0\n' \
                      '|t|e|s|t| |s|t|r|i|n|g|  11\n' \
                      ' T                      <-0'
    assert cb.show() == expected_result


def test_writelines():
    cb = CircIoBuffer()
    try:
        cb.writelines()
    except NotImplementedError:
        pass


def test_flush_until():
    cb = CircIoBuffer('this is test buffer', size=20)
    cb.flush_until('test')
    assert cb.read() == ' buffer'

def test_flush_unit_sequence_not_present():
    cb = CircIoBuffer('this is test buffer', size=20)
    cb.flush_until('xxx')
    assert cb.available() == 0


if __name__ == "__main__":
    pytest
