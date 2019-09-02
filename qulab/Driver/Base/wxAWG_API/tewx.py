#Tabor-Electronics WX-Instrument Controller (Without VISA-NI)

# Please refer to 
# Tabor Electronics website's tutorials ->> Remote control ->> Python ->> How To Manage Tabor AWG's Memory.
# Where you will find detailed information of how to use all binary data transfer SCPI commands.


#import sys
import socket
import struct
import copy
import numpy as np
import warnings

try:
    import usbtmc
    _usbtmc_supported = True
except:
    _usbtmc_supported = False


# WX2184 Properties
_wx2184_properties = {
    'model_name'      : 'WX2184', # the model name
    'num_parts'       : 2,        # number of instrument parts
    'chan_per_part'   : 2,        # number of channels per part
    'seg_quantum'     : 16,       # segment-length quantum
    'min_seg_len'     : 192,      # minimal segment length
    'max_arb_mem'     : 32E6,     # maximal arbitrary-memory (points per channel)
    'min_dac_val'     : 0,        # minimal DAC value
    'max_dac_val'     : 2**14-1,  # maximal DAC value
    'max_num_segs'    : 32E+3,    # maximal number of segments
    'max_seq_len'     : 48*1024-2,# maximal sequencer-table length (# rows)
    'min_seq_len'     : 3,        # minimal sequencer-table length (# rows)
    'max_num_seq'     : 1000,     # maximal number of sequencer-table
    'max_aseq_len'    : 48*1024-2,# maximal advanced-sequencer table length
    'min_aseq_len'    : 2,        # minimal advanced-sequencer table length
    'min_sclk'        : 75e6,     # minimal sampling-rate (samples/seconds)
    'max_sclk'        : 2300e6,   # maximal sampling-rate (samples/seconds)
    'digital_support' : False,    # is digital-wave supported?
    }

# WX1284 Definitions
_wx1284_properties = {
    'model_name'      : 'WX1284', # the model name
    'num_parts'       : 2,        # number of instrument parts
    'chan_per_part'   : 2,        # number of channels per part
    'seg_quantum'     : 16,       # segment-length quantum
    'min_seg_len'     : 192,      # minimal segment length
    'max_arb_mem'     : 32E6,     # maximal arbitrary-memory (points per channel)
    'min_dac_val'     : 0,        # minimal DAC value
    'max_dac_val'     : 2**14-1,  # maximal DAC value
    'max_num_segs'    : 32E+3,    # maximal number of segments
    'max_seq_len'     : 48*1024-2,# maximal sequencer-table length (# rows)
    'min_seq_len'     : 3,        # minimal sequencer-table length (# rows)
    'max_num_seq'     : 1000,     # maximal number of sequencer-table
    'max_aseq_len'    : 48*1024-2,# maximal advanced-sequencer table length
    'min_aseq_len'    : 2,        # minimal advanced-sequencer table length
    'min_sclk'        : 75e6,     # minimal sampling-rate (samples/seconds)
    'max_sclk'        : 1250e6,   # maximal sampling-rate (samples/seconds)
    'digital_support' : False,    # is digital-wave supported?
    }

# WX2182C Definitions
_wx2182C_properties = {
    'model_name'      : 'WX2182C',# the model name
    'num_parts'       : 2,        # number of instrument parts
    'chan_per_part'   : 1,        # number of channels per part
    'seg_quantum'     : 16,       # segment-length quantum
    'min_seg_len'     : 192,      # minimal segment length
    'max_arb_mem'     : 32E6,     # maximal arbitrary-memory (points per channel)
    'min_dac_val'     : 0,        # minimal DAC value
    'max_dac_val'     : 2**14-1,  # maximal DAC value
    'max_num_segs'    : 32E+3,    # maximal number of segments
    'max_seq_len'     : 48*1024-2,# maximal sequencer-table length (# rows)
    'min_seq_len'     : 3,        # minimal sequencer-table length (# rows)
    'max_num_seq'     : 1000,     # maximal number of sequencer-table
    'max_aseq_len'    : 48*1024-2,# maximal advanced-sequencer table length
    'min_aseq_len'    : 2,        # minimal advanced-sequencer table length
    'min_sclk'        : 10e6,     # minimal sampling-rate (samples/seconds)
    'max_sclk'        : 2.3e9,    # maximal sampling-rate (samples/seconds)
    'digital_support' : False,    # is digital-wave supported?
    }

# WX1282C Definitions
_wx1282C_properties = {
    'model_name'      : 'WX1282C',# the model name
    'num_parts'       : 2,        # number of instrument parts
    'chan_per_part'   : 1,        # number of channels per part
    'seg_quantum'     : 16,       # segment-length quantum
    'min_seg_len'     : 192,      # minimal segment length
    'max_arb_mem'     : 32E6,     # maximal arbitrary-memory (points per channel)
    'min_dac_val'     : 0,        # minimal DAC value
    'max_dac_val'     : 2**14-1,  # maximal DAC value
    'max_num_segs'    : 32E+3,    # maximal number of segments
    'max_seq_len'     : 48*1024-2,# maximal sequencer-table length (# rows)
    'min_seq_len'     : 3,        # minimal sequencer-table length (# rows)
    'max_num_seq'     : 1000,     # maximal number of sequencer-table
    'max_aseq_len'    : 48*1024-2,# maximal advanced-sequencer table length
    'min_aseq_len'    : 2,        # minimal advanced-sequencer table length
    'min_sclk'        : 10e6,     # minimal sampling-rate (samples/seconds)
    'max_sclk'        : 1.25e9,   # maximal sampling-rate (samples/seconds)
    'digital_support' : False,    # is digital-wave supported?
    }


# dictionary of supported-models' properties
model_properties_dict = {
    'WX2184'  : _wx2184_properties,
    'WX2184C' : _wx2184_properties,
    'WX1284'  : _wx2184_properties,
    'WX1284C' : _wx2184_properties,
    'WX2182C' : _wx2182C_properties,
    'WX1282C' : _wx1282C_properties,
    }

