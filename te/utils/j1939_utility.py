import itertools
import logging
import platform
import socket
from multiprocessing.pool import ThreadPool
from typing import List

import can

from te.interface.j1939 import J1939TouchEncoder
from te.interface.j1939.comm_interface.j1939_ca import J1939CA
from te.interface.j1939.comm_interface.j1939_ca_linux import J1939CALinux
from te.interface.j1939.comm_interface.j1939_ca_universal import J1939CAUniversal

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


def get_all_j1939_cas(bitrate: int = 500000) -> List[J1939CA]:
    i_names = get_all_can_interfaces()
    if not i_names:
        return []

    # Create J1939CA Objects
    j1939_cas = []
    for i_face in i_names:
        ca = create_j1939_ca(i_face=i_face, address=0x10, bitrate=bitrate, linux_j1939=platform.system() == 'Linux')
        j1939_cas.append(ca)

    return j1939_cas


def create_j1939_ca(i_face: str, address: int, bitrate: int = 500000, linux_j1939: bool = False) -> J1939CA:
    if linux_j1939:
        return J1939CALinux(interface_name=i_face, address=address)
    else:
        return J1939CAUniversal(interface_name=i_face, address=address, bitrate=bitrate)


def scan_bus_for_tes(i_face: str, bitrate: int = 500000) -> List[J1939TouchEncoder]:
    tes = []
    try:
        # Create J1939CA Object
        ca = create_j1939_ca(i_face=i_face, address=0x10, bitrate=bitrate, linux_j1939=platform.system() == 'Linux')

        # scan for devices
        devices = ca.scan_for_devices()
        if not devices:
            ca.disconnect()
            return tes

        for dev_name, dev_addr in devices:
            tes.append(J1939TouchEncoder(can_iface=ca.interface_name, address=dev_addr, name=dev_name, ca=ca))
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
