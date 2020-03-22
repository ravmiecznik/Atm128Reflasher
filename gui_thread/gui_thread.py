"""
author: Rafal Miecznik
contact: ravmiecznk@gmail.com
"""

import time
from PyQt4.QtCore import QThread
from config import LOG_PATH, thread_logger as t_logger

info = t_logger.info


def thread_this_method(**thread_kwargs):
    """
    This is decorator.
    It will turn given method into GuiThread.
    Usage:
    @thread_this_method(GuiThread args)
    def method(self, *method_args)
        method stuff here

    start method as thread:
    method(*method_args).start()

    kill method thread:
    method.kill()

    :param thread_kwargs:
    :return: wrapped GuiThread object
    """
    def method_wraper(method):
        def method_call_wrap(*args, **kwargs):
            instance = args[0]
            info("decorator {}: Converting method {} into {} object".format(thread_this_method.__name__, method.__name__, GuiThread.__name__))
            info("{} with args: {}, kwargs: {}".format(GuiThread.__name__, args, thread_kwargs))
            thread = GuiThread(method, args=args, **thread_kwargs)
            thread.__name__ = "threaded_{}".format(method.__name__)
            setattr(instance, method.__name__, thread)
            return thread
        return method_call_wrap
        method_wraper.__name__ = method.__name__
        method_call_wrap.__name__ = method.__name__
    return method_wraper


class ThreadById:
    def __init__(self, thread, thread_id, alias=None):
        self.thread = thread
        self.id = thread_id
        self.alias = alias

    def __str__(self):
        return "name:{} id:{} alias:{}".format(self.thread.process.__name__, self.id, self.alias)

    def __repr__(self):
        return self.__str__()


class GuiThread(QThread):
    threads = []

    @staticmethod
    def append_new_thread(item):
        t_id = len(GuiThread.threads)
        GuiThread.threads.append(item)
        return t_id

    @staticmethod
    def num_of_threads():
        return len(GuiThread.threads)

    @staticmethod
    def suspend_all_threads():
        for t in GuiThread.threads:
            t.suspend()

    @staticmethod
    def resume_all_threads():
        for t in GuiThread.threads:
            t.resume()

    @staticmethod
    def kill_all_threads():
        while GuiThread.threads:
            GuiThread.threads[0].kill()
            GuiThread.threads.remove(GuiThread.threads[0])

    def __init__(self, process, args=(), kwargs={}, period=0, delay=None, action_when_done=None, trace='full'):
        QThread.__init__(self)
        self.result = None
        self.target = process
        self.__period = period
        self.__delay = delay
        self.__args = args
        self.__kwargs = kwargs
        self.__id = None
        self.__id = GuiThread.append_new_thread(self)
        self.__suspend = False
        self.__action_when_done = action_when_done
        self.__was_suspension_communicated = False
        self.__is_terminated = False
        self.__trace = trace

    def set_delay(self, value):
        self.__delay = value

    def set_args(self, args):
        if not type(args) is tuple:
            raise Exception("Args must be tuple, got: {} type of: {}".format(args, type(args)))
        self.__args = args

    def set_kwargs(self, kwargs):
        if not type(kwargs) is dict:
            raise Exception("Args must be dict, got: {} type of: {}".format(kwargs, type(kwargs)))
        self.__kwargs = kwargs

    def suspend(self):
        self.__suspend = True
        self.__was_suspension_communicated = False

    def resume(self):
        self.__suspend = False

    def returned(self):
        return self.result


    @property
    def t_id(self):
        return self.__id

    def __run(self):
        if self.__delay:
            time.sleep(self.__delay)
        self.__is_terminated = False
        if not self.__suspend:
            # if self.__trace == 'full':
            #     t_logger.debug("start of: {}, period: {}".format(self, self.__period))
            t_logger.debug("start of: {}, period: {}".format(self, self.__period))
            self.result = self.target(*self.__args, **self.__kwargs)
        elif not self.__was_suspension_communicated:
            t_logger.debug("suspended: {}".format(self))
            self.__was_suspension_communicated = True

    def run(self):
        t_logger.debug("Run: {}, ARGS: {}, KWARGS: {}".format(self.target, self.__args, self.__kwargs))
        t_logger.debug("Num of threads: {}".format(len(GuiThread.threads)))
        self.__is_terminated = False
        if self.__delay:
            time.sleep(self.__delay)
        while self.__period != 0 and self.__is_terminated is not True:
            self.__run()
            try:
                time.sleep(self.__period)
            except AttributeError:
                pass
        else:
            self.__run()
        if self.__action_when_done:
            self.__action_when_done()
        # self.kill()
        try:
            GuiThread.threads.remove(self)
        except ValueError:
            pass

    def terminate_s(self):
        """
        Will stop the thread but it is still present in memory
        :return:
        """
        t_logger.debug("Terminating {}".format(self))
        self.__is_terminated = True

    def terminate(self):
        t_logger.debug("Deleting: {}".format(self))
        try:
            GuiThread.threads.remove(self)
        except ValueError:
            pass
        t_logger.debug("Num of threads: {}".format(len(GuiThread.threads)))
        QThread.terminate(self)

    def restart(self):
        """
        Will resurect the thread if terminate was used
        :param period:
        :return:
        """
        self.__is_terminated = False

    def kill(self):
        """
        :return:
        """
        self.terminate()
        t_logger.debug("Deleting: {}".format(self))
        try:
            GuiThread.threads.remove(self)
        except ValueError:
            pass
        t_logger.debug("Num of threads: {}".format(len(GuiThread.threads)))

    def __repr__(self):
        return "{}.{} id:{}".format(GuiThread, self.target.__name__, self.__id)


