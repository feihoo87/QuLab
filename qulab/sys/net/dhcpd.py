#
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

#
# DHCP option codes
# -----------------
#
# 1   - Subnet mask
# 3   - Router(s)
# 6   - DNS name server(s)
# 12  - Hostname
# 15  - Domain name
# 28  - Broadcast address
# 33  - Static route
# 42  - Network time protocol servers
# 51  - IP address lease time
# 53  - DHCP Message Type (DHCPDISCOVER, DHCPOFFER, etc)
# 54  - Server identifier
# 55  - Parameter Request List
# 57  - Maximum DHCP Message Size
# 58  - Renewal (T1) time value
# 59  - Renewal (T2) time value
# 60  - Vendor Class Identifier
# 61  - Client Identifier
# 67  - Boot file name (e.g. PXE booting)
# 80  -
# 116 -
# 119 -
# 145 -
# 167 -
# 171 -
#

import asyncio
import logging
import socket
from typing import NamedTuple

from waveforms.sys.net.dhcp import (MAGIC_COOKIE, DHCPMessageType, DHCPOption,
                                    DHCPPacket)

logger = logging.getLogger(__name__)


class DHCPServerProtocol:

    def connection_made(self, transport):
        self.transport = transport
        address, port = self.transport.get_extra_info('sockname')
        self.server_ip = '192.168.254.1'

    def connection_lost(self, exc):
        pass

    def datagram_received(self, data, addr):
        try:
            received = DHCPPacket.decode(data)
        except ValueError as e:
            logger.error("Error decoding DHCP packet: %s", e)
            return

        print("\nReceived DHCP packet from %s:%d" % (addr[0], addr[1]))
        print(received)

        # see if there is a DHCP message type option
        if 53 not in received.options:
            return

        messagetype = received.get_option(DHCPOption.DHCP_MSG_TYPE)
        if (messagetype != DHCPMessageType.DISCOVER) and (
                messagetype != DHCPMessageType.REQUEST):
            logger.error(
                "ignoring: DHCP message type not supported by this implementation"
            )
            return

        try:
            assigned_ip, subnet, gateway = get_ip_from_mac(received.chaddr)
        except:
            return

        response = DHCPPacket()
        response.op = 2
        response.xid = received.xid
        response.flags = received.flags
        response.chaddr = received.chaddr
        response.yiaddr = assigned_ip
        response.siaddr = self.server_ip

        if messagetype == DHCPMessageType.DISCOVER:
            # DHCPOFFER
            response.set_option(DHCPOption.DHCP_MSG_TYPE,
                                DHCPMessageType.OFFER)
        elif messagetype == DHCPMessageType.REQUEST:
            # DHCPACK
            response.set_option(DHCPOption.DHCP_MSG_TYPE, DHCPMessageType.ACK)
        else:
            return

        lease_time = 86400
        response.set_option(DHCPOption.SUBNET_MASK, subnet)
        response.set_option(DHCPOption.ROUTER, gateway)
        response.set_option(DHCPOption.IP_LEASE_TIME, lease_time)
        response.set_option(DHCPOption.SERVER_ID, self.server_ip)

        response_packet = response.encode()

        # send it
        print("\nSending DHCP packet to %s:%d" % (addr[0], addr[1]))
        print(DHCPPacket.decode(response_packet))
        self.send_packet(response_packet, addr)

    def send_packet(self, packet, addr):
        if addr == ('0.0.0.0', 68):
            send_address = ('255.255.255.255', 68)
        else:
            send_address = addr
        self.transport.sendto(packet, send_address)


class IPConfig(NamedTuple):
    ip: str
    subnet: str
    gateway: str


ip_table = {
    '00:19:AF:04:92:C4':
    IPConfig(ip='192.168.254.150', subnet='255.255.255.0', gateway='0.0.0.0')
}


def get_ip_from_mac(macaddr):
    ip_config = ip_table.get(macaddr, None)
    return ip_config.ip, ip_config.subnet, ip_config.gateway


async def main(server_ip='0.0.0.0'):
    loop = asyncio.get_running_loop()

    transport, protocol = await loop.create_datagram_endpoint(
        lambda: DHCPServerProtocol(),
        local_addr=(server_ip, 67),
        allow_broadcast=True)

    # print('start', server_ip)

    try:
        await asyncio.sleep(3600)  # Serve for 1 hour.
    finally:
        transport.close()


if __name__ == '__main__':
    asyncio.run(main(server_ip='0.0.0.0'))
