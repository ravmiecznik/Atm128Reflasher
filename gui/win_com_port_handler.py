"""
author: Rafal Miecznik
contact: ravmiecznk@gmail.com
creation date: 2020-03-18
"""

import string

import serial
import serial.tools.list_ports
from serial.tools.list_ports_common import ListPortInfo

encoders = {
    'ascii': lambda s: s.encode('ascii'),
    'utf-8': lambda s: s.encode('utf-8'),
    'ascii-r': lambda s: s.encode('ascii', errors='replace'),
}


class ListPortInfoEncodingFix(ListPortInfo):
    """
    Original class has issue with unicode.
    This class checks available encoders and sets the best one for __str__method
    """
    encoding_scheme = 'utf-8'

    def __init__(self, *args, **kwargs):
        ListPortInfo.__init__(self, *args, **kwargs)
        self.__encode = lambda s: s.encode('utf-8')


    @property
    def device(self):
        return self.__encode(self.__device)

    @device.setter
    def device(self, value):
        self.__device = value

    @property
    def manufacturer(self):
        return self.__encode(self.__manufacturer)

    @manufacturer.setter
    def manufacturer(self, value):
        self.__manufacturer = value

    @property
    def description(self):
        return self.__encode(self.__description)

    @description.setter
    def description(self, value):
        self.__description = value

    def __str__(self):
        s = 'device: {}\nmanufacturer: {}\ninterface: {}'.format(self.device, self.manufacturer, self.interface)
        return s

serial.tools.list_ports_common.ListPortInfo = ListPortInfoEncodingFix

def get_com_devices():
    """
    :return: List of ListPortInfo
    """
    return serial.tools.list_ports.comports()




