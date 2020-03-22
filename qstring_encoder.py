#!/usr/bin/python
"""
author: Rafal Miecznik
contact: ravmiecznk@gmail.com
created: 22.03.2020$
"""


class QStringEncoder(object):
    def __getattr__(self, item):
        return lambda x:x
