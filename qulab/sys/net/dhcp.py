# Packet format
# -------------
#
# Offset    Length   Notes
# ------    ------   -----
#
#   0       1        Operation code with 1 being request and 2 being response
#   1       1        Hardware type with 1 being "Ethernet 10Mb"
#   2       1        Hardware address length with 6 for Ethernet
#   3       1        Hops - usually 0 unless DHCP relaying in operation
#   4-7     4        Transaction ID (selected randomly by client)
#   8-9     2        Seconds - might be used by a server to prioritise requests
#  10-11    2        Flags (only most significan bit used for broadcast)
#  12-15    4        Client Internet address (might be requested by client)
#  16-19    4        Your Internet address (the IP assigned by the server)
#  20-23    4        Server Internet address (the IP of the server)
#  24-27    4        Gateway Internet address (if DHCP relaying in operation)
#  28-43    16       Client hardware address - only first 6 bytes used for Ethernet
#  44-107   64       Text name of server (optional)
# 108-235   128      Boot file name (optional - used for PXE booting)
# 236-239   4        Magic cookie (decimal values 99, 130, 83, 99 )
#

# Dynamic Host Configuration Protocol (DHCP) and Bootstrap Protocol (BOOTP) Parameters
# See http://www.iana.org/assignments/bootp-dhcp-parameters

import base64
import logging
import socket
from enum import Enum
from struct import Struct, pack, unpack
from typing import NamedTuple

MAGIC_COOKIE = b'c\x82Sc'