class SignalThread(GuiThread):
    """
    This thread generator must have defined general_signal static attribute.
    This must come from main window general signal.
    SignalThread.general_signal = main_window.general_signal
    """

    def __init__(self, *args, **kwargs):
        GuiThread.__init__(self, *args, **kwargs)
        self.target = self.to_signal(self.target)


    def to_signal(self, slot):
        """
        This functions will create a signal with slot argument
        :param signal:
        :param slot:
        :return:
        """
        def wrapper():
            try:
                dbg_msg = "emit signal: name:{} id:{}".format(slot.__name__, slot)
                t_logger.debug(dbg_msg)
                return self.general_signal.emit(slot, (), {})
            except AttributeError:
                raise Exception("{doc}\n.{factory}: missing signal attribute. "
                                "Set it up with {factory}.signal=some_signal"
                                .format(doc=SignalThread.__doc__, factory=self))
        wrapper.__name__ = slot.__name__
        wrapper.emit = wrapper.__call__
        return wrapper


if __name__ == "__main__":
    from PyQt4 import QtGui
    from PyQt4.QtCore import QMutex
    import sys
    from circ_io_buffer import CircIoBuffer
    class MainW(QtGui.QMainWindow):
        """
        Mainw to host and run one single thread
        """

        def __init__(self):
            QtGui.QMainWindow.__init__(self)
            self.mutex = QMutex()
            self.thr = GuiThread(process=self.fun, period=0.1)
            self.thr2 = GuiThread(process=self.fun2, period=0.1)
            self.buff = CircIoBuffer(byte_size=15*len('rafal miecznik'))
            self.thr.start()
            self.thr2.start()
            time.sleep(2)
            print self.buff.read()
            for d in dir(self.mutex):
                print d


        def fun(self):
            print self.mutex.tryLock()
            self.buff.write(' rafal')
            self.mutex.unlock()
            #print self.thr.currentThreadId()

        def fun2(self):
            self.mutex.lock()
            self.buff.write(' miecznik')
            #self.mutex.unlock()

                # try:
            #     print "TID", self.thr.currentThreadId()
            # except AttributeError:
            #     pass

    app = QtGui.QApplication(sys.argv)
    thr = app.thread()
    myapp = MainW()
    myapp.thr = thr
    myapp.show()
    app.exec_()
    print 'bye'
    sys.exit()

