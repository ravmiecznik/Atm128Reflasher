"""
author: Rafal Miecznik
contact: ravmiecznk@gmail.com

This module handles both message sending and message reception.

RxMessage structure:
 MESSAGE_BODY_BYTES<MSG_TAIL>crc_tail
   ?bytes           10 bytes 2bytes
Because of Atmega128 limited ram memory there is a message body sent first and it's tail in the end.
Tail acts like a header but attached in msg tail with all information: ID, CONTEXT, LEN, CRC. All those fields
are calculated when each msg byte is transmitted. Using those fileds allows to verify msg integrity and with
given msg len it is possible to extract it from rx buffer


"""

import struct
import time
import sys

from datetime import datetime
from crc import crc
from random import randrange
from loggers import create_logger
from PyQt4.QtCore import QMutex

from auxiliary_module import Uint16, MeanCalculator
from config import LOG_PATH


#log_format = '[%(pathname)s:%(lineno)s %(asctime)s]: %(levelname)s method:"%(funcName)s" %(message)s'
log_format = '[%(asctime)s]: %(levelname)s method:"%(funcName)s" %(message)s'
logger_name = "message_handler"
m_logger = create_logger(logger_name, log_path=LOG_PATH, format=log_format)


MAX_PACKET_SIZE = 256*8 + 20


class MsgLockTimeout(Exception):
    pass

class RxTimeout(Exception):
    pass

class TxTimeout(Exception):
    pass


class TransmissionStats:
    """
    Keeps track of ack/nack ratio
    """
    def __init__(self):
        self.__acks = 0
        self.__nacks = 0

    def ack(self):
        self.__acks += 1

    def nack(self):
        self.__nacks += 1

    def __repr__(self):
        try:
            err_rate = float(self.__nacks)/self.__acks
        except ZeroDivisionError:
            err_rate = 0
        return "acks: {}, nack: {}, err_rate: {}".format(self.__acks, self.__nacks, err_rate)


class MessageSender:
    """
    static fileds:
        context: to keep track of msg req<->resp mechanism msg context is attached.
                 Thanks to this value it is possible to find right response for given request.
                 There are context ids reserved for particular messages handling:
                 0: free text which should be displayed in console window
                 1: digidiag frame data
                 Message sender cant assign reserved_context id when message is created and sent.
    """

    reserved_context = (
        0,
        1,
    )
    context = Uint16(len(reserved_context)) #start with value greater than reserved_context
    lock = False

    class ID:
        """
        Message IDs reperesenting given procedure in EMU BT board
        """
        txt_message     = 0
        write_to_page   = 1
        rxflush         = 2
        setbankname     = 3
        get_sram_packet = 4
        get_bank_packet = 5
        enable_sram     = 6
        reload_sram     = 7
        send_sram_bytes = 8
        handshake       = 9
        get_write_stats = 10
        bootloader      = 11
        disable_btlrd   = 12
        dummy           = 13
        reset           = 14
        bank1_set       = 15
        bank2_set       = 16
        bank3_set       = 17
        get_bank_in_use = 18
        set_bank_name   = 19
        dgf_code_check  = 20
        set_pin         = 21
        digidag_enable  = 22
        digidag_disable = 23
        wipe_banks      = 24
        bootloader_old  = 25
        get_banks_info  = 26
        reset_banks_info = 27
        update_bank_data = 28
        run_main_app_btl= 254

        @classmethod
        def translate_id(cls, m_id):
            try:
                return [p[0] for p in MessageSender.ID.__dict__.items() if p[1] == m_id][0]
            except IndexError:
                return None

    def __init__(self, tx_interface):
        self.mutex = QMutex()
        self.__transmit = tx_interface
        #self.__rx_buffer = rx_buffer

    def __send_m(self, msg, m_id):
        """
        Send createad message.
         Avoid using recovered context_ids
        """
        context = MessageSender.context
        MessageSender.context += 1
        while MessageSender.context in MessageSender.reserved_context:
            MessageSender.context += 1
        translated_m_id = MessageSender.ID.translate_id(m_id)
        m_logger.debug("Sent message with context: {}, id: {}({})".format(context, translated_m_id, m_id))
        m_logger.debug(msg[11:30])
        self.__transmit(msg)
        return context

    def peek_context(self):
        return MessageSender.context + 1

    def send(self, m_id, body='NULL'):
        """
        Polymorphic method for send
        """
        return self.__send(m_id, body)

    def send_raw_msg(self, body):
        """
        Polymorphic method for send
        """
        return self.__send(m_id=None, body=body)

    def __send(self, m_id=None, body='NULL'):
        msg = create_message(msg_id=m_id, body=body, context=MessageSender.context) if m_id is not None else body
        self.mutex.lock()
        context = self.__send_m(msg, m_id)
        self.mutex.unlock()
        m_logger.debug("message sending unlocked")
        return context


