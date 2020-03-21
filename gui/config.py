import os
from loggers import create_logger

LOG_PATH = os.path.join(os.getcwd(), "DBG")

if not os.path.isdir(LOG_PATH):
    os.mkdir(LOG_PATH)

thread_logger = create_logger(name="thread_logger", log_path=LOG_PATH)