class DHCPOption(Enum):
    PAD = 0  # 0 [RFC2132] None
    SUBNET_MASK = 1  # 4 [RFC2132] Subnet Mask Value
    TIME_OFFSET = 2  # 4 [RFC2132] Time Offset in Seconds from UTC (note: deprecated by 100 and 101)
    ROUTER = 3  # N [RFC2132] N/4 Router addresses
    TIME_SERVER = 4  # N [RFC2132] N/4 Timeserver addresses
    NAME_SERVER = 5  # N [RFC2132] N/4 IEN-116 Server addresses
    DOMAIN_SERVER = 6  # N [RFC2132] N/4 DNS Server addresses
    LOG_SERVER = 7  # N [RFC2132] N/4 Logging Server addresses
    QUOTES_SERVER = 8  # N [RFC2132] N/4 Quotes Server addresses
    LPR_SERVER = 9  # N [RFC2132] N/4 Printer Server addresses
    IMPRESS_SERVER = 10  # N [RFC2132] N/4 Impress Server addresses
    RLP_SERVER = 11  # N [RFC2132] N/4 RLP Server addresses
    HOSTNAME = 12  # N [RFC2132] Hostname string
    BOOT_FILE_SIZE = 13  # 2 [RFC2132] Size of boot file in 512 byte chunks
    MERIT_DUMP_FILE = 14  # N [RFC2132] Client to dump and name the file to dump it to
    DOMAIN_NAME = 15  # N [RFC2132] The DNS domain name of the client
    SWAP_SERVER = 16  # N [RFC2132] Swap Server address
    ROOT_PATH = 17  # N [RFC2132] Path name for root disk
    EXTENSION_FILE = 18  # N [RFC2132] Path name for more BOOTP info
    FORWARD = 19  # 1 [RFC2132] Enable/Disable IP Forwarding
    SRCRTE = 20  # 1 [RFC2132] Enable/Disable Source Routing
    POLICY_FILTER = 21  # N [RFC2132] Routing Policy Filters
    MAX_DG_ASSEMBLY = 22  # 2 [RFC2132] Max Datagram Reassembly Size
    DEFAULT_IP_TTL = 23  # 1 [RFC2132] Default IP Time to Live
    MTU_TIMEOUT = 24  # 4 [RFC2132] Path MTU Aging Timeout
    MTU_PLATEAU = 25  # N [RFC2132] Path MTU Plateau Table
    MTU_INTERFACE = 26  # 2 [RFC2132] Interface MTU Size
    MTU_SUBNET = 27  # 1 [RFC2132] All Subnets are Local
    BROADCAST_ADDRESS = 28  # 4 [RFC2132] Broadcast Address
    MASK_DISCOVERY = 29  # 1 [RFC2132] Perform Mask Discovery
    MASK_SUPPLIER = 30  # 1 [RFC2132] Provide Mask to Others
    ROUTER_DISCOVERY = 31  # 1 [RFC2132] Perform Router Discovery
    ROUTER_REQUEST = 32  # 4 [RFC2132] Router Solicitation Address
    STATIC_ROUTE = 33  # N [RFC2132] Static Routing Table
    TRAILERS = 34  # 1 [RFC2132] Trailer Encapsulation
    ARP_TIMEOUT = 35  # 4 [RFC2132] ARP Cache Timeout
    ETHERNET = 36  # 1 [RFC2132] Ethernet Encapsulation
    DEFAULT_TCP_TTL = 37  # 1 [RFC2132] Default TCP Time to Live
    KEEPALIVE_TIME = 38  # 4 [RFC2132] TCP Keepalive Interval
    KEEPALIVE_DATA = 39  # 1 [RFC2132] TCP Keepalive Garbage
    NIS_DOMAIN = 40  # N [RFC2132] NIS Domain Name
    NIS_SERVERS = 41  # N [RFC2132] NIS Server Addresses
    NTP_SERVERS = 42  # N [RFC2132] NTP Server Addresses
    VENDOR_SPECIFIC = 43  # N [RFC2132] Vendor Specific Information
    NETBIOS_NAME_SRV = 44  # N [RFC2132] NETBIOS Name Servers
    NETBIOS_DIST_SRV = 45  # N [RFC2132] NETBIOS Datagram Distribution
    NETBIOS_NODE_TYPE = 46  # 1 [RFC2132] NETBIOS Node Type
    NETBIOS_SCOPE = 47  # N [RFC2132] NETBIOS Scope
    X_WINDOW_FONT = 48  # N [RFC2132] X Window Font Server
    X_WINDOW_MANAGER = 49  # N [RFC2132] X Window Display Manager
    ADDRESS_REQUEST = 50  # 4 [RFC2132] Requested IP Address
    IP_LEASE_TIME = 51  # 4 [RFC2132] IP Address Lease Time
    OVERLOAD = 52  # 1 [RFC2132] Overload "sname" or "file"
    DHCP_MSG_TYPE = 53  # 1 [RFC2132] DHCP Message Type
    SERVER_ID = 54  # 4 [RFC2132] DHCP Server Identification
    PARAMETER_LIST = 55  # N [RFC2132] Parameter Request List
    DHCP_MESSAGE = 56  # N [RFC2132] DHCP Error Message
    DHCP_MAX_MSG_SIZE = 57  # 2 [RFC2132] DHCP Maximum Message Size
    RENEWAL_TIME = 58  # 4 [RFC2132] DHCP Renewal (T1) Time
    REBINDING_TIME = 59  # 4 [RFC2132] DHCP Rebinding (T2) Time
    CLASS_ID = 60  # N [RFC2132] Class Identifier
    CLIENT_ID = 61  # N [RFC2132] Client Identifier
    NETWARE_IP_DOMAIN = 62  # N [RFC2242] NetWare/IP Domain Name
    NETWARE_IP_OPTION = 63  # N [RFC2242] NetWare/IP sub Options
    NIS_DOMAIN_NAME = 64  # N [RFC2132] NIS+ v3 Client Domain Name
    NIS_SERVER_ADDR = 65  # N [RFC2132] NIS+ v3 Server Addresses
    SERVER_NAME = 66  # N [RFC2132] TFTP Server Name
    BOOTFILE_NAME = 67  # N [RFC2132] Boot File Name
    HOME_AGENT_ADDRS = 68  # N [RFC2132] Home Agent Addresses
    SMTP_SERVER = 69  # N [RFC2132] Simple Mail Server Addresses
    POP3_SERVER = 70  # N [RFC2132] Post Office Server Addresses
    NNTP_SERVER = 71  # N [RFC2132] Network News Server Addresses
    WWW_SERVER = 72  # N [RFC2132] WWW Server Addresses
    FINGER_SERVER = 73  # N [RFC2132] Finger Server Addresses
    IRC_SERVER = 74  # N [RFC2132] Chat Server Addresses
    STREETTALK_SERVER = 75  # N [RFC2132] StreetTalk Server Addresses
    STDA_SERVER = 76  # N [RFC2132] ST Directory Assist. Addresses
    USER_CLASS = 77  # N [RFC3004] User Class Information
    DIRECTORY_AGENT = 78  # N [RFC2610] directory agent information
    SERVICE_SCOPE = 79  # N [RFC2610] service location agent scope
    RAPID_COMMIT = 80  # 0 [RFC4039] Rapid Commit
    CLIENT_FQDN = 81  # N [RFC4702] Fully Qualified Domain Name
    RELAY_AGENT_INFORMATION = 82  # N [RFC3046] Relay Agent Information
    ISNS = 83  # N [RFC4174] Internet Storage Name Service
    # 84 REMOVED/Unassigned [RFC3679]
    NDS_SERVERS = 85  # N [RFC2241] Novell Directory Services
    NDS_TREE_NAME = 86  # N [RFC2241] Novell Directory Services
    NDS_CONTEXT = 87  # N [RFC2241] Novell Directory Services
    BCMCS_CONTROLLER_DOMAIN_NAME_LIST = 88  #  [RFC4280]
    BCMCS_CONTROLLER_IPV4_ADDRESS_OPTION = 89  #  [RFC4280]
    AUTHENTICATION = 90  # N [RFC3118] Authentication
    CLIENT_LAST_TRANSACTION_TIME_OPTION = 91  #  [RFC4388]
    ASSOCIATED_IP_OPTION = 92  #  [RFC4388]
    CLIENT_SYSTEM = 93  # N [RFC4578] Client System Architecture
    CLIENT_NDI = 94  # N [RFC4578] Client Network Device Interface
    LDAP = 95  # N [RFC3679] Lightweight Directory Access Protocol
    # 96 REMOVED/Unassigned [RFC3679]
    UUID = 97  # N [RFC4578] UUID/GUID-based Client Identifier
    USER_AUTH = 98  # N [RFC2485] Open Group's User Authentication
    GEOCONF_CIVIC = 99  #  [RFC4776]
    PCODE = 100  # N [RFC4833] IEEE 1003.1 TZ String
    TCODE = 101  # N [RFC4833] Reference to the TZ Database
    # 102-107 REMOVED/Unassigned [RFC3679]
    IPV6_ONLY_PREFERRED = 108  # 4 [RFC8925] Number of seconds that DHCPv4 should be disabled
    OPTION_DHCP4O6_S46_SADDR = 109  # 16 [RFC8539] DHCPv4 over DHCPv6 Softwire Source Address Option
    # 110 REMOVED/Unassigned [RFC3679]
    # 111 Unassigned [RFC3679]
    NETINFO_ADDRESS = 112  # N [RFC3679] NetInfo Parent Server Address
    NETINFO_TAG = 113  # N [RFC3679] NetInfo Parent Server Tag
    DHCP_CAPTIVE_PORTAL = 114  # N [RFC8910] DHCP Captive-Portal
    # 115 REMOVED/Unassigned [RFC3679]
    AUTO_CONFIG = 116  # N [RFC2563] DHCP Auto-Configuration
    NAME_SERVICE_SEARCH = 117  # N [RFC2937] Name Service Search
    SUBNET_SELECTION_OPTION = 118  # 4 [RFC3011] Subnet Selection Option
    DOMAIN_SEARCH = 119  # N [RFC3397] DNS domain search list
    SIP_SERVERS_DHCP_OPTION = 120  # N [RFC3361] SIP Servers DHCP Option
    CLASSLESS_STATIC_ROUTE_OPTION = 121  # N [RFC3442] Classless Static Route Option
    CCC = 122  # N [RFC3495] CableLabs Client Configuration
    GEOCONF_OPTION = 123  # 16 [RFC6225] GeoConf Option
    VI_VENDOR_CLASS = 124  #  [RFC3925] Vendor-Identifying Vendor Class
    VI_VENDOR_SPECIFIC_INFORMATION = 125  #  [RFC3925] Vendor-Identifying Vendor-Specific Information
    # 128	PXE - undefined (vendor specific)			[RFC4578]
    # 128	Etherboot signature. 6 bytes: E4:45:74:68:00:00
    # 128	DOCSIS "full security" server IP address
    # 128	TFTP Server IP address (for IP Phone software load)
    # 129	PXE - undefined (vendor specific)			[RFC4578]
    # 129	Kernel options. Variable length string
    # 129	Call Server IP address
    # 130	PXE - undefined (vendor specific)			[RFC4578]
    # 130	Ethernet interface. Variable length string.
    # 130	Discrimination string (to identify vendor)
    # 131	PXE - undefined (vendor specific)			[RFC4578]
    # 131	Remote statistics server IP address
    # 132	PXE - undefined (vendor specific)			[RFC4578]
    # 132	IEEE 802.1Q VLAN ID
    # 133	PXE - undefined (vendor specific)			[RFC4578]
    # 133	IEEE 802.1D/p Layer 2 Priority
    # 134	PXE - undefined (vendor specific)			[RFC4578]
    # 134	Diffserv Code Point (DSCP) for VoIP signalling and media streams
    # 135	PXE - undefined (vendor specific)			[RFC4578]
    # 135	HTTP Proxy for phone-specific applications
    OPTION_PANA_AGENT = 136  #  [RFC5192]
    OPTION_V4_LOST = 137  #  [RFC5223]
    OPTION_CAPWAP_AC_V4 = 138  # N [RFC5417] CAPWAP Access Controller addresses
    OPTION_IPV4_ADDRESS_MOS = 139  # N [RFC5678] a series of suboptions
    OPTION_IPV4_FQDN_MOS = 140  # N [RFC5678] a series of suboptions
    SIP_UA_CONFIGURATION_SERVICE_DOMAINS = 141  # N [RFC6011] List of domain names to search for SIP User Agent Configuration
    OPTION_IPV4_ADDRESS_ANDSF = 142  # N [RFC6153] ANDSF IPv4 Address Option for DHCPv4
    OPTION_V4_SZTP_REDIRECT = 143  # N [RFC8572] This option provides a list of URIs for SZTP bootstrap servers
    GEOLOC = 144  # 16 [RFC6225] Geospatial Location with Uncertainty
    FORCERENEW_NONCE_CAPABLE = 145  # 1 [RFC6704] Forcerenew Nonce Capable
    RDNSS_SELECTION = 146  # N [RFC6731] Information for selecting RDNSS
    OPTION_V4_DOTS_RI = 147  # N [RFC8973] The name of the peer DOTS agent.
    OPTION_V4_DOTS_ADDRESS = 148  # N (the minimal length is 4) [RFC8973] N/4 IPv4 addresses of peer DOTS agent(s).
    # 149 Unassigned [RFC3942]
    TFTP_SERVER_ADDRESS = 150  #  [RFC5859]
    STATUS_CODE = 151  # N+1 [RFC6926] Status code and optional N byte text message describing status.
    BASE_TIME = 152  # 4 [RFC6926] Absolute time (seconds since Jan 1, 1970) message was sent.
    START_TIME_OF_STATE = 153  # 4 [RFC6926] Number of seconds in the past when client entered current state.
    QUERY_START_TIME = 154  # 4 [RFC6926] Absolute time (seconds since Jan 1, 1970) for beginning of query.
    QUERY_END_TIME = 155  # 4 [RFC6926] Absolute time (seconds since Jan 1, 1970) for end of query.
    DHCP_STATE = 156  # 1 [RFC6926] State of IP address.
    DATA_SOURCE = 157  # 1 [RFC6926] Indicates information came from local or remote server.
    OPTION_V4_PCP_SERVER = 158  # Variable; the minimum length is 5. [RFC7291] Includes one or multiple lists of PCP server IP addresses; each list is treated as a separate PCP server.
    OPTION_V4_PORTPARAMS = 159  # 4 [RFC7618] This option is used to configure a set of ports bound to a shared IPv4 address.
    # 160 Unassigned [RFC7710][RFC8910] Previously assigned by [RFC7710]; known to also be used by Polycom.
    OPTION_MUD_URL_V4 = 161  # N (variable) [RFC8520] Manufacturer Usage Descriptions
    OPTION_V4_DNR = 162  # N [RFC-ietf-add-dnr-13] Encrypted DNS Server
    # 163-174 Unassigned [RFC3942]
    # ETHERBOOT = 175  # Tentatively Assigned - 2005-06-23
    # IP_TELEPHONE = 176  # Tentatively Assigned - 2005-06-23
    # ETHERBOOT = 177  # Tentatively Assigned - 2005-06-23
    # PACKETCABLE_AND_CABLEHOME = 177  # replaced by 122
    # 178-207 Unassigned [RFC3942]
    PXELINUX_MAGIC = 208  # 4 [RFC5071][Deprecated] magic string = F1:00:74:7E
    CONFIGURATION_FILE = 209  # N [RFC5071] Configuration file
    PATH_PREFIX = 210  # N [RFC5071] Path Prefix Option
    REBOOT_TIME = 211  # 4 [RFC5071] Reboot Time
    OPTION_6RD = 212  # 18 + N [RFC5969] OPTION_6RD with N/4 6rd BR addresses
    OPTION_V4_ACCESS_DOMAIN = 213  # N [RFC5986] Access Network Domain Name
    # 214-219 Unassigned
    SUBNET_ALLOCATION_OPTION = 220  # N [RFC6656] Subnet Allocation Option
    VSS_OPTION = 221  # Virtual Subnet Selection (VSS) Option [RFC6607]
    # 222-223 Unassigned [RFC3942]
    # 224-254 Reserved (Private Use)
    WPAD_PROXY_URL = 252
    END = 255  # 0 [RFC2132] None


