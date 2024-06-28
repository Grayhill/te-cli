import itertools
import logging
import platform
import re
import socket
from multiprocessing.pool import ThreadPool
from typing import List

import can

from te.interface.j1939 import J1939TouchEncoder, j1939_messages
from te.interface.j1939.comm_interface import J1939CA
from te.interface.j1939.comm_interface.j1939_ca_universal import J1939CAUniversal
from te.interface.j1939.comm_interface.j1939_ca_linux import J1939CALinux

MAX_DATA_SIZE = 1785
MAX_NUM_TE_PER_BUS = 5

can.set_logging_level('critical')


def get_all_can_interfaces() -> List[str]:
    system_os = platform.system()
    names: List[str] = []
    if system_os == 'Linux':
        for idx, name in socket.if_nameindex():
            if 'can' in name:
                names.append(name)
    elif system_os == 'Windows':
        for iface in can.detect_available_configs():
            if iface['interface'] == 'pcan':
                names.append(iface['channel'])
    return names


def create_j1939_ca(i_face: str, address: int, bitrate: int = 500000) -> J1939CA:
    system_os = platform.system()
    if system_os == 'Linux':
        return J1939CALinux(interface_name=i_face, address=address)
    elif system_os == 'Windows':
        return J1939CAUniversal(interface_name=i_face, address=address, bitrate=bitrate)
    else:  # Unsupported OS
        raise Exception('Unsupported OS')


def scan_bus_for_tes(i_face: str, bitrate: int = 500000) -> List[J1939TouchEncoder]:
    tes = []
    try:
        # Create J1939CA Object
        i_face_num = re.search(r'.*(\d+)', i_face).group(1)
        b_addr = int(i_face_num) * MAX_NUM_TE_PER_BUS + 1
        ca = create_j1939_ca(i_face=i_face, address=b_addr, bitrate=bitrate)

        # scan for devices
        msgs = ca.scan_for_devices()
        ca.disconnect()

        for m in msgs:
            m: j1939_messages.AddressClaimMsg = m
            addr = m.address
            b_addr += 1
            te_ca = create_j1939_ca(i_face=i_face, address=b_addr, bitrate=bitrate)
            tes.append(J1939TouchEncoder(can_iface=addr[0], address=addr[-1], name=m.j1939_name, ca=te_ca))
    except OSError as e:
        logging.error(f'CAN interface ({i_face}) is down. Please setup CAN network. {e}')

    return tes


def discover_tes(bitrate: int = 500000) -> List[J1939TouchEncoder]:
    i_names = get_all_can_interfaces()
    if not i_names:
        return []

    param = [(i_n, bitrate) for i_n in i_names]

    with ThreadPool(len(i_names)) as t:
        t_output = t.starmap(scan_bus_for_tes, param)
        tes = list(itertools.chain.from_iterable(t_output))
        return tes
