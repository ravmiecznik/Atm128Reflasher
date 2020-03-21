"""
author: Rafal Miecznik
contact: ravmiecznk@gmail.com
"""

import os
import configparser
import time
import struct
import textwrap
from queue import Queue, Empty
import serial

from PyQt4 import QtGui
from PyQt4.QtGui import QFileDialog
from PyQt4.QtCore import pyqtSignal, QString

from intel_hex_handler import intel_hex_parser
from gui_thread import thread_this_method, GuiThread
from win_com_port_handler import get_com_devices, ListPortInfo

from gui.loggers import create_logger
from gui.message_handler import MessageSender, MessageReceiver, RxMessage
from serial_handler import SerialConnection
from circ_io_buffer import CircIoBuffer



stdout_log = create_logger("stdout")
dbg = stdout_log.debug
PACKET_SIZE = 256*8

class TextBrowserInSubWindow(QtGui.QTextBrowser):
    append_sig = pyqtSignal(object, object)
    def __init__(self):
        QtGui.QTextBrowser.__init__(self)
        self.append_sig.connect(QtGui.QTextBrowser.append)

    def append(self, string):
        self.append_sig.emit(self, string)


class DummyEmulator:
    pass

class WindowGeometry(object):
    def __init__(self, QtGuiobject):
        #self.parent = parent
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
        grid.addWidget(self.label, 0, 0)
        grid.addWidget(self.port_dev_combo_box, 0, 1, 1, 1)
        grid.addWidget(self.dev_type_combo_box, 0, 2, 1, 1)
        grid.addWidget(self.test_conn_button, 0, 3, 1, 1)
        grid.addWidget(self.descr_label, 1, 1, 2, 1)

        self.setLayout(grid)

    def index_changed(self, index):
        def wrap(txt):
            return ('\n' + ' '*len('description: ')).join(textwrap.wrap(txt, 30))
        device_info = self.devices[index]
        self.port_dev_combo_box.setToolTip(self.encoder(str(device_info)))
        descr = "manufacturer: {}\n" \
                "description: {}".format(
            wrap(device_info.manufacturer),
            wrap(device_info.description)
        )
        self.descr_label.setText(self.encoder(descr))
        # print self.get_current_serial_device()
        # print device_info.device
        # print device_info.name
        # print device_info.description
        # print device_info.hwid
        #
        # print device_info.vid
        # print device_info.pid
        # print device_info.serial_number
        # print device_info.location
        # print device_info.manufacturer
        # print device_info.product
        # print device_info.interface

    def get_connection_type(self):
        return self.dev_type_combo_box.currentText()

    def get_current_serial_device(self):
        device = filter(lambda i: i.device==self.port_dev_combo_box.currentText(), self.devices)[0]
        return device.device