class DHCPMessageType(Enum):
    # 53 Values
    DISCOVER = 1  # RFC 2131
    OFFER = 2  # RFC 2131
    REQUEST = 3  # RFC 2131
    DECLINE = 4  # RFC 2131
    ACK = 5  # RFC 2131
    NAK = 6  # RFC 2131
    RELEASE = 7  # RFC 2131
    INFORM = 8  # RFC 2131
    FORCERENEW = 9  # RFC 3203
    LEASEQUERY = 10  # RFC 4388
    LEASEUNASSIGNED = 11  # RFC 4388
    LEASEUNKNOWN = 12  # RFC 4388
    LEASEACTIVE = 13  # RFC 4388
    BULKLEASEQUERY = 14  # RFC 6926
    LEASEQUERYDONE = 15  # RFC 6926
    ACTIVELEASEQUERY = 16  # RFC 7724
    LEASEQUERYSTATUS = 17  # RFC 7724
    TLS = 18  # RFC 7724


class DHCPStatusCodeType(Enum):
    # 151 Values
    Success = 0  # RFC 6926
    UnspecFail = 1  # RFC 6926
    QueryTerminated = 2  # RFC 6926
    MalformedQuery = 3  # RFC 6926
    NotAllowed = 4  # RFC 6926
    DataMissing = 5  # RFC 7724
    ConnectionActive = 6  # RFC 7724
    CatchUpComplete = 7  # RFC 7724
    TLSConnectionRefused = 8  # RFC 7724


