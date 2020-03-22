"""
author: Rafal Miecznik
contact: ravmiecznk@gmail.com
creation date: 2020-03-20
"""

import time
import serial
from queue import Queue
from threading import Thread, Lock

from config import thread_logger

dbg = thread_logger.debug


class SerialThread(Thread):
    def __init__(self, target, period=0, delay=0, log_eriod=1, args=(), kwargs={}):
        self.target = target
        self.period = period
        self.delay = delay
        self.args = args
        self.kwargs = kwargs
        self.log_period = log_eriod
        self.__log_tstamp = time.time()
        Thread.__init__(self)

    def target_call(self):
        if time.time() - self.__log_tstamp > self.log_period:
            dbg("Call: {}, args: {}, kwargs: {}, period: {}".format(self.target.__name__, self.args, self.kwargs,
                                                                    self.period))
            self.__log_tstamp = time.time()
        self.target(*self.args, **self.kwargs)

    def run(self):
        time.sleep(self.delay)
        while self.period:
            self.target_call()
            time.sleep(self.period)
        else:
            self.target_call()

    def terminate(self):
        self.period = 0
        if self.is_alive():
            dbg("wait till die...{}".format(self.target.__name__))
        while self.is_alive():
            time.sleep(0.1)
        dbg('terminated: {}'.format(self.target.__name__))


class SerialConnection(serial.Serial):
    def __init__(self, **kwargs):
        self.data_ready_sig = kwargs.pop('data_ready_signal', lambda x:x)
        period = kwargs.get('timeout', 0.002)
        serial.Serial.__init__(self, **kwargs)
        self.reader = SerialThread(target=self.rx_data_thread, period=period)
        self.queue = Queue(maxsize=1024)
        self.reader.start()

    def rx_data_thread(self):
        rx_data = self.read(1024)
        while rx_data:
            self.queue.put(rx_data, timeout=0.1, block=True)
            rx_data = self.read(1024)
        if self.queue.qsize() > 0:
            self.data_ready_sig()

    def close(self):
        self.reader.terminate()
        serial.Serial.close(self)

    def send(self, data):
        self.write(data)



if __name__ == "__main__":
    mutex = Lock()
    def job(s):
        with mutex:
            print job.__name__, s

    t1 = SerialThread(target=job, args=("job1",), period=1)
    t2 = SerialThread(target=job, args=("job2",), delay=0.5, period=0.5)

    t1.start()
    t2.start()