def get_device_properties(idn_str, opt_str):
    '''Get the device-properties dictionary according to its *IDN? and *OPT?

    :param idn_str: the instrument's answer to '*IDN?' query.
    :param opt_str: the instrument's answer to '*OPT?' query.
    :returns: dictionary of the device properties.
    '''

    dev_props = None
    idn_parts = idn_str.split(',')
    if len(idn_parts) == 4 and idn_parts[1] in model_properties_dict:
        model_name = idn_parts[1]
        d = model_properties_dict[model_name]
        dev_props = copy.deepcopy(d)
        dev_props['model_name'] = model_name

        if model_name in ('WX2184', 'WX2184C', 'WX1284', 'WX1284C'):
            dev_props['max_arb_mem'] = int(opt_str[2:4]) * 1E6
        elif opt_str.startswith('1M', 1):
            dev_props['max_arb_mem'] = 1E6
        elif opt_str.startswith('2M', 1):
            dev_props['max_arb_mem'] = 2E6
        elif opt_str.startswith('8M', 1):
            dev_props['max_arb_mem'] = 8E6
        elif opt_str.startswith('16M', 1):
            dev_props['max_arb_mem'] = 16E6
        elif opt_str.startswith('32M', 1):
            dev_props['max_arb_mem'] = 32E6
        elif opt_str.startswith('64M', 1):
            dev_props['max_arb_mem'] = 64E6
        elif opt_str.startswith('512K', 1):
            dev_props['max_arb_mem'] = 512E3
        elif opt_str.startswith('116') or opt_str.startswith('216') or opt_str.startswith('416'):
            dev_props['max_arb_mem'] = 16E6
        elif opt_str.startswith('132') or opt_str.startswith('232') or opt_str.startswith('432'):
            dev_props['max_arb_mem'] = 32E6
        elif opt_str.startswith('164') or opt_str.startswith('264') or opt_str.startswith('464'):
            dev_props['max_arb_mem'] = 64E6

        if opt_str.endswith('D'):
            dev_props['digital_support'] = True

    return dev_props


def list_usb_devices():
    '''List devices available via USB interface

    :returns: list of the devices connection-string (NI-VISA format).
    '''
    resource_names = []

    try:
        if _usbtmc_supported:
            devs = usbtmc.list_devices()

            for dev in devs:
                idVendor, idProduct, iSerial = None, None, None

                try:
                    idVendor = dev.idVendor
                except:
                    idVendor = None

                try:
                    idProduct = dev.idProduct
                except:
                    idProduct = None

                try:
                    iSerial = dev.serial_number
                except:
                    iSerial = None

                if idVendor is None or idProduct is None:
                    continue

                if iSerial is None:
                    resource_name = 'USB::0x{0:02x}::0x{1:02x}::INSTR'.format(idVendor, idProduct)
                    resource_names.append(resource_name)
                else:
                    resource_name = 'USB::0x{0:02x}::0x{1:02x}::{2}::INSTR'.format(idVendor, idProduct, iSerial)
                    resource_names.append(resource_name)

    except:
        pass


    return resource_names

class CommIntfType:
    '''The supported communication interface types '''
    NIL = 0
    LAN = 1
    USB = 2