def mac_aton(s: str) -> bytes:
    try:
        haddr = [int(n, base=16) for n in s.split(':')]
        if not all(0 <= x <= 0xff for x in haddr):
            raise ValueError
    except:
        raise ValueError(f"Invalid MAC address {s!r}.")
    return bytes(haddr)


def mac_ntoa(b: bytes) -> str:
    return ':'.join([f"{x:02X}" for x in b])


def readable_packet(data: bytes) -> str:
    bpr = 16  # bpr is Bytes Per Row
    numbytes = len(data)

    if numbytes == 0:
        return " <empty packet>"
    else:
        output = ""
        i = 0
        while i < numbytes:
            if (i % bpr) == 0:
                output += f" {i:04d} :"

            output += f" {data[i]:02X}"

            if ((i + 1) % bpr) == 0:
                output += "\n"

            i = i + 1

    if (numbytes % bpr) != 0:
        output += "\n"

    return output


def buildbytesoption(optnum, ba):
    lenba = len(ba)

    if (ba) == 0:
        opt = bytearray(1)
        opt[0] = optnum
    else:
        opt = bytearray(2 + lenba)
        opt[0] = optnum
        opt[1] = lenba
        opt[2:2 + lenba] = ba

    return opt


def build1byteoption(optnum, databyte):
    return bytearray([optnum, 1, databyte])


