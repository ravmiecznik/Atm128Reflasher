"""
author: Rafal Miecznik
contact: ravmiecznk@gmail.com
"""
from PyQt4 import QtGui
import sys, time
from gui_thread import GuiThread
import unittest
from threading import Thread

class MainW(QtGui.QMainWindow):
    """
    Mainw to host and run one single thread
    """
    def __init__(self):
        QtGui.QMainWindow.__init__(self)

    def fetch_thread(self, mt):
        self.mt = mt
        return self.mt

    def get_thread(self):
        return self.mt

    def start_thread(self):
        self.mt.start()
        while self.mt.isRunning(): time.sleep(0.001)
        return


def some_fun():
    print some_fun.__name__




class TestMainThread(unittest.TestCase):

    def setUp(self):
        """
        Reset main window
        :return:
        """
        while self.mainw.__dict__:
            for k in self.mainw.__dict__:
                del self.mainw.__dict__[k]
                break

        while GuiThread.threads:
            GuiThread.threads[0].kill()
            break

    def test_create_single_thread(self):
        def modify_test_var_thread():
            self.mainw.test_var = 99
        thread = GuiThread(process=modify_test_var_thread)
        self.mainw.fetch_thread(thread)
        self.mainw.start_thread()
        self.assertEquals(self.mainw.test_var, 99)
        self.assertEquals(thread.t_id, 0)


    def test_create_three_threads_with_args(self):
        def modify_test_var_thread(val):
            self.mainw.test_var = val

        for i in range(3):
            thread = GuiThread(process=modify_test_var_thread, args=(i,))
            self.mainw.fetch_thread(thread)
            self.mainw.start_thread()
            self.assertEquals(thread.t_id, i)
            self.assertEquals(self.mainw.test_var, i)
        self.assertEquals(GuiThread.num_of_threads(), 3)


    def test_create_periodic_thread(self):
        def modify_test_var_thread():
            try:
                self.mainw.test_var += 1
            except AttributeError:
                self.mainw.test_var = 0

        periodic_thread = GuiThread(process=modify_test_var_thread, period=0.5)
        self.mainw.fetch_thread(periodic_thread).start()
        time.sleep(2)
        periodic_thread.kill()
        self.assertEquals(self.mainw.test_var, 4)

    def test_create_periodic_thread_with_delay(self):
        def modify_test_var_thread():
            try:
                self.mainw.test_var += 1
            except AttributeError:
                self.mainw.test_var = 0

        period = 0.5
        delay = 0.3
        sleep = 2
        periodic_thread = GuiThread(process=modify_test_var_thread, period=period, delay=delay)
        self.mainw.fetch_thread(periodic_thread).start()
        time.sleep(sleep)
        periodic_thread.kill()
        self.assertEquals(self.mainw.test_var, sleep/period - 1)


    def test_periodic_thread_suspend_and_resume(self):
        def modify_test_var_thread():
            try:
                self.mainw.test_var += 1
            except AttributeError:
                self.mainw.test_var = 0

        period = 0.5
        suspend_time_units = 3
        periodic_thread = GuiThread(process=modify_test_var_thread, period=period)
        self.mainw.fetch_thread(periodic_thread).start()
        t0 = time.time()
        time.sleep(period * 2)
        periodic_thread.suspend()
        time.sleep(period * suspend_time_units)
        periodic_thread.resume()
        time.sleep(period * 2)
        periodic_thread.kill()
        periodic_thread.wait()
        t_tot = round(time.time() - t0)
        self.assertEquals(self.mainw.test_var, t_tot/period - suspend_time_units - 1)


    def test_suspend_all_threads(self):
        def modify_test_var_thread():
            try:
                self.mainw.test_var += 1
            except AttributeError:
                self.mainw.test_var = 0

        period = 0.2
        num_of_threads = 3
        for i in range(num_of_threads):
            thread = GuiThread(process=modify_test_var_thread, period=period)
            self.mainw.fetch_thread(thread)
            thread.start()
        time.sleep(1)
        GuiThread.suspend_all_threads()
        time.sleep(1)
        GuiThread.kill_all_threads()
        self.assertEquals(self.mainw.test_var, 14)
        self.assertEquals(GuiThread.num_of_threads(), 0)

    def test_resume_all_threads(self):
        def modify_test_var_thread():
            try:
                self.mainw.test_var += 1
            except AttributeError:
                self.mainw.test_var = 0

        period = 0.2
        num_of_threads = 3
        for i in range(num_of_threads):
            thread = GuiThread(process=modify_test_var_thread, period=period)
            self.mainw.fetch_thread(thread)
            thread.start()
        time.sleep(1)
        GuiThread.suspend_all_threads()
        time.sleep(1)
        GuiThread.resume_all_threads()
        time.sleep(period * 2)
        GuiThread.kill_all_threads()
        self.assertTrue(self.mainw.test_var > 14)
        self.assertEquals(GuiThread.num_of_threads(), 0)

    @classmethod
    def tearDownClass(cls):
        cls.mainw.close()

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    myapp = MainW()
    myapp.show()
    TestMainThread.mainw = myapp
    test_thread = Thread(target=unittest.main)
    test_thread.start()
    app.exec_()
    print 'bye'
    sys.exit()