class RxId(tuple):
    """
    This is auxiliary object which holds rx id value for RxMessage.
    It returns id of ack, nack or dtx but in case of any error
    it return dtx id.
    """
    def __getitem__(self, item):
        try:
            try:
                return tuple.__getitem__(self, item)
            except IndexError as e:
                m_logger.error("{}: {}".format(e, item))
        except TypeError:
            print "Type error"
            return 'dtx'


class RxMessage(object):
    """
    Rx message ids (types)
    enum id{
        ack_feedback,
        nak_feedback,
    };
    """
    rx_id_tuple = ('ack', 'nack', 'dtx', 'txt', 'dbg', 'dgframe', 'pin_change_pending', 'banks_info')
    rx_id = RxId(rx_id_tuple)

    class RxId():
        ack                 = 0
        nack                = 1
        dtx                 = 2
        txt                 = 3
        dbg                 = 4
        dgframe             = 5
        pin_change_pending  = 6
        banks_info          = 7

    def __init__(self, msg_id, context, crc_check, body, length):
        self.__id = msg_id
        self.__context = context
        self.__crc_result = self.__set_result(crc_check)        #crc calculated from msg raceived vs tail crc
        self.__body = self.__set_body(body)
        if sys.platform in ('linux', 'linux2'):
            self.__tstamp = datetime.now().strftime("%H:%M:%S.%s")
        elif sys.platform == 'win32':
            self.__tstamp = datetime.now().strftime("%H:%M:%S.%ms")
        self.__len = length

    def __set_body(self, body):
        try:
            len(body)
            return body
        except TypeError:
            raise Exception("body is not iterable")

    def __set_result(self, result):
        valid_results = [RxMessage.RxId.ack, RxMessage.RxId.nack, RxMessage.RxId.dtx]
        if result not in valid_results:
            raise Exception("Result must be ACK {} | NACK {} | DTX {}".format(*valid_results))
        return result

    @property
    def tstamp(self):
        return self.__tstamp

    @property
    def id(self):
        return self.__id

    @property
    def ids(self):
        """
        id str
        :return:
        """
        return RxMessage.rx_id[self.id]

    @property
    def context(self):
        return self.__context

    @property
    def crc_check(self):
        return RxMessage.rx_id_tuple[self.__crc_result]

    @property
    def msg(self):
        return self.__body

    @property
    def len(self):
        return self.__len

    def __repr__(self):
        return "i{}\n" \
               "id:         {m_id}\n" \
               "context:    {context}\n" \
               "crcresult:  {result}\n" \
               "length:     {lenght}\n" \
               "body:      '{body}'\n" \
               "tstamp:     {tstamp}".format(RxMessage,
                                             m_id=RxMessage.rx_id[self.__id],
                                             context=self.__context,
                                             result=['ack', 'nack', 'dtx'][self.__crc_result],
                                             lenght=self.__len,
                                             body=' '.join(self.__body[0:20].split()) + '...',
                                             tstamp=self.__tstamp)


MSG_RX_DBG_TEMPLATE = "\n--------------------\n"\
                      "Message received:\n" \
                      "{}\n" \
                      "--------------------"