def build4byteoption(optnum, d1, d2, d3, d4):
    optbytes = bytearray(6)
    optbytes[0] = optnum
    optbytes[1] = 4
    optbytes[2] = d1
    optbytes[3] = d2
    optbytes[4] = d3
    optbytes[5] = d4

    return optbytes


def buildstringoption(optnum, string):
    optbytes = bytearray(2 + len(string))
    optbytes[0] = optnum
    optbytes[1] = len(string)
    d = 2
    for c in string:
        optbytes[d] = ord(c)
        if d == len(string) + 1:
            if c == "/":
                optbytes[d] = 0
        d += 1

    return optbytes


def buildendoption():
    optbytes = bytearray(1)
    optbytes[0] = 255

    return optbytes


class DHCPPacket():

    _format = Struct('!BBBBIHH4s4s4s4s16s64s128s4s')

    def __init__(self):
        self.op = 0
        self.htype = 1
        self.hlen = 6
        self.hops = 0
        self.xid = 0
        self.secs = 0
        self.flags = 0
        self.ciaddr = '0.0.0.0'
        self.yiaddr = '0.0.0.0'
        self.siaddr = '0.0.0.0'
        self.giaddr = '0.0.0.0'
        self.chaddr = '00:00:00:00:00:00'
        self.sname = ''
        self.file = ''
        self.options = {}
        self.data = None

    def encode(self):
        if self.data is not None:
            return self.data

        buf = DHCPPacket._format.pack(self.op, self.htype, self.hlen,
                                      self.hops, self.xid,
                                      self.secs, self.flags,
                                      socket.inet_aton(self.ciaddr),
                                      socket.inet_aton(self.yiaddr),
                                      socket.inet_aton(self.siaddr),
                                      socket.inet_aton(self.giaddr),
                                      mac_aton(self.chaddr),
                                      self.sname.encode(), self.file.encode(),
                                      MAGIC_COOKIE)

        ret = [buf]
        for opt, data in self.options.items():
            ret.append(bytearray([opt, len(data)]))
            ret.append(data)
        ret.append(bytearray([DHCPOption.END.value]))
        self.data = b''.join(ret)
        return self.data

    @classmethod
    def decode(cls, data):
        if len(data) < DHCPPacket._format.size:
            raise ValueError("Not enough data to decode")

        packet = cls()
        packet.data = data

        (packet.op, packet.htype, packet.hlen, packet.hops, packet.xid,
         packet.secs, packet.flags, ciaddr, yiaddr, siaddr, giaddr, chaddr,
         sname, file, magic_cookie) = DHCPPacket._format.unpack(
             data[:DHCPPacket._format.size])

        if magic_cookie != MAGIC_COOKIE:
            raise ValueError("Invalid message")

        packet.ciaddr = socket.inet_ntoa(ciaddr)
        packet.yiaddr = socket.inet_ntoa(yiaddr)
        packet.siaddr = socket.inet_ntoa(siaddr)
        packet.giaddr = socket.inet_ntoa(giaddr)

        packet.chaddr = mac_ntoa(chaddr[0:packet.hlen])
        packet.sname = sname.decode('utf-8')
        packet.file = file.decode('utf-8')

        offset = DHCPPacket._format.size

        while offset < len(data):
            option = data[offset]
            offset += 1
            if option == DHCPOption.PAD.value:
                continue
            elif option == DHCPOption.END.value:
                break
            optlen = data[offset]
            offset += 1
            if (offset + optlen) >= len(data):
                raise ValueError("Invalid option length")
            packet.options[option] = data[offset:offset + optlen]
            offset += optlen

        return packet

    def __str__(self):
        DHCP_ops = {0: 'ERROR_UNDEF', 1: 'BOOTREQUEST', 2: 'BOOTREPLY'}

        lines = [
            "###################### Header fields ######################",
            f"                      op : {DHCP_ops[self.op]}",
            f"                   htype : {self.htype}",
            f"                    hlen : {self.hlen}",
            f"                    hops : {self.hops}",
            f"                     xid : 0x{self.xid:08x}",
            f"                    secs : {self.secs}",
            f"                   flags : {self.flags}",
            f"       Client IP address : {self.ciaddr}",
            f"         Your IP address : {self.yiaddr}",
            f"       Server IP address : {self.siaddr}",
            f"      Gateway IP address : {self.giaddr}",
            f" Client hardware address : {self.chaddr}",
            "##################### Options fields ######################"
        ]
        for opt, value in self.options.items():
            if opt == 53:
                value = DHCPMessageType(value[0]).name
            elif opt in [50, 54, 1, 3, 6]:
                value = socket.inet_ntoa(value)
            elif opt in [51, 58, 59]:
                value = unpack('!I', value)[0]
            elif opt in [57]:
                value = unpack('!H', value)[0]
            elif opt in [12, 15, 56]:
                value = value.decode()
            elif opt in [28, 33, 42]:
                value = [
                    socket.inet_ntoa(x)
                    for x in [value[i:i + 4] for i in range(0, len(value), 4)]
                ]
                value = f'{value[0]}\n' + '\n'.join(f"{'':39s} : {x}"
                                                    for x in value[1:])
            elif opt in [55]:
                value = (f"({value[0]:3d}) {DHCPOption(value[0]).name}\n" +
                         '\n'.join(f"{'':39s} : ({x:3d}) {DHCPOption(x).name}"
                                   for x in value[1:]))
            elif opt in [61]:
                value = f"{value[0]} - {mac_ntoa(value[1:])}"
            else:
                value = f"({len(value):2d}) {base64.b16encode(value).decode()}"
            opt_name = DHCPOption(opt).name
            lines.append(f"    {opt_name:29s} ({opt:3d}) : {value}")

        if self.data is not None:
            lines.append(
                "######################## Raw data #########################")
            lines.append(readable_packet(self.data))
        lines.append(
            "###########################################################")
        return '\n'.join(lines)

    def set_option(self, opt: DHCPOption, value):
        if opt.value in [0, 255]:
            raise ValueError("Invalid option")
        if opt.value == 53:
            value = bytearray([value.value])
        elif opt.value in [50, 54, 1, 3, 6]:
            value = socket.inet_aton(value)
        elif opt.value in [51, 58, 59]:
            value = pack('!I', value)
        elif opt.value in [57]:
            value = pack('!H', value)
        elif opt.value in [12, 15, 56]:
            value = value.encode()
        elif opt.value in [28, 33, 42]:
            value = b''.join(socket.inet_aton(x) for x in value)
        elif opt.value in [55]:
            value = bytearray([v.value for v in value])
        elif opt.value in [61]:
            value = bytearray([1]) + mac_aton(value)
        else:
            value = bytearray(value)
        self.options[opt.value] = value

    def get_option(self, opt: DHCPOption):
        value = self.options[opt.value]
        if opt.value == 53:
            value = DHCPMessageType(value[0])
        elif opt.value in [50, 54, 1, 3, 6]:
            value = socket.inet_ntoa(value)
        elif opt.value in [51, 58, 59]:
            value = unpack('!I', value)[0]
        elif opt.value in [57]:
            value = unpack('!H', value)[0]
        elif opt.value in [12, 15, 56]:
            value = value.decode()
        elif opt.value in [28, 33, 42]:
            value = [
                socket.inet_ntoa(x)
                for x in [value[i:i + 4] for i in range(0, len(value), 4)]
            ]
        elif opt.value in [55]:
            value = [DHCPOption(x) for x in value]
        elif opt.value in [61]:
            value = mac_ntoa(value[1:])
        return value
