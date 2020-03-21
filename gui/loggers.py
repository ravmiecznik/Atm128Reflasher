#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
author: Rafal Miecznik
contact: ravmiecznk@gmail.com
"""
import logging, time, os, sys

#FORMATTING: https://docs.python.org/3/library/logging.html#logging.Formatter
# Parameters
# name – The name of the logger used to log the event represented by this LogRecord. Note that this name will always
#   have this value, even though it may be emitted by a handler attached to a different (ancestor) logger.#
# level – The numeric level of the logging event (one of DEBUG, INFO etc.) Note that this is converted to two
#   attributes of the LogRecord: levelno for the numeric value and levelname for the corresponding level name.
# pathname – The full pathname of the source file where the logging call was made.
# lineno – The line number in the source file where the logging call was made.
# msg – The event description message, possibly a format string with placeholders for variable data.
# args – Variable data to merge into the msg argument to obtain the event description.
# exc_info – An exception tuple with the current exception information, or None if no exception information is available.
# func – The name of the function or method from which the logging call was invoked.
# sinfo – A text string representing stack information from the base of the stack in the current thread, up to the logging call.

def tstamp():
    ts = time.localtime()
    ts_ms = time.time()%60
    ts_ms = "{:.3f}".format(ts_ms).zfill(6)
    return "{:02d}:{:02d}:{}:".format(ts.tm_hour, ts.tm_min, ts_ms)

log_format = '[%(asctime)s %(name)s %(filename)s:%(lineno)d in func:%(funcName)s thr:%(threadName)s]: %(levelname)s %(message)s'

def create_logger(name, log_path=None, format=log_format, log_level=logging.DEBUG):
    log_formatter = logging.Formatter(format)
    logger = logging.getLogger(name)
    if log_path is not None:
        log_file = '{}.log'.format(name)
        log_file = os.path.join(log_path, log_file)
        with open(log_file, 'w') as lf:
            lf.write('')
        if not logger.handlers:
            handler = logging.FileHandler(log_file)
            handler.setFormatter(log_formatter)
            logger.addHandler(handler)
    else:
        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(log_formatter)
            logger.addHandler(handler)

    logger.setLevel(log_level)
    return logger