class TEWXAwg(object):
    '''Tabor-Electronics WX-Instrument Controller (Without VISA-NI)'''

    def __init__(self, instr_addr=None, tcp_timeout=5.0, paranoia_level=1):
        ''' Initialize this `TEWWAwg` instance.

        The given `instr_address` defines the instrument-address.
        It can be either
         - An empty string or None (meaning no address)
         - IP-Address in digits and dots format (e.g. '192.168.0.170')
         - TCPIP NI-VISA format: 'TCPIP::<IP-Address>::<PortNo>::SOCKET'
           (for example: 'TCPIP:192.168.0.170::5025::SOCKET')
         - USB NI-VISA short-format: 'USB::<VendorId>::<ProductId>::INSTR
           (for example: 'USB::0x168b::0x2184::INSTR')
         - USB NI-VISA long-format: 'USB::<VendorId>::<ProductId>::<SerialNo>::INSTR
           (for example: 'USB::0x168b::0x2184::0000214991::INSTR')
        If it is not None, then communication is opened.

        In order to findout the USB-Address, use `usbtmc.usbtmc.list_devices()`.
        If for example it returns: `[<DEVICE ID 168b:2184 on Bus 001 Address 002>]`
        then the USB-Address is: 'USB::0x168b::0x2184::INSTR'.

        In case of multiple devices, the serial-number can be added too.
        For example: 'USB::0x168b::0x2184::0000214991::INSTR'


        :param instr_addr: the instrument address
        :param tcp_timeout: TCP-Socket time-out (in seconds)
        :param paranoia_level: the `paranoia_level` (0,1 or 2)
        '''

        self._tcp_sock = None
        self._usb_sock = None
        self._intf_type = CommIntfType.NIL

        self._model_name = ''

        self._ip_addr = None
        self._usb_addr = None
        self._dev_props = None
        self._instr_addr = None
        self._tcp_port_nb = None
        self._tcp_timeout = float(tcp_timeout)
        self._paranoia_level = int(paranoia_level)

        self._set_instr_address(instr_addr)
        if self._instr_addr is not None:
            self.open()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


    def open(self, instr_addr=None, tcp_timeout=None):
        '''Open/Reopen Connection

        The given `instr_address` defines the instrument-address.
        It can be either
         - An empty string or None (meaning no address)
         - IP-Address in digits and dots format (e.g. '192.168.0.170')
         - TCPIP NI-VISA format: 'TCPIP::<IP-Address>::<PortNo>::SOCKET'
           (for example: 'TCPIP:192.168.0.170::5025::SOCKET')
         - USB NI-VISA short-format: 'USB::<VendorId>::<ProductId>::INSTR
           (for example: 'USB::0x168b::0x2184::INSTR')
         - USB NI-VISA long-format: 'USB::<VendorId>::<ProductId>::<SerialNo>::INSTR
           (for example: 'USB::0x168b::0x2184::0000214991::INSTR')

        In order to findout the USB-Address, use `usbtmc.usbtmc.list_devices()`.
        If for example it returns: `[<DEVICE ID 168b:2184 on Bus 001 Address 002>]`
        then the USB-Address is: 'USB::0x168b::0x2184::INSTR'.

        In case of multiple devices, the serial-number can be added too.
        For example: 'USB::0x168b::0x2184::0000214991::INSTR'

        Note: If either `instr_addr` is None or `tcp_timeout` is None,
        then the the previous value of the relevant argument is used.

        :param instr_addr: the instrument's address.
        :param tcp_timeout: TCP-Socket time-out (in seconds)
        '''
        self.close()
        self._dev_props = None

        if instr_addr is not None:
            self._set_instr_address(instr_addr)
        if tcp_timeout is not None:
            self._tcp_timeout = float(tcp_timeout)

        if self._ip_addr is not None:
            # Open TCP-IP Socket:
            self._tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
            self._tcp_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._tcp_sock.settimeout(self._tcp_timeout)
            self._tcp_sock.connect((self._ip_addr, self._tcp_port_nb))
            self._intf_type = CommIntfType.LAN
        elif self._usb_addr is not None:
            self._usb_sock = usbtmc.Instrument(self._usb_addr)
            if self._usb_sock is None:
                warn_msg ='Failed to open USB-TMC Instrument at "{0}".'.format(self._usb_addr)
                warnings.warn(warn_msg)
            else:
                self._intf_type = CommIntfType.USB

        idn = self.send_query('*IDN?')
        opt = self.send_query('*OPT?')

        self._dev_props = get_device_properties(idn, opt)
        if self._dev_props is None and self._paranoia_level >= 2:
            warn_msg = 'unsupported model: {0}.'.format(idn)
            warnings.warn(warn_msg)

        self._model_name = self.get_dev_property('model_name', '')

    def close(self):
        '''Close Connection'''
        if self._tcp_sock is not None:
            self._tcp_sock.close();
            self._tcp_sock = None
        if self._usb_sock is not None:
            self._usb_sock.close()
            self._usb_sock = None
        self._intf_type = CommIntfType.NIL

    @property
    def intf_type(self):
        '''Get the communication-interface type '''
        return self._intf_type

    @property
    def tcp_sock(self):
        '''Get the tcp-ip socket '''
        return self._tcp_sock

    @property
    def usb_sock(self):
        '''Get the usb-tmc socket '''
        return self._usb_sock

    @property
    def instr_address(self):
        '''Get the instrument address '''
        return self._instr_addr

    @property
    def dev_properties(self):
        '''Get dictionary of the device properties '''
        return self._dev_props

    def get_dev_property(self, property_name, default_value=None):
        '''Get the value of the specified device-property

        :param property_name: the property name.
        :param default_value: default value (if the specified property is missing)
        :returns: the specified property, or the default-value if it's not defined.
        '''
        if self._dev_props is not None and property_name in self._dev_props:
            return self._dev_props[property_name]
        return default_value

    @property
    def model_name(self):
        '''Get the model name '''
        return self._model_name

    @property
    def paranoia_level(self):
        '''Get the (default) paranoia-level

        The paranoia-level indicates whether and which additional query
        should be sent after sending SCPI-Command to the instrument:
         - 0: do not send any additional query
         - 1: send '*OPC?' (recommended).
         - 2: send ':SYST:ERR?' and validate the response (for debug).
        '''
        return self._paranoia_level

    @paranoia_level.setter
    def paranoia_level(self, value):
        '''Set the (default) paranoia-level (0, 1 or 2)'''
        self._paranoia_level = int(value)

    def send_cmd(self, cmd_str, paranoia_level=None):
        '''Send the given command to the instrument

        The paranoia-level indicates whether and which additional query
        should be sent after sending the SCPI-Command to the instrument:
         - 0: do not send any additional query
         - 1: send '*OPC?' (recommended).
         - 2: send ':SYST:ERR?' and validate the response (for debug).
        If the given `paranoia_level` is `None`, then the default level is used.

        :param cmd_str: the command string (SCPI statement).
        :param paranoia_level: the paranoia-level (optional)
        '''
        assert (self._intf_type != CommIntfType.NIL)

        if paranoia_level is None:
            paranoia_level = self._paranoia_level

        if paranoia_level == 1:
            ask_str = cmd_str.rstrip()
            if len(ask_str) > 0:
                ask_str += '; *OPC?'
            else:
                ask_str += '*OPC?'
            _ = self.send_query(ask_str)
        elif paranoia_level >= 2:
            ask_str = cmd_str.rstrip()
            if len(ask_str) > 0:
                ask_str += '; :SYST:ERR?'
            else:
                ask_str += ':SYST:ERR?'
            syst_err = self.send_query( ask_str)
            if not syst_err.startswith('0'):
                wrn_msg = 'CMD: \"{0}\", ERR: \"{1}\"'.format(cmd_str.rstrip(), syst_err.rstrip())
                warnings.warn(wrn_msg)
                _ = self.send_query('*CLS; *OPC?')
        elif self._intf_type == CommIntfType.LAN:
            if not cmd_str.endswith('\n'):
                cmd_str = cmd_str + '\n'
            self._tcp_sock.sendall(cmd_str)
        elif self._intf_type == CommIntfType.USB:
            self._usb_sock.write(cmd_str)

    def send_query(self, query_str):
        '''Send the given query to the instrument and read the response

        :param query_str: the query string (SCPI statement).
        :returns: the instrument's response.
        '''
        resp = None
        assert (self._intf_type != CommIntfType.NIL)

        if self._intf_type == CommIntfType.LAN:
            if not query_str.endswith('\n'):
                query_str = query_str + '\n'
            self._tcp_sock.sendall(query_str)
            resp = self.read_resp()
        elif self._intf_type == CommIntfType.USB:
            resp = self._usb_sock.ask(query_str)

        return resp

    def read_resp(self):
        '''Read response from the instrument. '''

        resp = None
        assert (self._intf_type != CommIntfType.NIL)

        if self._intf_type == CommIntfType.LAN:
            ret = []
            ch = self._tcp_sock.recv(1)
            while '\n' != ch:
                if '\r' != ch:
                    ret.append(ch)
                ch = self._tcp_sock.recv(1)
            resp = ''.join(ret)
        elif self._intf_type == CommIntfType.USB:
            resp = self._usb_sock.read()

        return resp

    def send_binary_data(self, pref, bin_dat, paranoia_level=None):
        '''Send the given binary-data to the instrument.

        :param pref: binary-data header prefix (e.g. ':TRAC:DATA')
        :param bin_dat: the binary-data to send (a `numpy.ndarray`)
        :param paranoia_level: paranoia-level (that overrides the default one)
        '''
        assert(isinstance(bin_dat, np.ndarray))
        assert (self._intf_type != CommIntfType.NIL)

        if pref is None:
            pref = ''

        bin_dat_header = self._make_bin_dat_header(pref, bin_dat.nbytes)

        if paranoia_level is None:
            paranoia_level = self._paranoia_level

        if paranoia_level >= 1:
            bin_dat_header = '*OPC?; ' + bin_dat_header

        if self._intf_type == CommIntfType.LAN:
            self._tcp_sock.sendall(bin_dat_header)
        elif self._intf_type == CommIntfType.USB:
            self._usb_sock.write_raw(bin_dat_header)

        _ = self._send_raw_bin_dat(bin_dat)

        if paranoia_level >= 1:
            _ = self.read_resp() # read the response to the *OPC? that was sent with the header

        if paranoia_level >= 2:
            syst_err = self.send_query(':SYST:ERR?')
            if not syst_err.startswith('0'):
                syst_err = syst_err.rstrip()
                wrn_msg = 'ERR: "{0}" After Sending Binary-Data (pref="{1}" datLen={2}).'.format(syst_err, pref, len(bin_dat))
                warnings.warn(wrn_msg)
                _ = self.send_query('*CLS; *OPC?')

    def download_segment_lengths(self, seg_len_list, pref=':SEGM:DATA', paranoia_level=None):
        '''Download Segments-Lengths Table to Instrument

        :param seg_len_list: the list of segments-lengths.
        :param pref: the binary-data-header prefix.
        :param paranoia_level: paranoia-level (that overrides the default one)

        Example:
            The fastest way to download multiple segments to the instrument
            is to download the wave-data of all the segments, including the
            segment-prefixes (16 idle-points) of all segments except the 1st,
            into segment 1 (pseudo segment), and afterward download the
            appropriate segment-lengths. Using the SEGM:DATA command this will
            allow to slice the pseudo segment into the corresponding list of segments.

            >>> with TEWXAwg('192.168.0.170') as inst:
            >>>     # Select segment 1:
            >>>     inst.send_cmd(':TRACe:SELect 1')
            >>>
            >>>     # Download the wave-data of all segments:
            >>>     inst.send_binary_data(':TRACe:DATA', wave_data)
            >>>
            >>>     # Download the appropriate segment-lengths list:
            >>>     seg_lengths = [ 1024, 1024, 384, 4096, 8192 ]
            >>>     inst.download_segment_lengths(seg_lengths)
        '''
        if isinstance(seg_len_list, np.ndarray):
            if seg_len_list.ndim != 1:
                seg_len_list = seg_len_list.flatten()
            if seg_len_list.dtype != np.uint32:
                seg_len_list = np.asarray(seg_len_list, dtype=np.uint32)
        else:
            seg_len_list = np.asarray(seg_len_list, dtype=np.uint32)
            if seg_len_list.ndim != 1:
                seg_len_list = seg_len_list.flatten()

        self.send_binary_data(pref, seg_len_list, paranoia_level=paranoia_level)

    def download_sequencer_table(self, seq_table, pref=':SEQ:DATA', paranoia_level=None):
        '''Download Sequencer-Table to Instrument

        The sequencer-table, `seq_table`, is a list of 3-tuples
        of the form: (<repeats>, <segment no.>, <jump-flag>)

        :param seq_table: the sequencer-table (list of 3-tuples)
        :param pref: the binary-data-header prefix.
        :param paranoia_level: paranoia-level (that overrides the default one)

        Example:
            >>> # Create Sequencer-Table:
            >>> repeats = [ 1, 1, 100, 4, 1 ]
            >>> seg_nb = [ 2, 3, 5, 1, 4 ]
            >>> jump = [ 0, 0, 1, 0, 0 ]
            >>> sequencer_table = zip(repeats, seg_nb, jump)
            >>>
            >>> # Select sequencer no. 1, and write its table:
            >>> with TEWXAwg('192.168.0.170') as inst:
            >>>     inst.send_cmd(':SEQ:SELect 1')
            >>>     inst.download_sequencer_table(sequencer_table)
        '''

        tbl_len = len(seq_table)
        s = struct.Struct('< L H B x')
        s_size = s.size
        m = np.empty(s_size * tbl_len, dtype='uint8')
        for n in range(tbl_len):
            repeats, seg_nb, jump_flag = seq_table[n]
            s.pack_into(m, n * s_size, long(repeats), int(seg_nb), int(jump_flag))

        self.send_binary_data(pref, m, paranoia_level=paranoia_level)

    def download_adv_seq_table(self, seq_table, pref=':ASEQ:DATA', paranoia_level=None):
        '''Download Advanced-Sequencer-Table to Instrument

        The sequencer-table, `seq_table`, is a list of 3-tuples
        of the form: (<repeats>, <sequence no.>, <jump-flag>)

        :param seq_table: the sequencer-table (list of 3-tuples)
        :param pref: the binary-data-header prefix.
        :param paranoia_level: paranoia-level (that overrides the default one)

        Example:
            >>> # Create advanced-sequencer table:
            >>> repeats = [ 1, 1, 100, 4, 1 ]
            >>> seq_nb = [ 2, 3, 5, 1, 4 ]
            >>> jump = [ 0, 0, 1, 0, 0 ]
            >>> adv_sequencer_table = zip(repeats, seq_nb, jump)
            >>>
            >>> # Download it to instrument
            >>> with TEWXAwg('192.168.0.170') as inst:
            >>>     inst.download_adv_seq_table(adv_sequencer_table)
        '''

        tbl_len = len(seq_table)
        s = struct.Struct('< L H B x')
        s_size = s.size
        m = np.empty(s_size * tbl_len, dtype='uint8')
        for n in range(tbl_len):
            repeats, seg_nb, jump_flag = seq_table[n]
            s.pack_into(m, n * s_size, long(repeats), int(seg_nb), int(jump_flag))

        self.send_binary_data(pref, m, paranoia_level=paranoia_level)

    def download_fast_pattern_table(self, patt_table, pref=':PATT:COMP:FAST:DATA', paranoia_level=None):
        '''Download Fast (Piecewise-flat) Pulse-Pattern Table  to Instrument

        The pattern-table, `patt_table`, is a list of 2-tuples
        of the form: (<voltage-level (volt)>, <dwell-time (sec)>)

        :param patt_table: the pattern-table (list of 2-tuples)
        :param pref: the binary-data-header prefix.
        :param paranoia_level: paranoia-level (that overrides the default one)

        Note:
            In order to avoid Settings-Conflict make sure you can find
            a valid sampling-rate, `sclk`, such that the length in points
            of each dwell-time, `dwell-time*sclk` is integral number, and
            the total length in points is divisible by the segment-quantum
            (either 16 or 32 depending on the instrument model).
            Optionally set the point-time-resolution manually to `1/sclk`.

        Example:
            >>> inst = TEWXAwg('192.168.0.170')
            >>>
            >>> # Create fast-pulse pattern table:
            >>> volt_levels = [0.0 , 0.1 , 0.5 , 0.1 , -0.1, -0.5, -0.1, -0.05]
            >>> dwell_times = [1e-9, 1e-6, 1e-9, 1e-6, 1e-6, 1e-9, 1e-6, 5e-9 ]
            >>> pattern_table = zip(volt_levels, dwell_times)
            >>>
            >>> # Set Function-Mode=Pattern, Pattern-Mode=Composer, Pattern-Type=Fast:
            >>> inst.send_cmd(':FUNC:MODE PATT; :PATT:MODE COMP; :PATT:COMP:TRAN:TYPE FAST')
            >>>
            >>> # Optionally set User-Defined (rather than Auto) point sampling time:
            >>> inst.send_cmd(':PATT:COMP:RES:TYPE USER; :PATT:COMP:RES 0.5e-9')
            >>>
            >>> # Download the pattern-table to instrument:
            >>> inst.download_fast_pattern_table(pattern_table)
            >>>
            >>> inst.close()
        '''

        tbl_len = len(patt_table)
        s = struct.Struct('< f d')
        s_size = s.size
        m = np.empty(s_size * tbl_len, dtype='uint8')
        for n in range(tbl_len):
            volt_level, dwel_time = patt_table[n]
            volt_level = float(volt_level)
            dwel_time = float(dwel_time)
            s.pack_into(m, n * s_size, volt_level, dwel_time)

        self.send_binary_data(pref, m, paranoia_level=paranoia_level)

    def download_linear_pattern_table(self, patt_table, start_level, pref=':PATT:COMP:LIN:DATA', paranoia_level=None):
        '''Download Piecewise-Linear Pulse-Pattern to Instrument

        The pattern-table, `patt_table`, is a list of 2-tuples
        of the form: (<voltage-level (volt)>, <dwell-time (sec)>).

        Here the `vlotage-level` is the section's end-level.
        The section's start-lavel is the previous-section's end-level.
        The argument `start_level` is the first-section's start-level.

        :param patt_table: the pattern-table (list of 2-tuples)
        :param start_level: the (first-section's) start voltage level.
        :param pref: the binary-data-header prefix.

        Note:
            In order to avoid Settings-Conflict make sure you can find
            a valid sampling-rate, `sclk`, such that the length in points
            of each dwell-time, `dwell-time` * `sclk` is integral number, and
            the total length in points is divisible by the segment-quantum
            (either 16 or 32 depending on the instrument model).
            Optionally set the point-time-resolution manually to `1/sclk`.

        Example:
            >>> inst = TEWXAwg('192.168.0.170')
            >>>
            >>> # Create fast-pulse pattern table:
            >>> start_level = 0.0
            >>> volt_levels = [0.1 , 0.1 , 0.5 , 0.1 , -0.1, -0.1, -0.5, -0.1, 0.0  ]
            >>> dwel_times  = [1e-9, 1e-6, 1e-9, 1e-6, 4e-9, 1e-6, 1e-9, 1e-6, 1e-9 ]
            >>> pattern_table = zip(volt_levels, dwel_times)
            >>>
            >>> # Set Function-Mode=Pattern, Pattern-Mode=Composer, Pattern-Type=Linear:
            >>>inst.send_cmd(':FUNC:MODE PATT; :PATT:MODE COMP; :PATT:COMP:TRAN:TYPE LIN')
            >>>
            >>> # Optionally set User-Defined (rather than Auto) point sampling time:
            >>> inst.send_cmd(':PATT:COMP:RES:TYPE USER; :PATT:COMP:RES 0.5e-9')
            >>>
            >>> # Download the pattern-table to instrument:
            >>> inst.download_linear_pattern_table(pattern_table, start_level)
            >>>
            >>> inst.close()
        '''

        tbl_len = len(patt_table)
        s = struct.Struct('< f d')
        s_size = s.size
        m = np.empty(s_size * tbl_len, dtype='uint8')
        for n in range(tbl_len):
            volt_level, dwel_time = patt_table[n]
            volt_level = float(volt_level)
            dwel_time = float(dwel_time)
            s.pack_into(m, n * s_size, volt_level, dwel_time)

        if start_level is not None:
            start_level = float(start_level)
            self.send_cmd(':PATT:COMP:LIN:STARt {0:f}'.format(start_level))

        self.download_binary_data(pref, m, paranoia_level=paranoia_level)

    def build_sine_wave(self, cycle_len, num_cycles=1, phase_degree=0, low_level=0, high_level=2**14-1):
        '''Build Sine Wave

        :param cycle_len: cycle length (in points).
        :param num_cycles: number of cycles.
        :param phase_degree: starting-phase (in degrees)
        :param low_level: the sine low level.
        :param high_level: the sine high level.
        :returns: `numpy.array` with the wave data (DAC values)
        '''
        cycle_len = int(cycle_len)
        num_cycles = int(num_cycles)

        if cycle_len <= 0 or num_cycles <= 0:
            return None

        dac_min = self.get_dev_property('min_dac_val', 0)
        dac_max = self.get_dev_property('max_dac_val', 2**14-1)

        wav_len = cycle_len * num_cycles

        phase = float(phase_degree) * np.pi / 180.0
        x = np.linspace(start=phase, stop=phase+2*np.pi, num=cycle_len, endpoint=False)

        zero_val = (low_level + high_level) / 2.0
        amplitude = (high_level - low_level) / 2.0
        y = np.sin(x) * amplitude + zero_val
        y = np.round(y)
        y = np.clip(y, dac_min, dac_max)

        y = y.astype(np.uint16)

        wav = np.empty(wav_len, dtype=np.uint16)
        for n in range(num_cycles):
            wav[n * cycle_len : (n + 1) * cycle_len] = y

        return wav

    def build_triangle_wave(self, cycle_len, num_cycles=1, phase_degree=0, low_level=0, high_level=2**14-1):
        '''Build Triangle Wave

        :param cycle_len: cycle length (in points).
        :param num_cycles: number of cycles.
        :param phase_degree: starting-phase (in degrees)
        :param low_level: the triangle low level.
        :param high_level: the triangle high level.
        :returns: `numpy.array` with the wave data (DAC values)
        '''
        cycle_len = int(cycle_len)
        num_cycles = int(num_cycles)

        if cycle_len <= 0 or num_cycles <= 0:
            return None

        dac_min = self.get_dev_property('min_dac_val', 0)
        dac_max = self.get_dev_property('max_dac_val', 2**14-1)

        wav_len = cycle_len * num_cycles

        phase = float(phase_degree) * np.pi / 180.0
        x = np.linspace(start=phase, stop=phase+2*np.pi, num=cycle_len, endpoint=False)

        zero_val = (low_level + high_level) / 2.0
        amplitude = (high_level - low_level) / 2.0
        y = np.sin(x)
        y = np.arcsin(y) * 2 * amplitude / np.pi + zero_val
        y = np.round(y)
        y = np.clip(y, dac_min, dac_max)

        y = y.astype(np.uint16)

        wav = np.empty(wav_len, dtype=np.uint16)
        for n in range(num_cycles):
            wav[n * cycle_len : (n + 1) * cycle_len] = y

        return wav

    def build_square_wave(self, cycle_len, num_cycles=1, duty_cycle=50.0, phase_degree=0, low_level=0, high_level=2**14-1):
        '''Build Square Wave

        :param cycle_len: cycle length (in points).
        :param num_cycles: number of cycles.
        :param duty_cycle: duty-cycle (between 0% and 100%)
        :param phase_degree: starting-phase (in degrees)
        :param low_level: the triangle low level.
        :param high_level: the triangle high level.
        :returns: `numpy.array` with the wave data (DAC values)
        '''
        cycle_len = int(cycle_len)
        num_cycles = int(num_cycles)

        if cycle_len <= 0 or num_cycles <= 0:
            return None

        dac_min = self.get_dev_property('min_dac_val', 0)
        dac_max = self.get_dev_property('max_dac_val', 2**14-1)

        wav_len = cycle_len * num_cycles

        duty_cycle = np.clip(duty_cycle, 0.0, 100.0)
        low_level = np.clip(low_level, dac_min, dac_max)
        high_level = np.clip(high_level, dac_min, dac_max)

        phase = float(phase_degree) * np.pi / 180.0
        x = np.linspace(start=phase, stop=phase+2*np.pi, num=cycle_len, endpoint=False)
        x = x <= 2 * np.pi * duty_cycle / 100.0
        y = np.full(x.shape, low_level)
        y[x] = high_level

        y = y.astype(np.uint16)

        wav = np.empty(wav_len, dtype=np.uint16)
        for n in range(num_cycles):
            wav[n * cycle_len : (n + 1) * cycle_len] = y

        return wav

    def add_markers(self, dat_buff, marker_pos, marker_width, marker_bit1, marker_bit2, dat_offs=0, dat_len=None):
        """Add markers bits to the wave-data in the given buffer.

        Note that in case of 4-channels devices, the markers bits
        are both added to the 1st channel of each channels-pair.

        IMPORTANT: This function currently fits only 4-channels devices (WX2184 / WX1284).

        :param dat_buff: `numpy` array containing the wave-data (data-type='uint16')
        :param marker_pos: the marker start-position within the wave-data (in wave-points)
        :param marker_width: the marker width (in wave-points).
        :param marker_bit1: the value of 1st marker's bit (zero or one)
        :param marker_bit2: the value of 2nd marker's bit (zero or one)
        :param dat_offs: the offset of the wave-data within the data-buffer (default: 0).
        :param dat_len: the length of the actual wave-data (default: the length of `dat_buff`).
        """

        shift_pts = 12

        if dat_len is None:
            dat_len = len(dat_buff) - dat_offs

        if len(dat_buff) > 0 and dat_len > 0 and marker_width > 0:

            marker_bits = 0
            if marker_bit1:
                marker_bits |= 0x4000
            if marker_bit2:
                marker_bits |= 0x8000

            assert(marker_pos % 2 == 0)
            assert(marker_width % 2 == 0)
            assert(dat_len % 16 == 0 and dat_len >= 16)

            seg_pos = (marker_pos + shift_pts) % dat_len
            seg_pos = (seg_pos//16)*16 + 8 + (seg_pos%16)//2

            while marker_width > 0:
                if seg_pos >= dat_len:
                    seg_pos = 8

                buf_index = (dat_offs + seg_pos) % len(dat_buff)
                dat_buff[buf_index] &= 0x3fff
                dat_buff[buf_index] |= marker_bits

                marker_width -= 2
                seg_pos += 1
                if seg_pos % 16 == 0:
                    seg_pos += 8

    @staticmethod
    def make_combined_wave(wav1, wav2, dest_array, dest_array_offset=0, add_idle_pts=False, quantum=16):
        '''Make 2-channels combined wave from the 2 given waves

        The destination-array, `dest_array`, is either a `numpy.array` with `dtype=uint16`, or `None`.
        If it is `None` then only the next destination-array's write-offset offset is calculated.

        Each of the given waves, `wav1` and `wav2`, is either a `numpy.array` with `dtype=uint16`, or `None`.
        If it is `None`, then the corresponding entries of `dest_array` are not changed.

        :param wav1: the DAC values of wave 1 (either `numpy.array` with `dtype=uint16`, or `None`).
        :param wav2: the DAC values of wave 2 (either `numpy.array` with `dtype=uint16`, or `None`).
        :param dest_array: the destination-array (either `numpy.array` with `dtype=uint16`, or `None`).
        :param dest_array_offset: the destination-array's write-offset.
        :param add_idle_pts: should add idle-points (segment-prefix)?
        :param quantum: the combined-wave quantum (usually 16 points)
        :returns: the next destination-array's write-offset.
        '''
        len1, len2 = 0,0
        if wav1 is not None:
            len1 = len(wav1)

        if wav2 is not None:
            len2 = len(wav2)

        wav_len = max(len1, len2)
        if 0 == wav_len:
            return dest_array_offset

        if wav_len % quantum != 0:
            wav_len = wav_len + (quantum - wav_len % quantum)

        tot_len = 2 * wav_len
        if add_idle_pts:
            tot_len = tot_len + 2 * quantum

        if dest_array is None:
            return dest_array_offset + tot_len

        dest_len = len(dest_array)

        if min(quantum, len2) > 0:
            rd_offs = 0
            wr_offs = dest_array_offset
            if add_idle_pts:
                wr_offs = wr_offs + 2 * quantum

            while rd_offs < len2 and wr_offs < dest_len:
                chunk_len = min((quantum, len2 - rd_offs, dest_len - wr_offs))
                dest_array[wr_offs : wr_offs + chunk_len] = wav2[rd_offs : rd_offs + chunk_len]
                rd_offs = rd_offs + chunk_len
                wr_offs = wr_offs + chunk_len + quantum

            if add_idle_pts:
                rd_offs = 0
                wr_offs = dest_array_offset
                chunk_len = min(quantum, dest_len - wr_offs)
                if chunk_len > 0:
                    dest_array[wr_offs : wr_offs + chunk_len] = wav2[0]

        if min(quantum, len1) > 0:
            rd_offs = 0
            wr_offs = dest_array_offset + quantum
            if add_idle_pts:
                wr_offs = wr_offs + 2 * quantum

            while rd_offs < len1 and wr_offs < dest_len:
                chunk_len = min((quantum, len1 - rd_offs, dest_len - wr_offs))
                dest_array[wr_offs : wr_offs + chunk_len] = wav1[rd_offs : rd_offs + chunk_len]
                rd_offs = rd_offs + chunk_len
                wr_offs = wr_offs + chunk_len + quantum

            if add_idle_pts:
                rd_offs = 0
                wr_offs = dest_array_offset + quantum
                chunk_len = min(quantum, dest_len - wr_offs)
                if chunk_len > 0:
                    dest_array[wr_offs : wr_offs + chunk_len] = wav1[0]

        return dest_array_offset + tot_len

    @staticmethod
    def _make_bin_dat_header(pref, bin_dat_size):
        '''make binary-data-header '''
        size_str = '{0:d}'.format(bin_dat_size)
        if pref is None:
            pref = ''
        bin_dat_header = '{0}#{1:d}{2:s}'.format(pref, len(size_str), size_str)
        return bin_dat_header

    def _send_raw_bin_dat(self, bin_data):
        '''Send the given binary-data (`numpy.ndarray`) through the tcp socket (no binary-data-header is added) '''

        assert (self._intf_type != CommIntfType.NIL)

        if bin_data.ndim > 1:
            bin_data = bin_data.flatten()

        if self._intf_type == CommIntfType.USB:
            #self._usb_sock.write_raw(bin_data.tobytes())
            MAX_CHUNK_LEN = 4096
            if MAX_CHUNK_LEN // bin_data.itemsize < 1:
                bin_data = np.frombuffer(bin_data.data, dtype='uint8')
            num_items = len(bin_data)
            item_size = bin_data.itemsize
            chunk_len = MAX_CHUNK_LEN // item_size
            offset = 0
            while offset < num_items:
                if offset + chunk_len >= num_items:
                    chunk_len = num_items - offset
                # send the packet:
                self._usb_sock.write_raw(bin_data[offset : offset + chunk_len].tobytes())
                offset = offset + chunk_len
        elif self._intf_type == CommIntfType.LAN:
            MAX_CHUNK_LEN = 4096
            if MAX_CHUNK_LEN // bin_data.itemsize < 1:
                bin_data = np.frombuffer(bin_data.data, dtype='uint8')
            num_items = len(bin_data)
            item_size = bin_data.itemsize
            chunk_len = MAX_CHUNK_LEN // item_size
            offset = 0
            while offset < num_items:
                if offset + chunk_len >= num_items:
                    chunk_len = num_items - offset
                # send the packet:
                self._tcp_sock.sendall(bin_data[offset : offset + chunk_len].tobytes())
                offset = offset + chunk_len

    def _set_instr_address(self, instr_addr):
        '''Set the instrument address

        The given `instr_addr` can be either
         - An empty string or None (meaning no address)
         - IP-Address in digits and dots format (e.g. '192.168.0.170')
         - TCPIP NI-VISA format: 'TCPIP::<IP-Address>::<PortNo>::SOCKET'
           (for example: 'TCPIP:192.168.0.170::5025::SOCKET')
         - USB NI-VISA short-format: 'USB::<VendorId>::<ProductId>::INSTR
           (for example: 'USB::0x168b::0x2184::INSTR')
         - USB NI-VISA long-format: 'USB::<VendorId>::<ProductId>::<SerialNo>::INSTR
           (for example: 'USB::0x168b::0x2184::0000214991::INSTR')

        :param instr_addr: the instrument address (string)
        '''

        self._ip_addr = None
        self._usb_addr = None
        self._instr_addr = None
        self._tcp_port_nb = None

        if instr_addr is None or len(instr_addr) == 0:
            return

        # try to parse it as an IP-Address
        try:
            packed_ip = socket.inet_aton(instr_addr)
            ip_str = socket.inet_ntoa(packed_ip)
            self._ip_addr =  ip_str
            self._tcp_port_nb = 5025 # this is the default port number for wx devices
            self._instr_addr = "TCPIP::{0}::5025::SOCKET".format(ip_str)
            return
        except:
            pass

        addr_parts = instr_addr.split('::')
        for n in range(len(addr_parts)):
            addr_parts[n] = addr_parts[n].upper()

        if len(addr_parts) >= 1 and addr_parts[0].startswith('USB'):
            self._usb_addr = instr_addr
            self._instr_addr = instr_addr
            return

        if len(addr_parts) == 4 and addr_parts[0].startswith('TCPIP'):
            try:
                packed_ip = socket.inet_aton(addr_parts[1])
                ip_str = socket.inet_ntoa(packed_ip)
                port_nb = int(addr_parts[2])
                self._ip_addr =  ip_str
                self._tcp_port_nb = port_nb
                self._instr_addr = instr_addr
                return
            except:
                pass

        self._instr_addr = instr_addr




def wx_istrument_example():
    '''Example of use

    Connect to WX-Instrument, download 3 segments
    and define (simple) sequence based on those 3 segments.
    '''
    # print
    ip_addr = input('Please enter the instrument\'s IP-Address (for example: 192.168.0.199): ')
    # print

    with TEWXAwg(ip_addr, paranoia_level=2) as inst:

        idn = inst.send_query('*IDN?')
        # print 'connected to {0}\n'.format(idn)

        # reset instrument and clear error-list
        inst.send_cmd('*CLS; *RST')

        # select active channel
        inst.send_cmd(':INST:SEL 1')

        # set  function-mode: 'USER' (arbitrary-wave)
        inst.send_cmd('FUNCtion:MODE USER')

        # delete previously defined segments (not really necessary after *RST)
        inst.send_cmd(':TRACE:DEL:ALL')

        # set sampling-rate
        inst.send_cmd(':SOUR:FREQ:RAST 1.0e9')

        # ---------------------------------------------------------------------
        # download sine-wave with cycle-length of  1024 points to segment 1
        # ---------------------------------------------------------------------

        # print
        # print 'downloading sine-wave with cycle-length of 1024 points to segment 1 ...'

        seg_nb = 1
        cycle_len = 1024
        num_cycles = 1
        seg_len = cycle_len * num_cycles
        wav_dat = inst.build_sine_wave(cycle_len, num_cycles)

        # define the length of segment 1
        inst.send_cmd(':TRAC:DEF {0:d},{1:d}'.format(seg_nb, seg_len))

        # select segment 1 as the active segment
        # (the one to which binary-data is downloaded)
        inst.send_cmd(':TRAC:SEL {0:d}'.format(seg_nb))

        # download the binary wave data:
        inst.send_binary_data(pref=':TRAC:DATA', bin_dat=wav_dat)


        # ---------------------------------------------------------------------
        # download triangle-wave with cycle-length of 1024 points to segment 2
        # ---------------------------------------------------------------------

        # print
        # print 'downloading triangle-wave with cycle-length of 1024 points to segment 2 ...'

        seg_nb = 2
        cycle_len = 1024
        num_cycles = 1
        seg_len = cycle_len * num_cycles
        wav_dat = inst.build_triangle_wave(cycle_len, num_cycles)

        # define the length of segment 1
        inst.send_cmd(':TRAC:DEF {0:d},{1:d}'.format(seg_nb, seg_len))

        # select segment 1 as the active segment
        # (the one to which binary-data is downloaded)
        inst.send_cmd(':TRAC:SEL {0:d}'.format(seg_nb))

        # download the binary wave data:
        inst.send_binary_data(pref=':TRAC:DATA', bin_dat=wav_dat)

        # ---------------------------------------------------------------------
        # download square-wave with cycle-length of 1024 points to segment 3
        # ---------------------------------------------------------------------

        # print
        # print 'downloading square-wave with cycle-length of 1024 points to segment 3 ...'

        seg_nb = 3
        cycle_len = 1024
        num_cycles = 1
        seg_len = cycle_len * num_cycles
        wav_dat = inst.build_square_wave(cycle_len, num_cycles)

        # define the length of segment 1
        inst.send_cmd(':TRAC:DEF {0:d},{1:d}'.format(seg_nb, seg_len))

        # select segment 1 as the active segment
        # (the one to which binary-data is downloaded)
        inst.send_cmd(':TRAC:SEL {0:d}'.format(seg_nb))

        # download the binary wave data:
        inst.send_binary_data(pref=':TRAC:DATA', bin_dat=wav_dat)

        wav_dat = None # let the garbage-collecteor free it

        # ---------------------------------------------------------------------
        # define sequence based on those three segments:
        # ---------------------------------------------------------------------

        # print
        # print 'define sequencer based on those 3 segments ..'
        # create sequencer table:
        seg_num  = [2, 1, 2, 3, 1 ]
        repeats  = [5, 4, 3, 2, 1 ]
        jump     = [0, 0, 0, 0, 0 ]
        seq_table = zip(repeats, seg_num, jump)

        # select sequencer 1 as the active sequencer (the one that being editted)
        inst.send_cmd(':SEQ:SELect 1')

        # download the sequencer table:
        inst.download_sequencer_table(seq_table)

        # set  function-mode: 'SEQ' (simple sequencer)
        inst.send_cmd('FUNCtion:MODE SEQ')

        # turn on the active-channel's output:
        inst.send_cmd(':OUTP ON')

        syst_err = inst.send_query(':SYST:ERR?')
        # print
        # print 'End of the example - status: {0}'.format(syst_err)
        # print


if __name__ == "__main__":
    wx_istrument_example()























