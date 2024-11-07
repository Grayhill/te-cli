from multiprocessing.pool import ThreadPool
from typing import List

from rich.console import Console

from te.interface.hid.comm_interface.hid_manager import HIDManager
from te.utils import hid_utility
from te.utils import j1939_utility
from te.interface import TouchEncoder


def discover_touch_encoders(bitrate: int = 500000) -> (HIDManager, List[TouchEncoder]):
    devices: List[TouchEncoder] = []
    # Discover CAN touch encoders
    devices += j1939_utility.discover_tes(bitrate=bitrate)

    # Discover HID touch encoders
    hid_manager, hid_devices = hid_utility.discover_tes()
    devices += hid_devices

    return hid_manager, devices


def pprint_discover_tes(fetch_ext_ver: bool = False) -> (List[TouchEncoder], HIDManager):
    console = Console()
    with console.status('Discovering Touch Encoders...', spinner='bouncingBar', spinner_style='bright_yellow'):
        hid_manager, devices = discover_touch_encoders()
        if len(devices) == 0:
            return [], hid_manager

        def _refresh_info(_device: TouchEncoder):
            _device.refresh_info()

        with ThreadPool(len(devices)) as t:
            t.map(_refresh_info, devices)

    return devices, hid_manager
