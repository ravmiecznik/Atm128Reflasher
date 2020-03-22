"""
author: Rafal Miecznik
contact: ravmiecznk@gmail.com
"""

import os
import configparser
import time
import struct
import textwrap
from queue import Empty
import serial

from PyQt4 import QtGui
from PyQt4.QtGui import QFileDialog
from PyQt4.QtCore import pyqtSignal, QString

from intel_hex_handler import intel_hex_parser
from gui_thread import thread_this_method, GuiThread
from win_com_port_handler import get_com_devices, ListPortInfo

from loggers import create_logger, log_format_basic
from message_handler import MessageSender, MessageReceiver, RxMessage
from serial_handler import SerialConnection
from circ_io_buffer import CircIoBuffer
from config import LOG_PATH

print LOG_PATH

stdout_log = create_logger("stdout", log_path=LOG_PATH)
dbg = stdout_log.debug
PACKET_SIZE = 256*8

logger_name = "signal_calls"
signal_logger = create_logger(logger_name, log_path=LOG_PATH)

rx_logger = create_logger("rx_log", log_path=LOG_PATH, format=log_format_basic)

def general_signal_factory(slot):
    """
    This functions will create a signal with slot argument
    :param signal:
    :param slot:
    :return:
    """
    def wrapper(args=(), kwargs={}):
        try:
            dbg_msg = "emit signal: name:{} id:{} args: {} kwargs: {}".format(slot.__name__, slot, args, kwargs)
            signal_logger.debug(dbg_msg)
            return general_signal_factory.signal.emit(slot, args, kwargs)
        except AttributeError as e:
            raise Exception("{factory}: missing signal attribute. Set it up with {factory}.signal={slot}".format(factory=general_signal_factory.__name__, slot=slot))
    wrapper.__name__ = slot.__name__
    wrapper.emit = wrapper.__call__
    return wrapper


to_signal = general_signal_factory


class TextBrowserInSubWindow(QtGui.QTextBrowser):
    append_sig = pyqtSignal(object, object)

    def __init__(self):
        QtGui.QTextBrowser.__init__(self)
        self.append_sig.connect(QtGui.QTextBrowser.append)

    def append(self, string):
        self.append_sig.emit(self, string)


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


# Progress bar styles #
BLUE_STYLE = """
QProgressBar{
    border: 2px solid grey;
    border-radius: 5px;
    text-align: center
}

QProgressBar::chunk {
    background-color: lightblue;
    width: 10px;
    margin: 1px;
}
"""

RED_STYLE = """
QProgressBar{
    border: 2px solid grey;
    border-radius: 5px;
    text-align: center
}

QProgressBar::chunk {
    background-color: red;
    width: 10px;
    margin: 1px;
}
"""

TOOL_TIP_STYLE_SHEET = """
        QToolTip {
         background-color: rgba(140, 208, 211, 150);
        }
        """

#PUSH BUTTON STYLES
BACKGROUND = "background-color: rgb({r},{g},{b})"
GREEN_STYLE_SHEET = BACKGROUND.format(r=154, g=252, b=41)
GREEN_BACKGROUND_PUSHBUTTON = "QPushButton {}".format("{" + GREEN_STYLE_SHEET + ";}") + TOOL_TIP_STYLE_SHEET


class ColorProgressBar(QtGui.QProgressBar):
    set_val_signal = pyqtSignal(object)

    def __init__(self, parent = None):
        QtGui.QProgressBar.__init__(self)
        self.setStyleSheet(BLUE_STYLE)
        self.parent = parent
        self.set_val_signal.connect(self.setValue)

    def set_red_style(self):
        self.setStyleSheet(RED_STYLE)

    def set_blue_style(self):
        self.setStyleSheet(BLUE_STYLE)

    def set_title(self, title):
        self.setWindowTitle(title)

    def display(self, width=600, height=50, x_offset=400, y_offset=200):
        self.setValue(0)
        current_position_and_size = WindowGeometry(self.parent)
        x_pos = current_position_and_size.get_position_to_the_right()
        self.setGeometry(x_pos - x_offset, current_position_and_size.pos_y + y_offset, width, height)
        self.show()

    def set_red_style(self):
        self.setStyleSheet(RED_STYLE)

    def set_blue_style(self):
        self.setStyleSheet(BLUE_STYLE)