class MessageReceiver:
    """"
    Checks given rx buffer if message is present there.
        struct  Tail
        {
            uint8_t     tail_start = TAIL_START_MARK; // '<'
            uint16_t    id = 0;
            uint16_t    context = 0;
            uint16_t    msg_len = 0;
            uint16_t    body_crc= 0;
            uint8_t     tail_end = TAIL_END_MARK; // '>'
        }
        uint16_t    tail_crc= 0;
    """
    TAIL_LEN = 10
    TAIL_START_MARK = '<'
    TAIL_END_MARK = '>'
    TAIL_CRC_SHIFT_POS = 3
    ts = time.time()
    LOCKED = False

    def __init__(self, rx_buffer):
        self.rx_buffer = rx_buffer
        self.__mean_rx_time = MeanCalculator()
        self.mutex = QMutex()
        self.t0 = time.time()

    def check_tail(self, peek_buff):
        init_find = peek_buff.find(MessageReceiver.TAIL_START_MARK)
        peek_buff_len = len(peek_buff)
        for i in xrange(peek_buff_len - MessageReceiver.TAIL_LEN + init_find):
            latest_find = i + init_find
            try:
                tail_start_mark_pos = peek_buff[latest_find:].find(MessageReceiver.TAIL_START_MARK)
                tail_end_mark_pos = tail_start_mark_pos + MessageReceiver.TAIL_LEN - 1
                tail_end_mark = peek_buff[latest_find:][tail_end_mark_pos]
            except IndexError:
                return False
            try:
                if tail_end_mark == MessageReceiver.TAIL_END_MARK:
                    peek_buff = peek_buff[latest_find:]
                    tail = peek_buff[tail_start_mark_pos: tail_end_mark_pos]
                    _full_tail = peek_buff[tail_start_mark_pos: tail_end_mark_pos+1]
                    _id = struct.unpack('H', tail[1:3])[0]
                    _context = struct.unpack('H', tail[3:5])[0]
                    _msg_len = struct.unpack('H', tail[5:7])[0]
                    _body_crc = tail[7:9]

                    _tail_crc = peek_buff[tail_end_mark_pos+1: tail_end_mark_pos + MessageReceiver.TAIL_CRC_SHIFT_POS]
                    tail_integrity = _tail_crc == crc(_full_tail)    # tail integrity check
                    if _id < len(RxMessage.rx_id_tuple) and _msg_len < MAX_PACKET_SIZE and _context < 0xffff \
                            and self.rx_buffer.available() > _msg_len and tail_integrity:
                        return _id, _context, _msg_len, _body_crc, tail_start_mark_pos + latest_find, tail_end_mark_pos + latest_find
            except struct.error:
                return False
        return False

    def get_message(self):
        t0 = time.time()

        ret_rxmsg = None
        if self.rx_buffer.available() >= MessageReceiver.TAIL_LEN:
            self.mutex.lock()
            peek_buff = self.rx_buffer.peek()
            check_tail_result = self.check_tail(peek_buff)
            self.mutex.unlock()
            if check_tail_result:
                _id, _context, _msg_len, _crc, tail_start_mark_pos, tail_end_mark_pos = check_tail_result
                self.mutex.lock()
                msg_body = self.rx_buffer.read(tail_end_mark_pos + 1 + 2)
                self.mutex.unlock()
                msg_body = msg_body[:tail_start_mark_pos]
                MessageReceiver.ts = time.time()
                crc_check = RxMessage.RxId.ack if _crc == crc(msg_body) else RxMessage.RxId.nack
                rxmsg = RxMessage(msg_id=_id, crc_check=crc_check, length=len(msg_body), context=_context, body=msg_body)
                m_logger.debug(MSG_RX_DBG_TEMPLATE.format(rxmsg))
                self.t0 = time.time()
                if _crc == crc(msg_body):
                    self.__mean_rx_time.count(time.time() - t0)
                    ret_rxmsg = rxmsg
                m_logger.debug("Mean msg extract time: {}".format(self.__mean_rx_time))
                m_logger.debug("Period: {}".format(time.time() - self.t0))

        return ret_rxmsg



def create_message(msg_id, body, context=0, max_packet_size=MAX_PACKET_SIZE, fail_crc_factor=None):
    """
    Create message with name, body_len, crc, id
    fail_crc_factor: propability factor to fail crc, value 4 means that 1 of 4 transmissions will fail crc, overwrites fail_crc
    :param msg_id: msg id
    :param context: msg context
    :param body:
    :param max_packet_size:
    :param fail_crc_factor: fail factor for testing purposes
    :return:
    """
    body_len = len(body)                            #integer type, 4 bytes long
    header_size = 10
    if body_len + header_size > max_packet_size:
        raise Exception("msg len to big: {}>{}".format(body_len + header_size, max_packet_size))
    body_len = struct.pack('I', body_len)
    msg_id = struct.pack('H', msg_id)                       #two bytes
    context = struct.pack('H', context)  # two bytes
    c = crc(body)                                   #two bytes field
    if fail_crc_factor:
        if randrange(0, fail_crc_factor) == 0:
            c1 = c[0]
            c2 = chr(ord(c[1]) + 1) if ord(c[1]) <= 0xff else chr(ord(c[1]) - 1)
            c = c1 + c2
    return '>{id}{context}{body_len}{crc}<{body}'.format(id=msg_id, context=context, body_len=body_len, crc=c, body=body)


if __name__ == "__main__":
    rm = RxMessage(1, 2, 3, 'rafal')
    print rm