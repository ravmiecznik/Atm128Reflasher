#!/usr/bin/python
"""
author: Rafal Miecznik
contact: ravmiecznk@gmail.com
created: 22.03.2020$
"""

import os
from loggers import create_logger

LOG_PATH = os.path.join(os.getcwd(), "REFLASHER_DBG")

if not os.path.isdir(LOG_PATH):
    os.mkdir(LOG_PATH)

# common thread logger
thread_logger = create_logger(name="thread_logger", log_path=LOG_PATH)