class ComDevicesComboBox(QtGui.QGroupBox):
    def __init__(self):
        QtGui.QGroupBox.__init__(self)
        self.label = QtGui.QLabel("Select serial device and type: ")
        self.label.setFont(QtGui.QFont('Courier New', 12))
        self.descr_label = QtGui.QLabel()

        self.port_dev_combo_box = QtGui.QComboBox(self)
        self.port_dev_combo_box.currentIndexChanged.connect(self.index_changed)

        self.dev_type_combo_box = QtGui.QComboBox(self)
        self.dev_type_combo_box.addItems(['COM', 'BLUETOOTH'])
        self.dev_type_combo_box.setToolTip("Select device type")

        self.test_conn_button = QtGui.QPushButton("Test")
        self.test_conn_button.setToolTip("Test com connection")

        self.connect_button = QtGui.QPushButton("Connect")
        self.connect_button.setToolTip("Connect to device")
        self.default_button_style_sheet = self.connect_button.styleSheet()
        self.connect_button.set_default_style_sheet = lambda: self.connect_button.setStyleSheet(
            self.default_button_style_sheet )
        self.connect_button.set_green_style_sheet = lambda: self.connect_button.setStyleSheet(
            GREEN_BACKGROUND_PUSHBUTTON)

        com_devices = get_com_devices()
        self.encoder = {
            'utf-8': QString.fromUtf8,
            'ascii': QString.fromAscii,
            'ascii-r': QString.fromAscii,
        }[ListPortInfo.encoding_scheme]
        self.devices = [i for i in com_devices]
        self.devices.sort(key=lambda i:i.manufacturer != 'FTDI')
        print [i.manufacturer for i in self.devices]
        print [i.device for i in self.devices]
        self.port_dev_combo_box.addItems([i.device for i in self.devices])

        grid = QtGui.QGridLayout()
        grid.setSpacing(1)
        grid.addWidget(self.label,              0, 0)
        grid.addWidget(self.port_dev_combo_box, 0, 1, 1, 1)
        grid.addWidget(self.dev_type_combo_box, 0, 2, 1, 1)
        grid.addWidget(self.test_conn_button,   0, 3, 1, 1)
        grid.addWidget(self.connect_button,     1, 3, 1, 1)
        grid.addWidget(self.descr_label,        1, 1, 2, 1)

        self.setLayout(grid)

    def index_changed(self, index):
        def wrap(txt):
            if txt:
                return ('\n' + ' '*len('description: ')).join(textwrap.wrap(txt, 30))
        device_info = self.devices[index]
        self.port_dev_combo_box.setToolTip(self.encoder(str(device_info)))
        descr = "manufacturer: {}\n" \
                "description: {}".format(
            wrap(device_info.manufacturer),
            wrap(device_info.description)
        )
        self.descr_label.setText(self.encoder(descr))

    def get_connection_type(self):
        return self.dev_type_combo_box.currentText()

    def get_current_serial_device(self):
        device = filter(lambda i: i.device==self.port_dev_combo_box.currentText(), self.devices)[0]
        return device.device


