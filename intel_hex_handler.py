"""
author: Rafal Miecznik
contact: ravmiecznk@gmail.com
"""

import platform
platform = platform.system()


def intel_hex_parser(hex_string_lines, info=lambda x:x):
    """
    :param hex_string_lines: list of text lines of intel hex format
    :return: segmented binary file as dict, each segment key corresponds to target address
     INTEL HEX:
     :10010000214601360121470136007EFE09D2190140
        :               10              0100                    00             214601360121470136007EFE09D21901      40
     [:-1 char][num_of_bytes- 2 chars][address- 4 chars][record type- 2 chars][     data- num_of_bytes/2       ] [crc- 2 chars]
     record types:
     00 - record contains data and 16bit address
     01 - file end, last record
     02 - address extension record like :020000021000EC -> :02 - contains 2 bytes of information, 0x0000 - address,
            0x1000 - must be multiplied by 0x10, 0xEC - crc. From now on value 0x1000*0x10 will be added to address
            provieded in record type 00 (addressing up to 1MB address space)
     03 - sets reset vector, in other words it inctructs ucontroller to set application start address, e. g. if you
            want to set bootloader reset vector, you need to handle such command in you programmer

    """
    info("Parsing hex file")
    split_by_n = lambda s, n: [s[e:e + n] for e in range(0, len(s), n)]
    hexstr_to_int_list = lambda l: [int(e, 16) for e in l]
    int_to_chr_list = lambda l: [chr(e) for e in l]

    current_bin_segment = 0
    binary_segments = {current_bin_segment: bytes()}
    address_extension = 0

    addr_index = 2
    addr_index_end = 6

    num_of_data_index = 0
    num_of_data_index_end = 2

    record_type_index = 6
    record_type_index_end = 8
    data_index = 8
    line_num = 0
    for hex_line in hex_string_lines:
        # if platform != 'Linux':
        #     hex_line = hex_line + '\n'
        hex_line = hex_line[1:-3]   # no crc, no first colon
        num_of_data = int(hex_line[num_of_data_index:num_of_data_index_end], 16)
        record_type = hex_line[record_type_index:record_type_index_end]
        address_raw = hex_line[addr_index:addr_index_end]
        if record_type == '02':
            address_extension = hex_line[data_index:data_index+num_of_data*2]
            address_extension = int(address_extension, 16) * 0x10
            first_address_in_new_segment = hex_string_lines[line_num+1][1:][addr_index:addr_index_end]
            first_address_in_new_segment = int(first_address_in_new_segment, 16) + address_extension
            binary_segments[first_address_in_new_segment] = bytes()
            current_bin_segment = first_address_in_new_segment
        if record_type == '01':
            info("reach hex file end")
        if record_type == '00':
            address = address_extension + int(address_raw, 16)
            hex_data = hex_line[data_index:]
            calc_num_of_data = int(len(hex_data)/2)
            if num_of_data != calc_num_of_data:
                info(hex_line)
                exception = "Data length mismatch at line: {}. Calculated: {}, from file {}".format(line_num, calc_num_of_data, num_of_data)
                info(exception)
                raise Exception(exception)
            hex_str_list = split_by_n(hex_data, 2)
            hexstr_list_as_int = hexstr_to_int_list(hex_str_list)
            #raw_bin_line = ''.join(int_to_chr_list(hexstr_list_as_int))
            raw_bin_line = bytes(hexstr_list_as_int)
            binary_segments[current_bin_segment] += raw_bin_line
        line_num += 1
    info("parsing done")
    return binary_segments