class Reflasher(QtGui.QWidget):
    #TODO: create serial connection class for communicaton, use emulator from emu_bt_r as reference
    #TODO: the class must be more gneric, should handle bluetooth and FTDI as well
    #TODO: use some abstract classes for that ?
    def __init__(self, app_status_file,):
        QtGui.QWidget.__init__(self)
        self.setWindowTitle("REFLASH")
        self.x_siz, self.y_siz = 600, 400
        self.reflash()
        self.data_ready_slot()

        self.connection = None
        self.rx_buffer = CircIoBuffer(size=258*10)
        self.rx_message_buffer = dict() #this buffer wont't exceed number of maximum possible context ids in msg.id (0xffff)
        self.packets = {}

        self.message_receiver = MessageReceiver(self.rx_buffer)

        self.app_status_file = app_status_file
        self.last_hex_path = self.get_last_hex_file_path()
        self.flash_succeeded = False

        self.serial_connection = None
        self.set_event_handler()
        #self.message_sender = MessageSender(self.serial_connection.send, self.rx_buffer)
        #self.message_receiver = MessageReceiver(self.rx_buffer)

        #TEXT DISPLAY
        self.line_edit = QtGui.QLineEdit()
        self.text_browser = TextBrowserInSubWindow()
        self.progress_bar = ColorProgressBar(parent=self)
        font = QtGui.QFont('Courier New', 8)
        self.text_browser.setFont(font)
        self.text_browser.setFontPointSize(9)
        line_edit_text = self.last_hex_path if self.last_hex_path else "SELECT PROPER HEX FILE"
        self.line_edit.setText(line_edit_text)


        #WELCOME TEXT
        self.text_browser.append("WELCOME IN ATMEGA128 REFLASH TOOL\n")
        self.text_browser.append("Supported bootloader: atm128_bootloader_v3")
        self.text_browser.append("")
        self.text_browser.append("SELECT CORRECT SERIAL DEVICE AND DEVICE TYPE: COM OR BLUETOOTH")
        self.text_browser.append("SELECT HEX FILE")

        #self.text_browser.anchorClicked.connect(self.anchor_clicked)

        #COM DEVICES LIST
        self.com_devices = ComDevicesComboBox()
        self.com_devices.test_conn_button.clicked.connect(self.test_connection_slot)

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

        #GRID
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

        #threads
        self.test_connection()

    @thread_this_method()
    def test_connection(self):
        """
        This thread checks if selected connection is compatible with bootloader3
        :return:
        """
        tmp_connection = self.establish_connection()
        tmp_connection.close()


    @thread_this_method()
    def data_ready_slot(self):
        if self.connection:
            try:
                while self.connection.queue.qsize() > 0:
                    self.rx_buffer.write(self.connection.queue.get(timeout=1, block=True))
                else:
                    msg = self.message_receiver.get_message()
                    if msg is not None:
                        if msg.id == RxMessage.RxId.ack:
                            self.rx_message_buffer[msg.context] = msg
                        else:
                            print
                            print msg.id, RxMessage.RxId.ack
                            print msg
                        dbg(["ctx: {}, crc: {}, id: {}".format(m.context, m.crc_check, m.ids) for m in self.rx_message_buffer.values()])
                        dbg(["{}".format(m.context) for m in self.rx_message_buffer.values()])
                    else:
                        dbg('None')
            except Empty:
                pass

    def test_connection_slot(self):
        self.test_connection.start()

    def anchor_clicked(self, *args, **kwargs):
        print args, kwargs
        self.text_browser.setOpenExternalLinks(False)

    def _find_version_of_hex_to_reflash(self, bin_file):
        version_location_pos = bin_file.find("Version:R")
        version_location_pos_end = bin_file.find("\n", version_location_pos)
        if version_location_pos > 1:
            new_version = bin_file[version_location_pos:version_location_pos_end-1]
            return new_version

    # def get_raw_rx_buffer_slot(self):
    #     """
    #     This slot is triggered by data reception object whenever new data is present in rx buffer
    #     :return:
    #     """
    #     msg = self.message_receiver.get_message()
    #     if msg:
    #         self.rx_message_buffer[msg.context] = msg
    #         if msg.id == RxMessage.RxId.txt:
    #             self.text_browser.append("E: {}".format(msg.msg))
    #             if self.__expected_version and self.__expected_version in msg.msg:
    #                 self.text_browser.append("\nReflashing done\nYou can close Reflasher window")
    #                 self.cancel_button.setText("CLOSE")

    def set_event_handler(self):
        #self.old_eventhandler = self.serial_connection.event_handler
        #self.reflasher_event_handler = EventHandler()
        #self.reflasher_event_handler.add_event(self.get_raw_rx_buffer_slot)
        #self.serial_connection.set_event_handler(self.reflasher_event_handler)
        pass

    def restore_old_event_handler(self):
        self.serial_connection.set_event_handler(self.old_eventhandler)

    def get_last_hex_file_path(self):
        config = configparser.ConfigParser()
        config.read(self.app_status_file)

        try:
            path = config['FLASH_HEX_FILE']['path']
            return path
        except KeyError:
            return ''

    def closeEvent(self, event):
        self.restore_old_event_handler()
        QtGui.QWidget.close(self)
        event.accept()


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
                self.__expected_version = self._find_version_of_hex_to_reflash(bin_segments[start_address])
                self.text_browser.append("Version of new software: {}".format(self.__expected_version))
                self.bin_segments_to_packets(bin_segments[start_address])
                self.reflash.start()
        except IOError:
            self.text_browser.append("File not present or faulty:\n{}".format(file_path))


    def bin_segments_to_packets(self, bin_segments):
        self.packets = {}
        cnt = 0
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
            connection = Connection(port=self.com_devices.get_current_serial_device(), timeout=0.2, write_timeout=1,
                                        baudrate=115200, data_ready_signal=self.data_ready_slot.start)
        except serial.serialutil.SerialException:
            self.text_browser.append("Can't connect to: {}".format(self.com_devices.get_current_serial_device()))
            return

        raw_data = ''

        if connection.is_open:
            self.text_browser.append("{}: Connected".format(connection.name))

            try:
                MessageSender(connection.write).send(MessageSender.ID.bootloader)
            except serial.serialutil.SerialTimeoutException:
                self.text_browser.append("Connection write test failed")
                connection.close()
                return

            try:
                raw_data += connection.queue.get(timeout=1, block=True)
            except Empty:
                self.text_browser.append("Cant't receive data")
                connection.close()
                return

            # receive data
            while connection.queue.qsize() > 0:
                try:
                    raw_data += connection.queue.get(timeout=1, block=True)
                except Empty:
                    break

            try:
                cbuffer = CircIoBuffer(size=1024, initial_buffer=raw_data)
                resp = MessageReceiver(cbuffer).get_message().msg
                if resp == 'bootloader3':
                    self.text_browser.append("Connectiont test OK, reply: {}".format(resp))
            except AttributeError:
                self.text_browser.append("Connectiont test Failed, incorrect response")
        return connection

    @thread_this_method()
    def reflash(self):
        timeout = 30
        rxtimeout = 2
        self.progress_bar.set_val_signal.emit(0)
        self.connection = self.establish_connection()
        message_sender = MessageSender(self.connection.send)
        message_sender.send(MessageSender.ID.rxflush)
        num_of_packets = len(self.packets)
        t0 = time.time()
        context_to_packet_index_map = {}
        while self.packets:
            packet_index = self.packets.keys()[0]
            #context = message_sender.peek_context()
            context = message_sender.send(MessageSender.ID.write_to_page,
                                body=struct.pack('H', packet_index) + self.packets[packet_index])
            context_to_packet_index_map[context] = packet_index
            _t0 = time.time()
            # GuiThread(process=message_sender.send, args=(MessageSender.ID.write_to_page,),
            #           kwargs=dict(body=struct.pack('H', packet_index) + self.packets[packet_index])).start()
            # message_sender.send(MessageSender.ID.write_to_page,
            #                     body=struct.pack('H', packet_index) + self.packets[packet_index])
            while context not in self.rx_message_buffer:
                dbg("wait for {}".format(context))
                time.sleep(1)
                if time.time() - _t0 > rxtimeout:
                    dbg('timeout')
                    break
            else:
                if self.rx_message_buffer[context].id == RxMessage.RxId.ack:
                    __packet_index = context_to_packet_index_map[context]
                    self.packets.pop(__packet_index)
                    dbg('got ok')
                else:
                    self.text_browser.append("nack")
                self.rx_message_buffer.pop(context)
                self.progress_bar.set_val_signal.emit(100*float(num_of_packets-len(self.packets))/num_of_packets)
            if time.time() - t0 > timeout:
                self.text_browser.append("REFLASHING FAILED")
                self.connection.close()
                return
        self.text_browser.append("REFLASHING FINISHED")
        self.text_browser.append("VERYFYING")
        self.text_browser.append("{}".format(time.time()-t0))
        message_sender.send(MessageSender.ID.run_main_app_btl)
        self.connection.close()





if __name__ == "__main__":
    import sys
    dummy_emulator = DummyEmulator()
    app = QtGui.QApplication(sys.argv)
    myapp = Reflasher('app_status.sts')
    myapp.show()
    app.exec_()
    # myapp.safe_close()
    sys.exit()
    sys.stdout = STDOUT