class Reflasher(QtGui.QWidget):
    #TODO: create serial connection class for communicaton, use emulator from emu_bt_r as reference
    #TODO: the class must be more gneric, should handle bluetooth and FTDI as well
    #TODO: use some abstract classes for that ?

    general_signal_args_kwargs = pyqtSignal(object, object, object)

    def __init__(self, app_status_file, serial_connection=None):
        QtGui.QWidget.__init__(self)
        general_signal_factory.signal = self.general_signal_args_kwargs
        self.general_signal_args_kwargs.connect(self.general_signal_slot)

        self.setWindowTitle("REFLASH")
        self.x_siz, self.y_siz = 600, 400
        self.reflash()

        self.connection = serial_connection if serial_connection is not None else None
        self.rx_buffer = CircIoBuffer(size=258*10)
        self.rx_message_buffer = dict()     # this buffer wont't exceed number of maximum
                                            # possible context ids in msg.id (0xffff)
        self.packets = {}

        self.message_receiver = MessageReceiver(self.rx_buffer)

        self.app_status_file = app_status_file
        self.last_hex_path = self.get_last_hex_file_path()

        # TEXT DISPLAY
        self.line_edit = QtGui.QLineEdit()
        self.text_browser = TextBrowserInSubWindow()
        self.progress_bar = ColorProgressBar(parent=self)
        font = QtGui.QFont('Courier New', 8)
        self.text_browser.setFont(font)
        self.text_browser.setFontPointSize(9)
        line_edit_text = self.last_hex_path if self.last_hex_path else "SELECT PROPER HEX FILE"
        self.line_edit.setText(line_edit_text)


        # WELCOME TEXT
        self.text_browser.append("WELCOME IN ATMEGA128 REFLASH TOOL\n")
        self.text_browser.append("Supported bootloader: atm128_bootloader_v3")
        self.text_browser.append("")
        self.text_browser.append("SELECT CORRECT SERIAL DEVICE AND DEVICE TYPE: COM OR BLUETOOTH")
        self.text_browser.append("SELECT HEX FILE")

        # COM DEVICES LIST
        self.connect()  # create a thread
        self.com_devices = ComDevicesComboBox()
        self.com_devices.test_conn_button.clicked.connect(self.test_connection_slot)
        self.com_devices.connect_button.clicked.connect(self.connect.start)

        #LABEL
        bootloader_git_path = "https://github.com/ravmiecznik/atm128_bootloader_v3"
        self.label = QtGui.QLabel('Bootloader: <a href="{href}">{href}</a>'.format(href=bootloader_git_path))
        self.label.setOpenExternalLinks(True)


        #BUTTONS
        self.browse_button = QtGui.QPushButton()
        browse_icon_path = os.path.join('icons', 'browse.png')
        self.browse_button.setIcon(QtGui.QIcon(browse_icon_path))
        self.browse_button.setToolTip("Browse for hex file")
        self.reflash_button = QtGui.QPushButton("REFLASH")
        self.cancel_button = QtGui.QPushButton("Cancel")
        self.browse_button.setMaximumSize(25, 25)
        self.browse_button.clicked.connect(self.select_file)
        self.reflash_button.clicked.connect(self.check_selected_file)
        self.cancel_button.clicked.connect(self.close)

        # GRID
        mainGrid = QtGui.QGridLayout()
        mainGrid.setSpacing(10)
        mainGrid.addWidget(self.line_edit,      0, 0, 1, 5)
        mainGrid.addWidget(self.browse_button,  0, 5)
        mainGrid.addWidget(self.com_devices,    1, 0, 1, 5)
        mainGrid.addWidget(self.text_browser,   2, 0, 3, 5)
        mainGrid.addWidget(self.progress_bar,   5, 0, 1, 5)
        mainGrid.addWidget(self.cancel_button,  6, 0, 1, 1)
        mainGrid.addWidget(self.reflash_button, 6, 4, 1, 1)
        mainGrid.addWidget(self.label,          7, 0, 1, 5)
        self.setLayout(mainGrid)
        self.__expected_version = None
        self.resize(self.x_siz, self.y_siz)

        flash_icon_path = os.path.join('icons', 'flash.png')
        self.setWindowIcon(QtGui.QIcon(flash_icon_path))

        # threads
        self.test_connection()
        self.data_ready_slot()

    def general_signal_slot(self, objet, args=(), kwargs={}):
        objet(*args, **kwargs)

    def closeEvent(self, event):
        self.close()
        event.accept()

    def close(self):
        print "closing"
        if self.connection and self.connection.isOpen():
            self.connection.close()
        QtGui.QWidget.close(self)

    @thread_this_method()
    def connect(self):
        if not self.connection or not self.connection.isOpen():
            connection = self.establish_connection()
            if connection:
                self.connection = connection
        elif self.connection and self.connection.isOpen():
            self.tmp = GuiThread(process=self.text_browser.append, args=("disconnecting",))
            self.tmp.start()
            self.connection.close()
            self.set_disconnected()

    def set_connected(self):
        to_signal(self.com_devices.connect_button.set_green_style_sheet).emit()
        to_signal(self.com_devices.connect_button.setText)(args=("DISCONNECT",))

    def set_disconnected(self):
        to_signal(self.com_devices.connect_button.set_default_style_sheet)()
        self.com_devices.connect_button.setText("CONNECT")

    @thread_this_method()
    def test_connection(self):
        """
        This thread checks if selected connection is compatible with bootloader3
        :return:
        """
        if not self.connection or not self.connection.isOpen():
            self.connection = self.establish_connection()
            test_connection_thread = GuiThread(process=self.test_connection_with_req, args=(self.connection,))
            test_connection_thread.start()
            while test_connection_thread.returned() is None:
                pass
            if test_connection_thread.returned() is False:
                self.text_browser.append("Connection test failed")
                self.connection = None
            else:
                self.text_browser.append("Connection test passed")
                self.connection.close()
            self.set_disconnected()
        else:
            self.text_browser.append("This connection works already")

    def retrieve_messages(self):
        """
        Do until message available
        """
        msg = self.message_receiver.get_message()
        while msg:
            self.rx_message_buffer[msg.context] = msg
            msg = self.message_receiver.get_message()

    @thread_this_method()
    def data_ready_slot(self):
        """
        Slot called on 'data available in the buffer' event
        Gets data from queue and writes to local circular buffer,
        whehen data in circ buffer call message decoder
        """
        if self.connection:
            try:
                while self.connection.queue.qsize() > 0:
                    raw_data = self.connection.queue.get(timeout=0.1, block=True)
                    if raw_data:
                        self.rx_buffer.write(raw_data)
                if self.rx_buffer.available():
                    self.retrieve_messages()
            except Empty:
                pass

    def test_connection_slot(self):
        self.test_connection.start()

    def get_last_hex_file_path(self):
        config = configparser.ConfigParser()
        config.read(self.app_status_file)

        try:
            path = config['FLASH_HEX_FILE']['path']
            return path
        except KeyError:
            return ''

    def select_file(self):
        print 'select'
        start_dir = os.path.dirname(self.last_hex_path)
        file_path = QFileDialog.getOpenFileName(self, 'Select hex file',
                                                start_dir, "hex files (*.hex *.HEX)")
        if os.path.isfile(file_path):
            config = configparser.ConfigParser()
            config.read(self.app_status_file)
            config['FLASH_HEX_FILE'] = {'path': file_path}
            with open(self.app_status_file, 'w') as cf:
                config.write(cf)
            self.last_hex_path = self.get_last_hex_file_path()
            self.line_edit.setText(self.last_hex_path)

    def check_selected_file(self):
        try:
            file_path = self.line_edit.text()
            with open(file_path) as hex_file:
                hex_lines = hex_file.readlines()
                bin_segments = intel_hex_parser(hex_lines, self.text_browser.append)
                start_address = 0
                self.text_browser.append("Reflash with:\n{}\n".format(file_path))
                self.bin_segments_to_packets(bin_segments[start_address])
                self.reflash.start()
        except IOError:
            self.text_browser.append("File not present or faulty:\n{}".format(file_path))


    def bin_segments_to_packets(self, bin_segments):
        self.packets = {}
        cnt = 0
        print "size", hex(len(bin_segments))
        for i in xrange(0, len(bin_segments), PACKET_SIZE):
            self.packets[cnt] = bin_segments[i:i+PACKET_SIZE]
            cnt += 1
        return self.packets

    def establish_connection(self):
        conn_type = self.com_devices.get_connection_type()
        if conn_type == "COM":
            Connection = SerialConnection
        elif conn_type == "BLUETOOTH":
            self.text_browser.append("{} not yet supported".format(conn_type))
            return

        try:
            self.text_browser.append("Connecting to {}...".format(self.com_devices.get_current_serial_device()))
            connection = Connection(port=self.com_devices.get_current_serial_device(), timeout=0.002, write_timeout=1,
                                        baudrate=115200, data_ready_signal=self.data_ready_slot.start)
        except serial.serialutil.SerialException:
            self.text_browser.append("Can't connect to: {}".format(self.com_devices.get_current_serial_device()))
            return

        if connection.isOpen():
            self.text_browser.append("{}: Connected".format(connection.name))
            self.set_connected()
            return connection

    def test_connection_with_req(self, connection):
        """
        Sends test request
        """
        retx = 3
        timeout = 1
        self.rx_message_buffer = {}
        try:
            MessageSender(connection.write).send(MessageSender.ID.bootloader)
        except serial.serialutil.SerialTimeoutException:
            self.text_browser.append("Connection write test failed")
            return False

        while retx > 0:
            t0 = time.time()
            while 'bootloader3' not in [self.rx_message_buffer[m].msg for m in self.rx_message_buffer]:
                time.sleep(0.1)
                if time.time() - t0 > timeout:
                    MessageSender(connection.write).send(MessageSender.ID.bootloader)
                    retx -= 1
                    break
            else:
                return True
        else:
            self.text_browser.append("Can't enable bootloader")
            return False

    @thread_this_method()
    def reflash(self):
        """
        Main reflashing thread
        """
        reflash_timeout = 30
        rxtimeout = 1
        self.progress_bar.set_val_signal.emit(0)
        if self.connection is None or not self.connection.isOpen():
            self.connection = self.establish_connection()

        test_connection_thread = GuiThread(process=self.test_connection_with_req, args=(self.connection,))
        test_connection_thread.start()
        if test_connection_thread.get_result(timeout=2) is False:
            self.text_browser.append("Bootloader did not repsond !")
            return

        message_sender = MessageSender(self.connection.send)
        message_sender.send(MessageSender.ID.rxflush)
        num_of_packets = len(self.packets)
        t0 = time.time()
        context_to_packet_index_map = {}
        self.rx_message_buffer = {}     #reset rx message buffer
        while self.packets:
            packet_index = self.packets.keys()[0]

            context = message_sender.send(MessageSender.ID.write_to_page,
                                body=struct.pack('H', packet_index) + self.packets[packet_index])

            context_to_packet_index_map[context] = packet_index
            tx_t0 = time.time()
            while context not in self.rx_message_buffer:
                time.sleep(0.01)
                if time.time() - tx_t0 > rxtimeout:
                    dbg('timeout for context: {}'.format(context))
                    break
            else:
                if self.rx_message_buffer[context].id == RxMessage.RxId.ack:
                    __packet_index = context_to_packet_index_map[context]
                    self.packets.pop(__packet_index)
                self.rx_message_buffer.pop(context)
                context_to_packet_index_map.pop(context)
                self.progress_bar.set_val_signal.emit(100*float(num_of_packets-len(self.packets))/num_of_packets)

            if time.time() - t0 > reflash_timeout:
                self.text_browser.append("REFLASHING FAILED")
                return
        self.text_browser.append("REFLASHING FINISHED")
        self.text_browser.append("{}".format(time.time()-t0))
        message_sender.send(MessageSender.ID.run_main_app_btl)
        self.cancel_button.setText("CLOSE")





if __name__ == "__main__":
    import sys
    app = QtGui.QApplication(sys.argv)
    myapp = Reflasher('app_status.sts')
    myapp.show()
    app.exec_()
    # myapp.safe_close()
    sys.exit()
    sys.stdout = STDOUT